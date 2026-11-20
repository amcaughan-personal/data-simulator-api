"""Generate a dataset from a spec.

1. Lay out rows: their profile, individual and timestamp (`rows.py`).
2. Generate columns in order (common columns, then profile columns), so a column can
   depend on earlier ones. Each profile's rows use that profile's definition (`columns.py`).
3. Convert to JSON-ready rows (`output.py`).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from data_simulator.engine.columns import column_values, is_integer
from data_simulator.engine.frame import Frame, GenerationError
from data_simulator.engine.output import to_rows
from data_simulator.engine.rows import layout_rows
from data_simulator.rng import new_seed, rng_for
from data_simulator.spec import ColumnSpec, DatasetSpec

__all__ = ["GenerationError", "generate"]


def generate(spec: DatasetSpec, max_cells: int | None = None) -> dict[str, Any]:
    cells = spec.row_count * spec.column_count
    if max_cells is not None and cells > max_cells:
        raise GenerationError(
            f"spec would produce {cells:,} cells ({spec.row_count:,} rows x {spec.column_count} columns); "
            f"the limit is {max_cells:,}"
        )

    seed = spec.seed if spec.seed is not None else new_seed()
    frame = layout_rows(spec, seed)

    if frame.timestamps is not None:
        frame.columns[spec.rows.timestamp_column] = frame.timestamps
    if frame.individual is not None:
        frame.columns[spec.id_column] = frame.ids[frame.individual]
    if frame.profile is not None:
        frame.columns[spec.profile_column] = np.array(frame.profile_names, dtype=object)[frame.profile]

    for name in spec.column_order:
        frame.columns[name] = _generate_column(name, spec, frame)

    names = [*spec.generated_columns, *spec.column_order]
    return {
        "name": spec.name,
        "description": spec.description,
        "seed": seed,
        "row_count": frame.n,
        "columns": names,
        "rows": to_rows(frame, names),
    }


def _generate_column(name: str, spec: DatasetSpec, frame: Frame) -> np.ndarray:
    groups = _groups(name, spec, frame)
    defined = [column for column, _, _ in groups if column is not None]
    numeric = all(column.is_numeric for column in defined)
    if defined and all(is_integer(column) for column in defined):
        frame.integer_columns.add(name)

    result = np.full(frame.n, np.nan) if numeric else np.full(frame.n, None, dtype=object)
    for column, rows, key in groups:
        if column is None or len(rows) == 0:
            continue
        rng = rng_for(frame.seed, "column", name, key)
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
        result[rows] = values
    return result


def _groups(name: str, spec: DatasetSpec, frame: Frame) -> list[tuple[ColumnSpec | None, np.ndarray, str]]:
    """(definition, rows it applies to, seed key): one group for a common column, else one per profile."""
    if name in spec.common_columns:
        return [(spec.common_columns[name], np.arange(frame.n), "common")]
    return [
        (profile.columns[name], np.flatnonzero(frame.profile == index), profile_name)
        for index, (profile_name, profile) in enumerate(spec.profiles.items())
    ]


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
