"""Request examples shown on the interactive /docs page."""

from __future__ import annotations

from typing import Any

from fastapi.openapi.models import Example

TRANSACTIONS: dict[str, Any] = {
    "name": "transactions",
    "description": "Card transactions at random times from standard and premium cards.",
    "seed": 34,
    "profiles": {
        "standard_card": {
            "count": 32,
            "columns": {
                "amount": {"lognormal": {"median": 35, "sigma": 0.8}, "round": 2},
                "items": {"poisson": {"mean": 2}, "min": 1},
                "declined": {"bernoulli": 0.03},
            },
        },
        "premium_card": {
            "count": 8,
            "columns": {
                "amount": {"lognormal": {"median": 60, "sigma": 0.6}, "round": 2},
                "items": {"poisson": {"mean": 4}, "min": 1},
                "declined": {"bernoulli": 0.01},
            },
        },
    },
    "common_columns": {
        "channel": {"categorical": {"in_store": 0.6, "online": 0.4}},
    },
    "rows": {
        "count": 200,
        "between": ["2026-03-01", "2026-03-08"],
        "from": {"standard_card": 0.8, "premium_card": 0.2},
    },
    "profile_column": "card_type",
    "id_column": "card_id",
}

INSTITUTIONS: dict[str, Any] = {
    "name": "institutions",
    "description": "One row per institution.",
    "seed": 1,
    "profiles": {
        "bank": {
            "count": 12,
            "columns": {
                "employees": {"lognormal": {"median": 1000, "sigma": 0.9}, "round": 0},
                "is_public": {"bernoulli": 0.5},
            },
        },
        "credit_union": {
            "count": 8,
            "columns": {
                "employees": {"lognormal": {"median": 160, "sigma": 0.7}, "round": 0},
                "is_public": {"constant": 0},
            },
        },
        "insurer": {
            "count": 5,
            "columns": {
                "employees": {"lognormal": {"median": 400, "sigma": 0.9}, "round": 0},
                "is_public": {"bernoulli": 0.4},
            },
        },
    },
    "common_columns": {
        "region": {"categorical": ["west", "midwest", "south", "northeast"]},
    },
    "rows": {"one_each": True},
}

SENSOR_FLEET: dict[str, Any] = {
    "name": "sensor_fleet",
    "description": (
        "Hourly readings from indoor and outdoor sensors. Each sensor reads a bit high or low; "
        "indoor sensors sometimes go dead, and outdoor ones see an afternoon heatwave."
    ),
    "seed": 3,
    "profiles": {
        "indoor": {
            "count": 3,
            "columns": {
                "temperature_c": {
                    "constant": 21,
                    "add_column": "calibration_offset",
                    "noise": {"random_walk": {"step": 0.1}},
                    "round": 2,
                    "anomalies": [{"name": "sensor_dead", "set": None, "chance": 0.03}],
                }
            },
        },
        "outdoor": {
            "count": 2,
            "columns": {
                "temperature_c": {
                    "constant": 12,
                    "add_column": "calibration_offset",
                    "seasonality": [{"period": "1d", "amplitude": 5, "peak": "15h"}],
                    "noise": {"normal": {"stddev": 0.5}},
                    "round": 2,
                    "anomalies": [
                        {
                            "name": "heatwave",
                            "add": 8,
                            "between": ["2026-01-01T12:00:00Z", "2026-01-01T17:00:00Z"],
                        }
                    ],
                }
            },
        },
    },
    "common_columns": {
        "calibration_offset": {"normal": {"mean": 0, "stddev": 0.8}, "per": "id", "round": 2},
    },
    "rows": {"every": "1h", "count": 24, "one_each": True},
}

WEB_TRAFFIC: dict[str, Any] = {
    "name": "web_traffic",
    "description": "Hourly page views for two weeks: growing 1% a day, busiest at 2pm and midweek.",
    "seed": 1,
    "common_columns": {
        "page_views": {
            "constant": 1000,
            "trend": {"growth": 0.01, "per": "1d"},
            "seasonality": [
                {"period": "1d", "amplitude": 400, "peak": "14h"},
                {"period": "7d", "amplitude": 150, "peak": "2d"},
            ],
            "noise": {"poisson": True},
        }
    },
    "rows": {"every": "1h", "count": 336, "start": "2026-03-02T00:00:00Z"},
}

DATASET_EXAMPLES: dict[str, Example] = {
    "transactions": Example(summary="Two profiles, rows drawn 80/20 at random times", value=TRANSACTIONS),
    "institutions": Example(summary="One row per institution, three profiles", value=INSTITUTIONS),
    "sensor_fleet": Example(summary="Hourly time series per sensor", value=SENSOR_FLEET),
    "web_traffic": Example(summary="One time series with trend and cycles", value=WEB_TRAFFIC),
}
