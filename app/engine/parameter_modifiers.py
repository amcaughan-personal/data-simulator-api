from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.api.models import FieldMatchSpec, ParameterModifierSpec
from app.engine.distributions import resolve_distribution_parameter

if TYPE_CHECKING:
    from app.engine.entities import EntityContext


def matches_conditions(row: dict[str, Any], conditions: list[FieldMatchSpec]) -> bool:
    return all(row.get(condition.field) == condition.equals for condition in conditions)


def resolve_parameter_modifier_value(
    modifier: ParameterModifierSpec,
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


def apply_parameter_modifier(current_value: float, modifier: ParameterModifierSpec, modifier_value: float) -> float:
    if modifier.operation == "add":
        return current_value + modifier_value

    if modifier.operation == "multiply":
        return current_value * modifier_value

    if modifier.operation == "set":
        return modifier_value

    raise ValueError(f"unsupported modifier operation: {modifier.operation}")


def apply_parameter_modifiers(
    distribution: str,
    parameters: dict[str, Any],
    parameter_modifiers: list[ParameterModifierSpec],
    row: dict[str, Any],
    row_index: int,
    entity_context: "EntityContext",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    updated_parameters = dict(parameters)
    applied_adjustments: list[dict[str, Any]] = []

    for parameter_modifier in parameter_modifiers:
        if not matches_conditions(row, parameter_modifier.when):
            continue

        modifier_value = resolve_parameter_modifier_value(parameter_modifier, row, row_index, entity_context)
        current_value = resolve_distribution_parameter(distribution, updated_parameters, parameter_modifier.parameter)
        updated_value = apply_parameter_modifier(current_value, parameter_modifier, modifier_value)
        updated_parameters[parameter_modifier.parameter] = updated_value
        applied_adjustments.append(
            {
                "parameter": parameter_modifier.parameter,
                "operation": parameter_modifier.operation,
                "modifier_value": modifier_value,
                "resulting_value": updated_value,
            }
        )

    return updated_parameters, applied_adjustments
