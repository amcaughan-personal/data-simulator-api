"""Turn generated columns into JSON-ready rows."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from data_simulator.engine.frame import Frame


def to_rows(frame: Frame, column_names: list[str]) -> list[dict[str, Any]]:
    converted = [_to_python(frame.columns[name], name in frame.integer_columns) for name in column_names]
    return [dict(zip(column_names, values, strict=True)) for values in zip(*converted, strict=True)]


def _to_python(values: np.ndarray, integer: bool) -> list[Any]:
    if np.issubdtype(values.dtype, np.datetime64):
        return [np.datetime_as_string(value, unit="s") + "Z" for value in values]
    if values.dtype == object:
        return [_scalar(value) for value in values]

    floats = values.tolist()
    if integer:
        return [None if math.isnan(value) else int(round(value)) for value in floats]
    return [None if math.isnan(value) else value for value in floats]


def _scalar(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value
