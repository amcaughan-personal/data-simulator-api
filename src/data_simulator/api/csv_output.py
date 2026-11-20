"""Render a generated dataset as CSV."""

from __future__ import annotations

import csv
import io
from typing import Any


def to_csv(dataset: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=dataset["columns"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(dataset["rows"])  # None is written as an empty field
    return buffer.getvalue()
