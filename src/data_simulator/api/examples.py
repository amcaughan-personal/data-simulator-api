"""Request examples shown on the interactive /docs page."""

from __future__ import annotations

from typing import Any

from fastapi.openapi.models import Example

INSTITUTIONS: dict[str, Any] = {
    "name": "institutions",
    "description": "One row per institution. Banks tend to be bigger.",
    "seed": 7,
    "rows": {"one_per": "institution"},
    "entities": [{"name": "institution", "count": 25}],
    "columns": [
        {"name": "institution_id", "type": "entity", "entity": "institution"},
        {"name": "type", "type": "categorical", "values": {"bank": 5, "credit_union": 3, "insurer": 2}},
        {"name": "region", "type": "categorical", "values": ["west", "midwest", "south", "northeast"]},
        {
            "name": "employees",
            "type": "numeric",
            "base": {"dist": "lognormal", "median": 400, "sigma": 0.9},
            "effects": [{"field": "type", "op": "multiply", "values": {"bank": 2.5, "credit_union": 0.4}}],
            "decimals": 0,
        },
        {"name": "is_public", "type": "flag", "probability": 0.3},
    ],
}

TRANSACTIONS: dict[str, Any] = {
    "name": "transactions",
    "description": "Card transactions at random times. A few cards are used a lot; premium cards spend more.",
    "seed": 42,
    "rows": {"count": 200, "between": ["2026-03-01T00:00:00Z", "2026-03-08T00:00:00Z"]},
    "entities": [
        {
            "name": "card",
            "count": 40,
            "popularity": "skewed",
            "attributes": [{"name": "tier", "type": "categorical", "values": {"standard": 8, "premium": 2}}],
        }
    ],
    "columns": [
        {"name": "card_id", "type": "entity", "entity": "card"},
        {"name": "card_tier", "type": "entity", "entity": "card", "attribute": "tier"},
        {
            "name": "amount",
            "type": "numeric",
            "base": {"dist": "lognormal", "median": 35, "sigma": 0.8},
            "effects": [{"field": "card_tier", "op": "multiply", "values": {"premium": 1.8}}],
            "min": 0.5,
            "decimals": 2,
        },
        {"name": "channel", "type": "categorical", "values": {"in_store": 6, "online": 4}},
    ],
}

SENSOR_FLEET: dict[str, Any] = {
    "name": "sensor_fleet",
    "description": "Hourly readings per device. Each device reads a bit high or low, and drifts.",
    "seed": 3,
    "rows": {"every": "1h", "count": 24, "one_per": "device"},
    "entities": [
        {
            "name": "device",
            "count": 5,
            "attributes": [
                {
                    "name": "offset",
                    "type": "numeric",
                    "base": {"dist": "normal", "stddev": 1.5},
                    "decimals": 2,
                }
            ],
        }
    ],
    "columns": [
        {"name": "device_id", "type": "entity", "entity": "device"},
        {"name": "device_offset", "type": "entity", "entity": "device", "attribute": "offset"},
        {
            "name": "temperature_c",
            "type": "numeric",
            "base": 21.0,
            "effects": [{"field": "device_offset", "op": "add"}],
            "noise": {"kind": "random_walk", "step": 0.2},
            "decimals": 2,
            "missing_rate": 0.02,
        },
    ],
}

DATASET_EXAMPLES: dict[str, Example] = {
    "institutions": Example(summary="One row per institution", value=INSTITUTIONS),
    "transactions": Example(summary="Events at random times", value=TRANSACTIONS),
    "sensor_fleet": Example(summary="Hourly time series per device", value=SENSOR_FLEET),
}
