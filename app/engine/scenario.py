from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np

from app.api.models import FieldSpec, ScenarioGenerateRequest, ScenarioRequestBase, ScenarioSampleRequest
from app.engine.distributions import sample_distribution
from app.engine.injectors import (
    apply_injectors,
    initialize_labels,
    summarize_labels,
    validate_stateless_injectors,
)


def _field_seed(rng: np.random.Generator) -> int:
    return int(rng.integers(0, 2**31 - 1))


def _generate_field_values(field: FieldSpec, row_count: int, rng: np.random.Generator) -> list[Any]:
    generator = field.generator

    if generator.kind == "constant":
        return [generator.value for _ in range(row_count)]

    if generator.kind == "categorical":
        return sample_distribution(
            distribution="categorical",
            parameters={"values": generator.values, "weights": generator.weights},
            count=row_count,
            seed=_field_seed(rng),
        )

    if generator.kind == "distribution":
        return sample_distribution(
            distribution=generator.distribution,
            parameters=generator.parameters,
            count=row_count,
            seed=_field_seed(rng),
        )

    raise ValueError(f"unsupported generator kind: {generator.kind}")


def _build_rows(request: ScenarioRequestBase, row_count: int, stateless_only: bool = False) -> list[dict[str, Any]]:
    rng = np.random.default_rng(request.seed)
    if stateless_only:
        validate_stateless_injectors(request.injectors)

    rows = [
        {
            "__row_index": index,
            "event_ts": (request.time.start + timedelta(seconds=index * request.time.frequency_seconds)).isoformat(),
        }
        for index in range(row_count)
    ]

    for field in request.fields:
        values = _generate_field_values(field, row_count, rng)
        for index, value in enumerate(values):
            rows[index][field.name] = value

    initialize_labels(rows)
    apply_injectors(rows, request.injectors, rng)
    return rows


def generate_scenario(request: ScenarioGenerateRequest) -> dict[str, Any]:
    rows = _build_rows(request, request.row_count)

    return {
        "schema_version": request.schema_version,
        "scenario_name": request.name,
        "description": request.description,
        "seed": request.seed,
        "row_count": len(rows),
        "fields": [field.name for field in request.fields],
        "rows": rows,
        "label_summary": summarize_labels(rows),
    }


def sample_scenario(request: ScenarioSampleRequest) -> dict[str, Any]:
    rows = _build_rows(request, row_count=1, stateless_only=True)
    row = rows[0]

    return {
        "schema_version": request.schema_version,
        "scenario_name": request.name,
        "description": request.description,
        "seed": request.seed,
        "fields": [field.name for field in request.fields],
        "row": row,
    }
