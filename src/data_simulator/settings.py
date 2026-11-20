"""Runtime settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    max_cells: int
    root_path: str


def load_settings() -> Settings:
    return Settings(
        # Rows x columns per response. 100,000 cells is roughly 3 MB of JSON, well under
        # Lambda's 6 MB response limit; it also bounds compute and data transfer per request.
        max_cells=int(os.environ.get("DATA_SIMULATOR_MAX_CELLS", "100000")),
        # Path prefix when served behind an API Gateway stage, so /docs links resolve.
        root_path=os.environ.get("DATA_SIMULATOR_ROOT_PATH", ""),
    )
