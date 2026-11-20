from itertools import pairwise

import pytest
from pydantic import ValidationError

from data_simulator import StreamWindowRequest, generate_window
from data_simulator.api.examples import CARD_STREAM, SENSOR_STREAM
from data_simulator.engine import GenerationError


def window(stream: dict, start: str, end: str, max_cells: int | None = None) -> dict:
    request = StreamWindowRequest.model_validate({"stream": stream, "window": {"from": start, "to": end}})
    return generate_window(request.stream, request.window, max_cells=max_cells)


@pytest.mark.parametrize("stream", [CARD_STREAM, SENSOR_STREAM], ids=["rate", "every"])
def test_windows_join_up_into_the_whole(stream):
    whole = window(stream, "2026-03-01T00:00:00Z", "2026-03-03T00:00:00Z")["rows"]
    cuts = ["2026-03-01T00:00:00Z", "2026-03-01T09:17:30Z", "2026-03-02T13:00:00Z", "2026-03-03T00:00:00Z"]
    parts = [row for a, b in pairwise(cuts) for row in window(stream, a, b)["rows"]]
    assert whole and parts == whole


def test_individuals_keep_their_fixed_values_across_windows():
    def limits(rows):
        return {row["id"]: row["credit_limit"] for row in rows}

    march = limits(window(CARD_STREAM, "2026-03-01", "2026-03-02")["rows"])
    june = limits(window(CARD_STREAM, "2026-06-01", "2026-06-02")["rows"])
    shared = march.keys() & june.keys()
    assert shared and all(march[i] == june[i] for i in shared)


def test_rows_follow_the_rate_and_are_numbered_from_the_start():
    day = window(CARD_STREAM, "2026-03-01", "2026-03-02")
    assert 2400 < day["row_count"] < 3360  # about 120 an hour
    ids = [row["transaction_id"] for row in day["rows"]]
    assert ids == list(range(ids[0], ids[0] + len(ids)))
    assert window(CARD_STREAM, "2026-01-01", "2026-01-01T01:00:00Z")["rows"][0]["transaction_id"] == 1


def test_every_individual_reports_at_every_step():
    rows = window(SENSOR_STREAM, "2026-03-01T09:00:00Z", "2026-03-01T10:00:00Z")["rows"]
    assert len(rows) == 4 * 4  # 4 sensors, every 15 minutes
    assert rows[0]["timestamp"] == "2026-03-01T09:00:00Z"
    assert rows[-1]["timestamp"] == "2026-03-01T09:45:00Z"


def test_large_windows_are_refused():
    with pytest.raises(GenerationError, match="shorter window"):
        window(CARD_STREAM, "2026-03-01", "2026-04-01", max_cells=10_000)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"rows": {"count": 10, "rate": 1}}, "Extra inputs"),
        ({"rows": {"rate": 1, "every": "1h"}}, "exactly one of"),
        ({"rows": {"rate": 100, "per": "1s"}}, "rows an hour"),
        ({"seed": None}, "seed"),
        (
            {"common_columns": {"x": {"constant": 1, "noise": {"random_walk": {"step": 1}}}}},
            "random_walk",
        ),
    ],
)
def test_invalid_streams_are_rejected(change, message):
    with pytest.raises(ValidationError, match=message):
        window({**SENSOR_STREAM, **change}, "2026-03-01", "2026-03-02")


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        ("2025-12-31", "2026-01-02", "before the stream's start"),
        ("2026-03-02", "2026-03-01", "after 'from'"),
        ("2036-03-01", "2036-03-02", "within 10 years"),
    ],
)
def test_invalid_windows_are_rejected(start, end, message):
    with pytest.raises(ValidationError, match=message):
        window(SENSOR_STREAM, start, end)
