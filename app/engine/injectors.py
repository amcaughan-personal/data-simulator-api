from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from app.api.models import InjectorSpec


LABELS_KEY = "__labels"
IS_ANOMALY_KEY = "__is_anomaly"


def initialize_labels(rows: Sequence[dict[str, Any]]) -> None:
    for row in rows:
        row[IS_ANOMALY_KEY] = False
        row[LABELS_KEY] = []


def summarize_labels(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    total_anomalous_rows = 0
    anomaly_counts: dict[str, int] = {}

    for row in rows:
        labels = row.get(LABELS_KEY, [])
        if labels:
            total_anomalous_rows += 1
        for label in labels:
            anomaly_type = label["anomaly_type"]
            anomaly_counts[anomaly_type] = anomaly_counts.get(anomaly_type, 0) + 1

    return {
        "anomalous_rows": total_anomalous_rows,
        "anomaly_counts": anomaly_counts,
    }


def _tag_row(row: dict[str, Any], injector: InjectorSpec) -> None:
    row[IS_ANOMALY_KEY] = True
    row[LABELS_KEY].append(
        {
            "anomaly_type": injector.kind,
            "injector_id": injector.injector_id,
            "field": injector.field,
            "severity": injector.severity,
        }
    )


def _validate_field(rows: Sequence[dict[str, Any]], field: str) -> None:
    if rows and field not in rows[0]:
        raise ValueError(f"injector references unknown field: {field}")


def _end_index(end_index: int | None, row_count: int) -> int:
    return row_count if end_index is None else min(end_index, row_count)


def _apply_point_spike(rows: Sequence[dict[str, Any]], injector) -> None:
    indexes: list[int]
    if injector.mode == "rate":
        raise ValueError("point_spike rate mode requires an RNG")

    if injector.index is None or injector.index >= len(rows):
        return

    indexes = [injector.index]
    _apply_point_spike_indexes(rows, injector, indexes)


def _apply_point_spike_indexes(rows: Sequence[dict[str, Any]], injector, indexes: Sequence[int]) -> None:
    for index in indexes:
        row = rows[index]
        current_value = row[injector.field]

        if injector.value is not None:
            row[injector.field] = injector.value
        elif injector.offset is not None:
            row[injector.field] = current_value + injector.offset
        elif injector.scale is not None:
            row[injector.field] = current_value * injector.scale
        else:
            raise ValueError("point_spike requires one of value, offset, or scale")

        _tag_row(row, injector)


def _apply_level_shift(rows: Sequence[dict[str, Any]], injector) -> None:
    start = min(injector.start_index, len(rows))
    end = _end_index(injector.end_index, len(rows))

    for index in range(start, end):
        rows[index][injector.field] = rows[index][injector.field] + injector.offset
        _tag_row(rows[index], injector)


def _apply_missing_burst(rows: Sequence[dict[str, Any]], injector) -> None:
    if injector.start_index is None:
        return

    start = min(injector.start_index, len(rows))
    end = _end_index(injector.end_index, len(rows))

    for index in range(start, end):
        rows[index][injector.field] = None
        _tag_row(rows[index], injector)


def _apply_missing_indexes(rows: Sequence[dict[str, Any]], injector, indexes: Sequence[int]) -> None:
    for index in indexes:
        rows[index][injector.field] = None
        _tag_row(rows[index], injector)


def _apply_stuck_value(rows: Sequence[dict[str, Any]], injector) -> None:
    start = min(injector.start_index, len(rows))
    end = _end_index(injector.end_index, len(rows))

    if start >= len(rows):
        return

    stuck_value = rows[start][injector.field] if injector.value is None else injector.value
    for index in range(start, end):
        rows[index][injector.field] = stuck_value
        _tag_row(rows[index], injector)


def _rate_indexes(row_count: int, rate: float, rng: np.random.Generator) -> list[int]:
    return [index for index in range(row_count) if rng.random() < rate]


def apply_injectors(
    rows: Sequence[dict[str, Any]],
    injectors: Sequence[InjectorSpec],
    rng: np.random.Generator | None = None,
) -> None:
    for injector in injectors:
        _validate_field(rows, injector.field)

        if injector.kind == "point_spike":
            if injector.mode == "rate":
                if rng is None:
                    raise ValueError("rate-based injectors require an RNG")
                indexes = _rate_indexes(len(rows), injector.rate, rng)
                _apply_point_spike_indexes(rows, injector, indexes)
                continue
            _apply_point_spike(rows, injector)
            continue

        if injector.kind == "level_shift":
            _apply_level_shift(rows, injector)
            continue

        if injector.kind == "missing_burst":
            if injector.mode == "rate":
                if rng is None:
                    raise ValueError("rate-based injectors require an RNG")
                indexes = _rate_indexes(len(rows), injector.rate, rng)
                _apply_missing_indexes(rows, injector, indexes)
                continue
            _apply_missing_burst(rows, injector)
            continue

        if injector.kind == "stuck_value":
            _apply_stuck_value(rows, injector)
            continue

        raise ValueError(f"unsupported injector kind: {injector.kind}")
