import pytest
from pydantic import ValidationError

from data_simulator.spec import DatasetSpec


def spec(**overrides):
    base = {
        "rows": {"count": 10},
        "entities": [{"name": "user", "count": 12}],
        "columns": [{"name": "x", "type": "numeric"}],
    }
    return DatasetSpec.model_validate({**base, **overrides})


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ({"count": 7}, 7),
        ({"one_per": "user"}, 12),
        ({"count": 50, "between": ["2026-01-01", "2026-01-02"]}, 50),
        ({"every": "1h", "count": 24}, 24),
        ({"every": "1d", "count": 3, "one_per": "user"}, 36),
    ],
)
def test_row_shapes(rows, expected):
    assert spec(rows=rows).row_count == expected


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"rows": {"every": "1h"}}, "needs 'count'"),
        ({"rows": {"one_per": "bank"}}, "unknown entity 'bank'"),
        (
            {"columns": [{"name": "y", "type": "numeric", "trend": {"kind": "linear", "change": 1}}]},
            "need timestamps",
        ),
        (
            {
                "columns": [
                    {"name": "y", "type": "numeric", "effects": [{"field": "z", "values": {"a": 2}}]},
                    {"name": "z", "type": "categorical", "values": ["a"]},
                ]
            },
            "must be an earlier column",
        ),
    ],
)
def test_invalid_specs_explain_the_problem(overrides, message):
    with pytest.raises(ValidationError, match=message):
        spec(**overrides)
