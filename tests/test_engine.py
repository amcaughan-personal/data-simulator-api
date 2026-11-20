from collections import Counter

import numpy as np
import pytest

from data_simulator import DatasetSpec, generate
from data_simulator.api.examples import INSTITUTIONS, SENSOR_FLEET, TRANSACTIONS


def run(raw: dict) -> dict:
    return generate(DatasetSpec.model_validate(raw))


def column(dataset: dict, name: str) -> list:
    return [row[name] for row in dataset["rows"]]


def test_same_seed_gives_same_data():
    assert run(TRANSACTIONS) == run(TRANSACTIONS)
    assert run({**TRANSACTIONS, "seed": 1})["rows"] != run(TRANSACTIONS)["rows"]

    unseeded = run({**TRANSACTIONS, "seed": None})
    assert run({**TRANSACTIONS, "seed": unseeded["seed"]}) == unseeded


def test_adding_a_column_leaves_other_columns_unchanged():
    extra = {"name": "x", "type": "flag", "probability": 0.5}
    with_extra = {**TRANSACTIONS, "columns": [*TRANSACTIONS["columns"], extra]}
    assert column(run(with_extra), "amount") == column(run(TRANSACTIONS), "amount")


def test_one_row_per_entity():
    assert column(run(INSTITUTIONS), "institution_id") == [f"institution_{i:04d}" for i in range(1, 26)]


def test_time_series_per_entity():
    rows = run(SENSOR_FLEET)["rows"]
    assert len(rows) == 24 * 5
    assert [(r["timestamp"], r["device_id"]) for r in rows[:2]] == [
        ("2026-01-01T00:00:00Z", "device_0001"),
        ("2026-01-01T00:00:00Z", "device_0002"),
    ]
    assert rows[-1]["timestamp"] == "2026-01-01T23:00:00Z"

    # Entity attributes stay fixed for each device across all its rows.
    offsets = {(r["device_id"], r["device_offset"]) for r in rows}
    assert len(offsets) == 5


def test_events_at_random_times_are_sorted_within_range():
    timestamps = column(run(TRANSACTIONS), "timestamp")
    assert timestamps == sorted(timestamps)
    assert timestamps[0] >= "2026-03-01" and timestamps[-1] < "2026-03-08"


def test_effects():
    raw = {
        "rows": {"count": 200},
        "columns": [
            {"name": "tier", "type": "categorical", "values": ["standard", "premium"]},
            {"name": "x", "type": "sequence"},
            {
                "name": "by_tier",
                "type": "numeric",
                "base": 100,
                "effects": [{"field": "tier", "values": {"premium": 2}}],
            },
            {"name": "plus_x", "type": "numeric", "base": 10, "effects": [{"field": "x", "op": "add"}]},
        ],
    }
    dataset = run(raw)
    assert {(r["tier"], r["by_tier"]) for r in dataset["rows"]} == {("standard", 100), ("premium", 200)}
    assert column(dataset, "plus_x")[:3] == [11, 12, 13]


@pytest.mark.parametrize(
    ("noise", "check"),
    [
        ({"kind": "normal", "stddev": 5}, lambda v: v.std() == pytest.approx(5, rel=0.1)),
        ({"kind": "uniform", "width": 4}, lambda v: np.ptp(v) <= 4),
        (
            {"kind": "poisson"},
            lambda v: np.all(v == np.round(v)) and v.mean() == pytest.approx(100, rel=0.05),
        ),
    ],
)
def test_noise(noise, check):
    raw = {
        "seed": 2,
        "rows": {"count": 5000},
        "columns": [{"name": "y", "type": "numeric", "base": 100, "noise": noise}],
    }
    assert check(np.array(column(run(raw), "y")))


def test_missing_values():
    raw = {
        "seed": 8,
        "rows": {"count": 10000},
        "columns": [{"name": "y", "type": "numeric", "missing_rate": 0.1}],
    }
    assert column(run(raw), "y").count(None) == pytest.approx(1000, rel=0.15)


def test_skewed_popularity_concentrates_rows():
    def top_ten_share(popularity: str) -> float:
        raw = {
            "seed": 6,
            "rows": {"count": 5000},
            "entities": [{"name": "user", "count": 100, "popularity": popularity}],
            "columns": [{"name": "user_id", "type": "entity", "entity": "user"}],
        }
        return sum(n for _, n in Counter(column(run(raw), "user_id")).most_common(10)) / 5000

    assert top_ten_share("uniform") < 0.2 < 0.4 < top_ten_share("skewed")
