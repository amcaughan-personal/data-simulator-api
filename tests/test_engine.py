from collections import Counter

import numpy as np
import pytest

from data_simulator import DatasetSpec, generate
from data_simulator.api.examples import INSTITUTIONS, SENSOR_FLEET, TRANSACTIONS
from data_simulator.engine import GenerationError


def run(raw: dict, **kwargs) -> dict:
    return generate(DatasetSpec.model_validate(raw), **kwargs)


def column(dataset: dict, name: str) -> list:
    return [row[name] for row in dataset["rows"]]


@pytest.mark.parametrize("example", [INSTITUTIONS, TRANSACTIONS, SENSOR_FLEET])
def test_examples_generate(example):
    dataset = run(example)
    assert dataset["row_count"] == len(dataset["rows"]) > 0
    assert list(dataset["rows"][0]) == dataset["columns"]


def test_same_seed_same_data_and_different_seed_different_data():
    assert run(TRANSACTIONS) == run(TRANSACTIONS)
    assert run({**TRANSACTIONS, "seed": 1})["rows"] != run(TRANSACTIONS)["rows"]


def test_random_seed_is_reported_and_reproduces():
    unseeded = {**TRANSACTIONS, "seed": None}
    first = run(unseeded)
    assert run({**unseeded, "seed": first["seed"]}) == first


def test_adding_a_column_does_not_change_other_columns():
    extra = {
        **TRANSACTIONS,
        "columns": [*TRANSACTIONS["columns"], {"name": "x", "type": "flag", "probability": 0.5}],
    }
    assert column(run(extra), "amount") == column(run(TRANSACTIONS), "amount")


def test_one_row_per_entity():
    dataset = run(INSTITUTIONS)
    ids = column(dataset, "institution_id")
    assert ids == [f"institution_{i:04d}" for i in range(1, 26)]


def test_regular_time_series_per_entity():
    dataset = run(SENSOR_FLEET)
    assert dataset["row_count"] == 24 * 5
    first_hour = dataset["rows"][:5]
    assert {row["timestamp"] for row in first_hour} == {"2026-01-01T00:00:00Z"}
    assert [row["device_id"] for row in first_hour] == [f"device_{i:04d}" for i in range(1, 6)]
    assert dataset["rows"][5]["timestamp"] == "2026-01-01T01:00:00Z"
    assert dataset["rows"][-1]["timestamp"] == "2026-01-01T23:00:00Z"


def test_entity_attributes_are_stable_per_entity():
    dataset = run(SENSOR_FLEET)
    offsets: dict[str, set] = {}
    for row in dataset["rows"]:
        offsets.setdefault(row["device_id"], set()).add(row["device_offset"])
    assert all(len(values) == 1 for values in offsets.values())


def test_random_timestamps_are_sorted_and_in_range():
    timestamps = column(run(TRANSACTIONS), "timestamp")
    assert timestamps == sorted(timestamps)
    assert timestamps[0] >= "2026-03-01" and timestamps[-1] < "2026-03-08"


def test_lookup_effect_shifts_values():
    raw = {
        "seed": 1,
        "rows": {"count": 4000},
        "columns": [
            {"name": "tier", "type": "categorical", "values": ["standard", "premium"]},
            {
                "name": "spend",
                "type": "numeric",
                "base": 100,
                "effects": [{"field": "tier", "values": {"premium": 2}}],
            },
        ],
    }
    by_tier = {row["tier"]: row["spend"] for row in run(raw)["rows"]}
    assert by_tier == {"standard": 100.0, "premium": 200.0}


def test_numeric_effect_multiplies_or_adds_the_column():
    raw = {
        "rows": {"count": 3},
        "columns": [
            {"name": "x", "type": "sequence", "start": 1},
            {"name": "times_x", "type": "numeric", "base": 10, "effects": [{"field": "x", "op": "multiply"}]},
            {"name": "plus_x", "type": "numeric", "base": 10, "effects": [{"field": "x", "op": "add"}]},
        ],
    }
    dataset = run(raw)
    assert column(dataset, "times_x") == [10.0, 20.0, 30.0]
    assert column(dataset, "plus_x") == [11.0, 12.0, 13.0]


