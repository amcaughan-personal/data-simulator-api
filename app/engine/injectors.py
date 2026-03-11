from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.api.models import InjectorSpec, MutationSpec, SelectionSpec


LABELS_KEY = "__labels"
IS_ANOMALY_KEY = "__is_anomaly"


@dataclass(frozen=True)
class SelectionBehavior:
    stateless: bool
    select_indexes: Callable[[int, SelectionSpec, np.random.Generator], list[int]]


@dataclass(frozen=True)
class MutationBehavior:
    stateless: bool
    apply: Callable[[Sequence[dict[str, Any]], Sequence[int], str, MutationSpec], None]


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
            "anomaly_type": injector.mutation.kind,
            "injector_id": injector.injector_id,
            "field": injector.field,
            "selection_kind": injector.selection.kind,
            "severity": injector.severity,
        }
    )


def _validate_field(rows: Sequence[dict[str, Any]], field: str) -> None:
    if rows and field not in rows[0]:
        raise ValueError(f"injector references unknown field: {field}")


def _end_index(end_index: int | None, row_count: int) -> int:
    return row_count if end_index is None else min(end_index, row_count)


def _select_index(row_count: int, selection: SelectionSpec, rng: np.random.Generator) -> list[int]:
    if selection.index >= row_count:
        return []
    return [selection.index]


def _select_window(row_count: int, selection: SelectionSpec, rng: np.random.Generator) -> list[int]:
    start = min(selection.start_index, row_count)
    end = _end_index(selection.end_index, row_count)
    return list(range(start, end))


def _select_rate(row_count: int, selection: SelectionSpec, rng: np.random.Generator) -> list[int]:
    return [index for index in range(row_count) if rng.random() < selection.rate]


def _select_count(row_count: int, selection: SelectionSpec, rng: np.random.Generator) -> list[int]:
    actual_count = min(selection.count, row_count)
    if actual_count <= 0:
        return []
    return sorted(rng.choice(row_count, size=actual_count, replace=False).tolist())


def _apply_offset(rows: Sequence[dict[str, Any]], indexes: Sequence[int], field: str, mutation: MutationSpec) -> None:
    for index in indexes:
        rows[index][field] = rows[index][field] + mutation.amount


def _apply_scale(rows: Sequence[dict[str, Any]], indexes: Sequence[int], field: str, mutation: MutationSpec) -> None:
    for index in indexes:
        rows[index][field] = rows[index][field] * mutation.factor


def _apply_set_value(rows: Sequence[dict[str, Any]], indexes: Sequence[int], field: str, mutation: MutationSpec) -> None:
    for index in indexes:
        rows[index][field] = mutation.value


def _apply_set_missing(rows: Sequence[dict[str, Any]], indexes: Sequence[int], field: str, mutation: MutationSpec) -> None:
    for index in indexes:
        rows[index][field] = None


SELECTION_BEHAVIORS: dict[str, SelectionBehavior] = {
    "count": SelectionBehavior(stateless=False, select_indexes=_select_count),
    "index": SelectionBehavior(stateless=False, select_indexes=_select_index),
    "rate": SelectionBehavior(stateless=True, select_indexes=_select_rate),
    "window": SelectionBehavior(stateless=False, select_indexes=_select_window),
}

MUTATION_BEHAVIORS: dict[str, MutationBehavior] = {
    "offset": MutationBehavior(stateless=True, apply=_apply_offset),
    "scale": MutationBehavior(stateless=True, apply=_apply_scale),
    "set_missing": MutationBehavior(stateless=True, apply=_apply_set_missing),
    "set_value": MutationBehavior(stateless=True, apply=_apply_set_value),
}


def injector_is_stateless(injector: InjectorSpec) -> bool:
    selection_behavior = SELECTION_BEHAVIORS[injector.selection.kind]
    mutation_behavior = MUTATION_BEHAVIORS[injector.mutation.kind]
    return selection_behavior.stateless and mutation_behavior.stateless


def validate_stateless_injectors(injectors: Sequence[InjectorSpec]) -> None:
    non_stateless = [
        injector.injector_id
        for injector in injectors
        if not injector_is_stateless(injector)
    ]

    if non_stateless:
        ids = ", ".join(non_stateless)
        raise ValueError(f"scenario sample only supports stateless injectors; invalid injectors: {ids}")


def apply_injectors(
    rows: Sequence[dict[str, Any]],
    injectors: Sequence[InjectorSpec],
    rng: np.random.Generator,
) -> None:
    for injector in injectors:
        _validate_field(rows, injector.field)

        selection_behavior = SELECTION_BEHAVIORS[injector.selection.kind]
        mutation_behavior = MUTATION_BEHAVIORS[injector.mutation.kind]

        indexes = selection_behavior.select_indexes(len(rows), injector.selection, rng)
        mutation_behavior.apply(rows, indexes, injector.field, injector.mutation)

        for index in indexes:
            _tag_row(rows[index], injector)
