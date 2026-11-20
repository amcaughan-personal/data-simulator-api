"""The working state while a dataset is generated."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


class GenerationError(ValueError):
    """A spec that validated but can't be generated, e.g. a lookup on a numeric column."""


@dataclass
class Frame:
    """Everything known about the `n` rows being built.

    - `profile`: index into the spec's profiles for each row (if there are profiles)
    - `individual`: index into `ids` for each row (if profiles have a count)
    - `series`: rows sharing a value form one time series (one per individual, else one)
    """

    n: int
    seed: int
    profile_names: list[str] = field(default_factory=list)
    profile: np.ndarray | None = None
    ids: np.ndarray | None = None
    individual_profile: np.ndarray | None = None
    individual: np.ndarray | None = None
    timestamps: np.ndarray | None = None
    time_origin: np.datetime64 | None = None
    series: np.ndarray | None = None
    columns: dict[str, np.ndarray] = field(default_factory=dict)
    integer_columns: set[str] = field(default_factory=set)
