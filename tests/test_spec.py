import pytest
from pydantic import ValidationError

from data_simulator.durations import format_duration, parse_duration
from data_simulator.spec import DatasetSpec


def spec(**overrides):
    base = {"rows": {"count": 10}, "columns": [{"name": "x", "type": "numeric", "base": 1}]}
    return DatasetSpec.model_validate({**base, **overrides})


def test_durations_round_trip():
    for text in ["30s", "15m", "1h", "36h", "1d", "2w"]:
        assert format_duration(parse_duration(text)) == text.replace("36h", "36h")
    assert parse_duration("1.5h").total_seconds() == 5400


@pytest.mark.parametrize("bad", ["1", "h", "5 hours", "-1h", ""])
def test_bad_durations_rejected(bad):
    with pytest.raises(ValueError):
        parse_duration(bad)


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ({"count": 7}, 7),
        ({"every": "1h", "count": 24}, 24),
        ({"count": 50, "between": ["2026-01-01", "2026-01-02"]}, 50),
        ({"one_per": "users"}, 12),
        ({"every": "1d", "count": 3, "one_per": "users"}, 36),
    ],
)
def test_row_shapes_and_counts(rows, expected):
    parsed = spec(rows=rows, entities=[{"name": "users", "count": 12}])
    assert parsed.row_count == expected


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ({}, "set 'count'"),
        ({"every": "1h"}, "needs 'count'"),
        ({"every": "1h", "count": 2, "between": ["2026-01-01", "2026-01-02"]}, "either 'every' or 'between'"),
        ({"count": 5, "between": ["2026-01-02", "2026-01-01"]}, "end must be after start"),
        ({"one_per": "users", "count": 5}, "drop 'count'"),
    ],
)
def test_invalid_row_shapes(rows, message):
    with pytest.raises(ValidationError, match=message):
        spec(rows=rows, entities=[{"name": "users", "count": 3}])


def test_unknown_entity_references_rejected():
    with pytest.raises(ValidationError, match="unknown entity 'users'"):
        spec(rows={"one_per": "users"})
    with pytest.raises(ValidationError, match="unknown entity 'cards'"):
        spec(columns=[{"name": "card_id", "type": "entity", "entity": "cards"}])


def test_unknown_entity_attribute_rejected():
    with pytest.raises(ValidationError, match="has no 'tier'"):
        spec(
            entities=[{"name": "cards", "count": 3}],
            columns=[{"name": "t", "type": "entity", "entity": "cards", "attribute": "tier"}],
        )


def test_effects_must_reference_earlier_columns():
    columns = [
        {"name": "amount", "type": "numeric", "base": 1, "effects": [{"field": "tier", "values": {"a": 2}}]},
        {"name": "tier", "type": "categorical", "values": ["a", "b"]},
    ]
    with pytest.raises(ValidationError, match="must be an earlier column"):
        spec(columns=columns)


def test_duplicate_column_names_rejected():
    columns = [{"name": "x", "type": "numeric"}, {"name": "x", "type": "flag", "probability": 0.5}]
    with pytest.raises(ValidationError, match="duplicate column name 'x'"):
        spec(columns=columns)


def test_column_cannot_reuse_timestamp_name():
    with pytest.raises(ValidationError, match="duplicate column name 'timestamp'"):
        spec(
            rows={"every": "1h", "count": 3}, columns=[{"name": "timestamp", "type": "constant", "value": 1}]
        )


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        spec(columns=[{"name": "x", "type": "numeric", "bse": 1}])
