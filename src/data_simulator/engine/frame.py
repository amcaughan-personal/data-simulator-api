"""The working state while a dataset is generated."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


class GenerationError(ValueError):
    """A spec that validated but can't be generated, e.g. a lookup effect on a numeric column."""


@dataclass
class Frame:
    """Columns being built for `n` rows.

    `series` groups rows that belong to one time series (one per entity for per-entity
    series, a single group otherwise) so noise like random walks accumulates per series.
    """

    n: int
    seed: int
    timestamps: np.ndarray | None = None
    series: np.ndarray | None = None
    entity_rows: dict[str, np.ndarray] = field(default_factory=dict)
    columns: dict[str, np.ndarray] = field(default_factory=dict)
    integer_columns: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.series is None:
            self.series = np.zeros(self.n, dtype=np.int64)
