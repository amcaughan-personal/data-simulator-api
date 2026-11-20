"""Runtime settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    max_rows: int
    root_path: str


def load_settings() -> Settings:
    return Settings(
        # Caps response size, and with it compute time and data transfer per request.
        max_rows=int(os.environ.get("DATA_SIMULATOR_MAX_ROWS", "5000")),
        # Path prefix when served behind an API Gateway stage, so /docs links resolve.
        root_path=os.environ.get("DATA_SIMULATOR_ROOT_PATH", ""),
    )
