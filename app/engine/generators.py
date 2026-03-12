from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.api.models import (
    CategoricalGeneratorSpec,
    ConstantGeneratorSpec,
    ContextualDistributionGeneratorSpec,
    DistributionGeneratorSpec,
    FieldMatchSpec,
)
from app.engine.distributions import resolve_distribution_parameter, sample_distribution
from app.engine.randomness import derive_seed

if TYPE_CHECKING:
    from app.engine.entities import EntityContext


PrimitiveGenerator = DistributionGeneratorSpec | ConstantGeneratorSpec | CategoricalGeneratorSpec


def generate_primitive_values(
    generator: PrimitiveGenerator,
    row_count: int,
    scenario_seed: int | None,
    *seed_parts: Any,
) -> list[Any]:
    generator_seed = derive_seed(scenario_seed, *seed_parts)

    if generator.kind == "constant":
        return [generator.value for _ in range(row_count)]

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


def _matches_conditions(row: dict[str, Any], conditions: list[FieldMatchSpec]) -> bool:
    return all(row.get(condition.field) == condition.equals for condition in conditions)


def _resolve_modifier_value(
    modifier: Any,
    row: dict[str, Any],
    row_index: int,
    entity_context: "EntityContext",
) -> float:
    from app.engine.entities import resolve_entity_attribute_value

    if modifier.value is not None:
        return modifier.value

    if modifier.source_field is not None:
        return float(row[modifier.source_field])

    return float(
        resolve_entity_attribute_value(
            entity_context,
            modifier.entity_name,
            modifier.entity_attribute,
            row_index,
        )
    )


def _apply_modifier(current_value: float, modifier: Any, modifier_value: float) -> float:
    if modifier.operation == "add":
        return current_value + modifier_value

    if modifier.operation == "multiply":
        return current_value * modifier_value

    if modifier.operation == "set":
        return modifier_value

    raise ValueError(f"unsupported modifier operation: {modifier.operation}")


def generate_contextual_distribution_values(
    generator: ContextualDistributionGeneratorSpec,
    field_name: str,
    rows: list[dict[str, Any]],
    scenario_seed: int | None,
    entity_context: "EntityContext",
) -> list[Any]:
    values: list[Any] = []

    for row_index, row in enumerate(rows):
        parameters = dict(generator.parameters)

        for modifier in generator.parameter_modifiers:
            if not _matches_conditions(row, modifier.when):
                continue

            modifier_value = _resolve_modifier_value(modifier, row, row_index, entity_context)
            current_value = resolve_distribution_parameter(generator.distribution, parameters, modifier.parameter)
            parameters[modifier.parameter] = _apply_modifier(current_value, modifier, modifier_value)

        values.append(
            sample_distribution(
                distribution=generator.distribution,
                parameters=parameters,
                count=1,
                seed=derive_seed(scenario_seed, "field", field_name, "row", row_index),
            )[0]
        )

    return values
