from __future__ import annotations

from typing import Any

from app.api.models import FieldSpec, ScenarioGenerateRequest, ScenarioRequestBase, ScenarioSampleRequest
from app.engine.entities import EntityContext, build_entity_context, generate_entity_values
from app.engine.generators import generate_distribution_values, generate_primitive_values
from app.engine.labels import add_label, initialize_labels, summarize_labels
from app.engine.mutations import apply_mutations, validate_sample_compatible_mutations
from app.engine.process_modifiers import plan_process_modifiers, validate_sample_compatible_process_modifiers


def _generate_field_values(
    field: FieldSpec,
    rows: list[dict[str, object]],
    scenario_seed: int | None,
    entity_context: EntityContext,
    process_modifier_plans: list[Any],
) -> tuple[list[object], dict[int, list[dict[str, Any]]]]:
    generator = field.generator
    row_count = len(rows)

    if generator.kind in {"constant", "categorical", "sequence"}:
        return (
            generate_primitive_values(generator, row_count, scenario_seed, "field", field.name),
            {},
        )

    if generator.kind in {"distribution", "contextual_distribution"}:
        return generate_distribution_values(
            generator,
            field.name,
            rows,
            scenario_seed,
            entity_context,
            process_modifier_plans,
        )

    if generator.kind in {"entity_attribute", "entity_id"}:
        return generate_entity_values(generator, row_count, entity_context), {}

    raise ValueError(f"unsupported generator kind: {generator.kind}")


def _build_rows(request: ScenarioRequestBase, row_count: int, sample_only: bool = False) -> list[dict[str, Any]]:
    if sample_only:
        validate_sample_compatible_process_modifiers(request.process_modifiers)
        validate_sample_compatible_mutations(request.mutations)

    entity_context = build_entity_context(request.entity_pools, row_count, request.seed)
    rows = [{"__row_index": index} for index in range(row_count)]
    initialize_labels(rows)

    for field in request.fields:
        process_modifier_plans = plan_process_modifiers(rows, field.name, request.process_modifiers, request.seed)
        values, process_modifier_labels = _generate_field_values(
            field,
            rows,
            request.seed,
            entity_context,
            process_modifier_plans,
        )

        for index, value in enumerate(values):
            rows[index][field.name] = value

        for index, labels in process_modifier_labels.items():
            for label in labels:
                add_label(rows[index], label)

    apply_mutations(rows, request.mutations, request.seed)
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
    rows = _build_rows(request, row_count=1, sample_only=True)
    row = rows[0]

    return {
        "schema_version": request.schema_version,
        "scenario_name": request.name,
        "description": request.description,
        "seed": request.seed,
        "fields": [field.name for field in request.fields],
        "row": row,
    }