def test_lookup_effect_on_numeric_needs_values():
    raw = {
        "rows": {"count": 3},
        "columns": [
            {"name": "label", "type": "categorical", "values": ["a"]},
            {"name": "y", "type": "numeric", "base": 1, "effects": [{"field": "label"}]},
        ],
    }
    with pytest.raises(GenerationError, match="needs 'values'"):
        run(raw)


def test_flag_probability_and_effects():
    raw = {
        "seed": 5,
        "rows": {"count": 20000},
        "columns": [
            {"name": "risk", "type": "categorical", "values": ["low", "high"]},
            {
                "name": "declined",
                "type": "flag",
                "probability": 0.05,
                "effects": [{"field": "risk", "values": {"high": 4}}],
            },
        ],
    }
    rows = run(raw)["rows"]
    rate = {
        tier: np.mean([row["declined"] for row in rows if row["risk"] == tier]) for tier in ("low", "high")
    }
    assert rate["low"] == pytest.approx(0.05, abs=0.01)
    assert rate["high"] == pytest.approx(0.20, abs=0.02)
    assert {row["declined"] for row in rows} == {0, 1}


def test_noise_kinds():
    def noisy(noise):
        raw = {
            "seed": 2,
            "rows": {"count": 5000},
            "columns": [{"name": "y", "type": "numeric", "base": 100, "noise": noise}],
        }
        return np.array(column(run(raw), "y"))

    assert noisy({"kind": "normal", "stddev": 5}).std() == pytest.approx(5, rel=0.1)
    assert noisy({"kind": "normal", "stddev": 0.1, "relative": True}).std() == pytest.approx(10, rel=0.1)
    assert np.ptp(noisy({"kind": "uniform", "width": 4})) <= 4
    counts = noisy({"kind": "poisson"})
    assert np.all(counts == np.round(counts)) and counts.mean() == pytest.approx(100, rel=0.05)
    walk = noisy({"kind": "random_walk", "step": 1})
    assert abs(walk[-1] - 100) > abs(walk[1] - 100)  # it wanders further over time


def test_distributions_and_integer_output():
    raw = {
        "seed": 9,
        "rows": {"count": 2000},
        "columns": [
            {"name": "n", "type": "numeric", "base": {"dist": "poisson", "mean": 3}},
            {"name": "u", "type": "numeric", "base": {"dist": "uniform", "low": 5, "high": 6}},
            {"name": "price", "type": "numeric", "base": {"dist": "lognormal", "median": 20}, "decimals": 0},
        ],
    }
    dataset = run(raw)
    assert all(isinstance(value, int) for value in column(dataset, "n"))
    assert all(isinstance(value, int) for value in column(dataset, "price"))
    assert all(5 <= value < 6 for value in column(dataset, "u"))
    assert np.median(column(dataset, "price")) == pytest.approx(20, rel=0.1)


def test_clip_and_round():
    raw = {
        "seed": 4,
        "rows": {"count": 1000},
        "columns": [
            {
                "name": "y",
                "type": "numeric",
                "base": {"dist": "normal", "stddev": 10},
                "min": 0,
                "max": 5,
                "decimals": 1,
            }
        ],
    }
    values = column(run(raw), "y")
    assert min(values) == 0 and max(values) == 5
    assert all(round(value, 1) == value for value in values)


def test_missing_rate():
    raw = {
        "seed": 8,
        "rows": {"count": 10000},
        "columns": [
            {"name": "y", "type": "numeric", "base": 1, "missing_rate": 0.1},
            {"name": "c", "type": "categorical", "values": ["a"], "missing_rate": 0.1},
        ],
    }
    dataset = run(raw)
    for name in ("y", "c"):
        assert column(dataset, name).count(None) == pytest.approx(1000, rel=0.15)


def test_skewed_popularity_concentrates_rows():
    def top_share(popularity):
        raw = {
            "seed": 6,
            "rows": {"count": 5000},
            "entities": [{"name": "users", "count": 100, "popularity": popularity}],
            "columns": [{"name": "user_id", "type": "entity", "entity": "users"}],
        }
        counts = Counter(column(run(raw), "user_id"))
        return sum(count for _, count in counts.most_common(10)) / 5000

    assert top_share("uniform") < 0.2
    assert top_share("skewed") > 0.4


def test_row_limit():
    with pytest.raises(GenerationError, match="limit is 100"):
        run({"rows": {"count": 101}, "columns": [{"name": "x", "type": "numeric"}]}, max_rows=100)
