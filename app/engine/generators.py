from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.api.models import (
    CategoricalGeneratorSpec,
    ConstantGeneratorSpec,
    ContextualDistributionGeneratorSpec,
    DistributionGeneratorSpec,
    SequenceGeneratorSpec,
)
from app.engine.parameter_modifiers import apply_parameter_modifiers
from app.engine.process_modifiers import PlannedProcessModifier, apply_planned_process_modifiers
from app.engine.randomness import derive_seed
from app.engine.distributions import sample_distribution

if TYPE_CHECKING:
    from app.engine.entities import EntityContext


PrimitiveGenerator = DistributionGeneratorSpec | SequenceGeneratorSpec | ConstantGeneratorSpec | CategoricalGeneratorSpec
DistributionGenerator = DistributionGeneratorSpec | ContextualDistributionGeneratorSpec


def generate_primitive_values(
    generator: PrimitiveGenerator,
    row_count: int,
    scenario_seed: int | None,
    *seed_parts: Any,
) -> list[Any]:
    generator_seed = derive_seed(scenario_seed, *seed_parts)

    if generator.kind == "constant":
        return [generator.value for _ in range(row_count)]

    if generator.kind == "sequence":
        return [generator.start + (index * generator.step) for index in range(row_count)]

    if generator.kind == "categorical":
        return sample_distribution(
            distribution="categorical",
            parameters={"values": generator.values, "weights": generator.weights},
            count=row_count,
            seed=generator_seed,
        )

    if generator.kind == "distribution":
        return sample_distribution(
            distribution=generator.distribution,
            parameters=generator.parameters,
            count=row_count,
            seed=generator_seed,
        )

    raise ValueError(f"unsupported primitive generator kind: {generator.kind}")


def generate_distribution_values(
    generator: DistributionGenerator,
    field_name: str,
    rows: list[dict[str, Any]],
    scenario_seed: int | None,
    entity_context: "EntityContext",
    process_modifier_plans: list[PlannedProcessModifier] | None = None,
) -> tuple[list[Any], dict[int, list[dict[str, Any]]]]:
    values: list[Any] = []
    labels_by_index: dict[int, list[dict[str, Any]]] = {}
    planned_process_modifiers = process_modifier_plans or []

    for row_index, row in enumerate(rows):
        parameters = dict(generator.parameters)

        if generator.kind == "contextual_distribution":
            parameters, _ = apply_parameter_modifiers(
                generator.distribution,
                parameters,
                generator.parameter_modifiers,
                row,
                row_index,
                entity_context,
            )

        parameters, process_modifier_labels = apply_planned_process_modifiers(
            field_name,
            generator.distribution,
            parameters,
            row,
            row_index,
            planned_process_modifiers,
            entity_context,
        )

        sampled_value = sample_distribution(
            distribution=generator.distribution,
            parameters=parameters,
            count=1,
            seed=derive_seed(scenario_seed, "field", field_name, "row", row_index),
        )[0]

        if process_modifier_labels:
            labels_by_index[row_index] = [
                {
                    **label,
                    "generated_value": sampled_value,
                }
                for label in process_modifier_labels
            ]

        values.append(sampled_value)

    return values, labels_by_index
