"""Generate a dataset from a spec.

1. Lay out rows: their profile, individual and timestamp (`rows.py`).
2. Generate columns in order (common columns, then profile columns), so a column can
   depend on earlier ones. Each profile's rows use that profile's definition (`columns.py`).
3. Convert to JSON-ready rows (`output.py`).

Streams (`stream.py`) lay out rows in fixed time buckets instead, then run the same steps
2 and 3 on each bucket.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from data_simulator.engine.columns import column_values, is_integer
from data_simulator.engine.frame import Frame, GenerationError
from data_simulator.engine.output import to_rows
from data_simulator.engine.rows import layout_rows
from data_simulator.engine.stream import stream_layouts
from data_simulator.rng import new_seed, rng_for
from data_simulator.spec import Anomaly, ColumnSpec, DatasetSpec, StreamSpec, Window, _TableSpec

__all__ = ["GenerationError", "column_types", "generate", "generate_window"]


def generate(spec: DatasetSpec, max_cells: int | None = None) -> dict[str, Any]:
    cells = spec.row_count * spec.column_count
    if max_cells is not None and cells > max_cells:
        raise GenerationError(
            f"spec would produce {cells:,} cells ({spec.row_count:,} rows x {spec.column_count} columns); "
            f"the limit is {max_cells:,}"
        )

    seed = spec.seed if spec.seed is not None else new_seed()
    frame = layout_rows(spec, seed)
    _fill_columns(spec, frame)

    return {
        "name": spec.name,
        "description": spec.description,
        "seed": seed,
        "row_count": frame.n,
        "columns": spec.output_columns,
        "types": column_types(spec),
        "rows": to_rows(frame, spec.output_columns),
    }


def generate_window(spec: StreamSpec, window: Window, max_cells: int | None = None) -> dict[str, Any]:
    names = spec.output_columns
    layouts, row_count = [], 0
    for frame, keep in stream_layouts(spec, window.from_, window.to):
        row_count += int(keep.sum())
        if max_cells is not None and row_count * len(names) > max_cells:
            raise GenerationError(
                f"window has more than {max_cells // len(names):,} rows ({len(names)} columns, "
                f"limit {max_cells:,} cells); ask for a shorter window"
            )
        if keep.any():
            layouts.append((frame, keep))

    rows: list[dict[str, Any]] = []
    for frame, keep in layouts:
        _fill_columns(spec, frame)
        frame.columns = {name: values[keep] for name, values in frame.columns.items()}
        rows.extend(to_rows(frame, names))

    return {
        "name": spec.name,
        "description": spec.description,
        "seed": spec.seed,
        "start": _iso(spec.start),
        "window": {"from": _iso(window.from_), "to": _iso(window.to)},
        "row_count": len(rows),
        "columns": names,
        "types": column_types(spec),
        "rows": rows,
    }


def column_types(spec: _TableSpec) -> dict[str, str]:
    """Each output column's type: integer, number, string, boolean or timestamp.

    Known from the spec alone (validation makes every profile agree), so it's the same
    for every response and every stream window. Any value may also be null.
    """
    types = {spec.rows.timestamp_column: "timestamp"} if spec.rows.has_timestamps else {}
    if spec.has_ids:
        types[spec.id_column] = "string"
    if spec.profiles:
        types[spec.profile_column] = "string"
    for name in spec.column_order:
        defined = [column for column in spec.specs_for(name) if column is not None]
        kinds = {column.value_type for column in defined} - {None}
        kind = kinds.pop() if kinds else "string"
        if kind == "number" and all(is_integer(column) for column in defined):
            kind = "integer"
        types[name] = kind
    if spec.has_anomalies:
        types[spec.anomaly_column] = "string"
    return types


def _iso(value) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _fill_columns(spec: _TableSpec, frame: Frame) -> None:
    """Add the generated columns (timestamp, id, profile), then every defined column."""
    if frame.timestamps is not None:
        frame.columns[spec.rows.timestamp_column] = frame.timestamps
    if frame.individual is not None:
        frame.columns[spec.id_column] = frame.ids[frame.individual]
    if frame.profile is not None:
        frame.columns[spec.profile_column] = np.array(frame.profile_names, dtype=object)[frame.profile]

    if spec.has_anomalies:
        frame.anomaly_labels = np.full(frame.n, None, dtype=object)

    for name in spec.column_order:
        frame.columns[name] = _generate_column(name, spec, frame)
        values = frame.columns[name]
        if values.dtype != object and np.isinf(values).any():
            raise GenerationError(
                f"{name}: values overflowed to infinity; use smaller numbers or a gentler trend"
            )

    if frame.anomaly_labels is not None:
        frame.columns[spec.anomaly_column] = frame.anomaly_labels


def _generate_column(name: str, spec: _TableSpec, frame: Frame) -> np.ndarray:
    groups = _groups(name, spec, frame)
    defined = [column for column, _, _ in groups if column is not None]
    numeric = all(column.is_numeric for column in defined)
    if defined and all(is_integer(column) for column in defined):
        frame.integer_columns.add(name)

    result = np.full(frame.n, np.nan) if numeric else np.full(frame.n, None, dtype=object)
    for column, rows, key in groups:
        if column is None or len(rows) == 0:
            continue
        # Values fixed per individual must match across stream buckets, so use the fixed seed.
        rng = rng_for(frame.fixed_seed if column.per else frame.seed, "column", name, key)
        values = (
            _per_individual(column, rows, key, frame, rng)
            if column.per
            else column_values(column, rows, frame, rng)
        )
        if column.missing > 0:
            missing = rng_for(frame.seed, "column", name, key, "missing").random(len(rows)) < column.missing
            if values.dtype == object:
                values = values.copy()
                values[missing] = None
            else:
                values = np.where(missing, np.nan, values)
        for index, anomaly in enumerate(column.anomalies):
            anomaly_rng = rng_for(frame.seed, "column", name, key, "anomaly", index)
            values = _apply_anomaly(anomaly, values, rows, frame, anomaly_rng)
        if column.anomalies and column.round is not None and values.dtype != object:
            values = np.round(values, column.round)  # anomalies may break the normal range, not the rounding
        result[rows] = values
    return result


def _groups(name: str, spec: _TableSpec, frame: Frame) -> list[tuple[ColumnSpec | None, np.ndarray, str]]:
    """(definition, rows it applies to, seed key): one group for a common column, else one per profile."""
    if name in spec.common_columns:
        return [(spec.common_columns[name], np.arange(frame.n), "common")]
    return [
        (profile.columns[name], np.flatnonzero(frame.profile == index), profile_name)
        for index, (profile_name, profile) in enumerate(spec.profiles.items())
    ]


def _apply_anomaly(
    anomaly: Anomaly, values: np.ndarray, rows: np.ndarray, frame: Frame, rng: np.random.Generator
) -> np.ndarray:
    hit = np.ones(len(rows), dtype=bool)
    if anomaly.between is not None:
        start, end = (np.datetime64(t.replace(tzinfo=None), "ms") for t in anomaly.between)
        timestamps = frame.timestamps[rows]
        hit &= (timestamps >= start) & (timestamps < end)
    if anomaly.chance is not None:
        hit &= rng.random(len(rows)) < anomaly.chance
    if not hit.any():
        return values

    values = values.copy()
    if anomaly.multiply is not None:
        values[hit] = values[hit] * anomaly.multiply
    elif anomaly.add is not None:
        values[hit] = values[hit] + anomaly.add
    elif values.dtype == object:
        values[hit] = anomaly.set
    else:
        values[hit] = np.nan if anomaly.set is None else float(anomaly.set)

    labels = frame.anomaly_labels
    for row in rows[hit]:
        labels[row] = anomaly.name if labels[row] is None else f"{labels[row]}, {anomaly.name}"
    return values


def _per_individual(
    column: ColumnSpec, rows: np.ndarray, key: str, frame: Frame, rng: np.random.Generator
) -> np.ndarray:
    """Draw one value per individual, then give each row its individual's value."""
    if key == "common":
        owners = np.arange(len(frame.ids))
    else:
        owners = np.flatnonzero(frame.individual_profile == frame.profile_names.index(key))
    per_owner = column_values(column, owners, None, rng)
    lookup = np.empty(len(frame.ids), dtype=per_owner.dtype)
    lookup[owners] = per_owner
    return lookup[frame.individual[rows]]
