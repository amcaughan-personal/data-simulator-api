import pytest
from pydantic import ValidationError

from data_simulator.spec import DatasetSpec

X = {"x": {"normal": {}}}


def two_profiles(**profile_overrides):
    return {
        "a": {"count": 3, "columns": X, **profile_overrides},
        "b": {"count": 2, "columns": X, **profile_overrides},
    }


def spec(**overrides):
    return DatasetSpec.model_validate({"rows": {"count": 10}, "common_columns": X, **overrides})


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ({"count": 7}, 7),
        ({"count": 50, "between": ["2026-01-01", "2026-01-02"]}, 50),
        ({"every": "1h", "count": 24}, 24),
        ({"one_each": True}, 5),
        ({"every": "1d", "count": 3, "one_each": True}, 15),
    ],
)
def test_row_shapes(rows, expected):
    raw = {"rows": rows, "profiles": two_profiles()}
    assert DatasetSpec.model_validate(raw).row_count == expected


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (
            {
                "rows": {"count": 5},
                "profiles": {"a": {"columns": X}, "b": {"columns": {"y": {"normal": {}}}}},
            },
            "must declare the same columns",
        ),
        (
            {"rows": {"one_each": True}, "profiles": {"a": {"columns": X}}},
            "needs every profile to have a count",
        ),
        (
            {"rows": {"count": 5}, "common_columns": {"x": {"normal": {}, "trend": {"linear": 1}}}},
            "need timestamps",
        ),
        ({"rows": {"count": 5}, "common_columns": {"x": {"normal": {}, "poisson": {}}}}, "exactly one of"),
        (
            {"rows": {"count": 5}, "common_columns": {"x": {"categorical": {"a": 6, "b": 4}}}},
            "add up to 1",
        ),
        (
            {
                "rows": {"count": 5},
                "common_columns": {"y": {"normal": {}, "add_column": "x"}, "x": {"normal": {}}},
            },
            "must be an earlier column",
        ),
        (
            {"rows": {"count": 5}, "common_columns": {"x": {"normal": {}, "add_column": "x"}}},
            "earlier column",
        ),
        (
            {"rows": {"count": 5}, "common_columns": {f"c{i}": {"normal": {}} for i in range(101)}},
            "limit is 100",
        ),
        ({"rows": {"count": 5}, "common_columns": {"x": {"constant": "x" * 101}}}, "at most 100 characters"),
        (
            {
                "rows": {"count": 5},
                "common_columns": {"x": {"normal": {}, "anomalies": [{"name": "a", "add": 1}]}},
            },
            "set 'chance', 'between', or both",
        ),
    ],
)
def test_invalid_specs_explain_the_problem(raw, message):
    with pytest.raises(ValidationError, match=message):
        DatasetSpec.model_validate(raw)


def test_null_column_satisfies_same_columns_rule():
    profiles = {"a": {"columns": {"x": {"normal": {}}}}, "b": {"columns": {"x": None}}}
    assert spec(common_columns={}, profiles=profiles).column_order == ["x"]
