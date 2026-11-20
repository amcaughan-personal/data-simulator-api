"""CSV output: rendering, and deciding whether the client asked for it."""

from __future__ import annotations

import csv
import io
from typing import Any


def wants_csv(accept: str) -> bool:
    """True if the Accept header prefers text/csv over application/json.

    Honours q-values (`application/json, text/csv;q=0.5` means JSON) and wildcards;
    on a tie, or when neither is mentioned, JSON wins.
    """
    preference = {"application/json": 0.0, "text/csv": 0.0}
    for part in accept.split(","):
        media_type, *params = (piece.strip().lower() for piece in part.split(";"))
        quality = 1.0
        for param in params:
            if param.startswith("q="):
                try:
                    quality = float(param[2:])
                except ValueError:
                    quality = 0.0
        for target in preference:
            if media_type in (target, "*/*", target.split("/")[0] + "/*"):
                preference[target] = max(preference[target], quality)
    return preference["text/csv"] > preference["application/json"]


def to_csv(dataset: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=dataset["columns"], lineterminator="\n")
    writer.writeheader()
    # Booleans as true/false to match the JSON output; None becomes an empty field.
    writer.writerows(
        {name: str(value).lower() if isinstance(value, bool) else value for name, value in row.items()}
        for row in dataset["rows"]
    )
    return buffer.getvalue()
