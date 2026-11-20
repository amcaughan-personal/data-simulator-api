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
    extra = {**TRANSACTIONS, "common_columns": {**TRANSACTIONS["common_columns"], "x": {"bernoulli": 0.5}}}
    assert column(run(extra), "amount") == column(run(TRANSACTIONS), "amount")


def test_profiles_set_frequency_and_their_own_distributions():
    raw = {
        "seed": 1,
        "rows": {"count": 10000, "from": {"standard": 0.8, "premium": 0.2}},
        "profiles": {
            "standard": {"columns": {"amount": {"lognormal": {"median": 35, "sigma": 0.5}}}},
            "premium": {"columns": {"amount": {"lognormal": {"median": 60, "sigma": 0.5}}}},
        },
    }
    rows = run(raw)["rows"]
    assert Counter(r["profile"] for r in rows)["premium"] == pytest.approx(2000, rel=0.1)
    for profile, median in [("standard", 35), ("premium", 60)]:
        amounts = [r["amount"] for r in rows if r["profile"] == profile]
        assert np.median(amounts) == pytest.approx(median, rel=0.05)


def test_individuals_keep_their_profile_and_per_values():
    rows = run(TRANSACTIONS)["rows"]
    assert all(r["card_id"].startswith(r["card_type"]) for r in rows)

    offsets = {(r["id"], r["calibration_offset"]) for r in run(SENSOR_FLEET)["rows"]}
    assert len(offsets) == 5  # one fixed offset per sensor


def test_one_row_per_individual():
    ids = column(run(INSTITUTIONS), "id")
    assert len(ids) == len(set(ids)) == 25
    assert ids[:2] == ["bank_0001", "bank_0002"]


def test_time_series_per_individual():
    rows = run(SENSOR_FLEET)["rows"]
    assert len(rows) == 24 * 5
    assert [(r["timestamp"], r["id"]) for r in rows[:2]] == [
        ("2026-01-01T00:00:00Z", "indoor_0001"),
        ("2026-01-01T00:00:00Z", "indoor_0002"),
    ]
    assert rows[-1]["timestamp"] == "2026-01-01T23:00:00Z"


def test_events_at_random_times_are_sorted_within_range():
    timestamps = column(run(TRANSACTIONS), "timestamp")
    assert timestamps == sorted(timestamps)
    assert timestamps[0] >= "2026-03-01" and timestamps[-1] < "2026-03-08"


def test_trend_and_seasonality():
    raw = {
        "rows": {"every": "1h", "count": 48},
        "common_columns": {
            "linear": {"constant": 100, "trend": {"linear": 10}},
            "growth": {"constant": 100, "trend": {"growth": 0.1}},
            "daily": {"constant": 100, "seasonality": [{"period": "1d", "amplitude": 20, "peak": "14h"}]},
        },
    }
    rows = run(raw)["rows"]
    assert rows[24]["linear"] == pytest.approx(110)  # one day in
    assert rows[24]["growth"] == pytest.approx(110)
    peak = max(rows[:24], key=lambda r: r["daily"])
    assert peak["timestamp"] == "2026-01-01T14:00:00Z" and peak["daily"] == pytest.approx(120)


def test_columns_can_depend_on_earlier_columns():
    raw = {
        "rows": {"count": 200},
        "common_columns": {
            "tier": {"categorical": ["standard", "premium"]},
            "x": {"sequence": {}},
            "by_tier": {"constant": 100, "multiply_column": {"tier": {"premium": 2}}},
            "plus_x": {"constant": 10, "add_column": "x"},
        },
    }
    dataset = run(raw)
    assert {(r["tier"], r["by_tier"]) for r in dataset["rows"]} == {("standard", 100), ("premium", 200)}
    assert column(dataset, "plus_x")[:3] == [11, 12, 13]


@pytest.mark.parametrize(
    ("noise", "check"),
    [
        ({"normal": {"stddev": 5}}, lambda v: v.std() == pytest.approx(5, rel=0.1)),
        ({"uniform": {"width": 4}}, lambda v: np.ptp(v) <= 4),
        ({"poisson": True}, lambda v: np.all(v == np.round(v)) and v.mean() == pytest.approx(100, rel=0.05)),
    ],
)
def test_noise(noise, check):
    raw = {"seed": 2, "rows": {"count": 5000}, "common_columns": {"y": {"constant": 100, "noise": noise}}}
    assert check(np.array(column(run(raw), "y")))


def test_anomalies_change_values_and_are_labelled():
    raw = {
        "seed": 4,
        "rows": {"every": "1h", "count": 2000},
        "common_columns": {
            "y": {
                "constant": 10,
                "anomalies": [
                    {"name": "spike", "multiply": 3, "chance": 0.05},
                    {
                        "name": "outage",
                        "set": None,
                        "between": ["2026-01-02T00:00:00Z", "2026-01-02T06:00:00Z"],
                    },
                ],
            }
        },
    }
    rows = run(raw)["rows"]
    spikes = [r for r in rows if r["anomaly"] == "spike"]
    assert len(spikes) == pytest.approx(100, rel=0.3) and all(r["y"] == 30 for r in spikes)

    outage = [r for r in rows if "outage" in (r["anomaly"] or "")]
    assert [r["timestamp"][11:13] for r in outage] == ["00", "01", "02", "03", "04", "05"]
    assert all(r["y"] is None for r in outage)

    assert all(r["y"] == 10 for r in rows if r["anomaly"] is None)


def test_missing_and_null_columns():
    raw = {
        "seed": 8,
        "rows": {"count": 10000},
        "profiles": {
            "a": {"columns": {"y": {"normal": {}, "missing": 0.1}}},
            "b": {"columns": {"y": None}},
        },
    }
    rows = run(raw)["rows"]
    a_values = [r["y"] for r in rows if r["profile"] == "a"]
    assert a_values.count(None) == pytest.approx(len(a_values) * 0.1, rel=0.2)
    assert all(r["y"] is None for r in rows if r["profile"] == "b")


def test_skewed_popularity_concentrates_rows():
    def top_ten_share(popularity: str) -> float:
        raw = {
            "seed": 6,
            "rows": {"count": 5000},
            "profiles": {"user": {"count": 100, "popularity": popularity, "columns": {"x": {"normal": {}}}}},
        }
        return sum(n for _, n in Counter(column(run(raw), "id")).most_common(10)) / 5000

    assert top_ten_share("uniform") < 0.2 < 0.4 < top_ten_share("skewed")
