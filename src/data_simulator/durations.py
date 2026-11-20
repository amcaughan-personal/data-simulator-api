"""Compact duration strings such as "15m", "1h", "7d"."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer

_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhdw])\s*$")


def parse_duration(value: object) -> timedelta:
    if isinstance(value, timedelta):
        return value
    if not isinstance(value, str):
        raise ValueError("duration must be a string like '30s', '15m', '1h', '7d' or '2w'")

    match = _PATTERN.match(value)
    if not match:
        raise ValueError(f"invalid duration {value!r}; use a number and a unit, e.g. '15m', '1h', '7d'")

    amount, unit = match.groups()
    return timedelta(seconds=float(amount) * _UNIT_SECONDS[unit])


def format_duration(value: timedelta) -> str:
    seconds = value.total_seconds()
    for unit in ("w", "d", "h", "m"):
        size = _UNIT_SECONDS[unit]
        if seconds and seconds % size == 0:
            return f"{int(seconds // size)}{unit}"
    return f"{seconds:g}s"


Duration = Annotated[
    timedelta,
    BeforeValidator(parse_duration),
    PlainSerializer(format_duration, return_type=str),
]
