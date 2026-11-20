"""Lay out rows: which profile and individual each row belongs to, and its timestamp."""

from __future__ import annotations

import numpy as np

from data_simulator.engine.frame import Frame
from data_simulator.rng import rng_for
from data_simulator.spec import DatasetSpec, Profile, _TableSpec


def layout_rows(spec: DatasetSpec, seed: int) -> Frame:
    rows = spec.rows
    profiles = list(spec.profiles.items())
    frame = Frame(n=spec.row_count, seed=seed, profile_names=[name for name, _ in profiles])

    if spec.has_ids:
        frame.ids, frame.individual_profile = create_individuals(spec)

    step = np.arange(frame.n)
    if rows.one_each:
        # Every individual gets a row (or a row at every time step, ordered by time).
        individual_count = len(frame.ids)
        frame.individual = np.arange(frame.n) % individual_count
        step = np.arange(frame.n) // individual_count
    else:
        pick_owners(spec, frame)
    set_series(frame)

    if rows.every is not None:
        frame.time_origin = datetime64(rows.start)
        frame.timestamps = frame.time_origin + step * np.timedelta64(
            int(rows.every.total_seconds() * 1000), "ms"
        )
    elif rows.between is not None:
        start, end = rows.between
        span_ms = (end - start).total_seconds() * 1000
        offsets = np.sort(rng_for(seed, "rows", "timestamps").uniform(0, span_ms, frame.n)).astype(np.int64)
        frame.time_origin = datetime64(start)
        frame.timestamps = frame.time_origin + offsets.astype("timedelta64[ms]")
    return frame


def create_individuals(spec: _TableSpec) -> tuple[np.ndarray, np.ndarray]:
    """Every individual's ID, and the index of the profile it belongs to."""
    ids, owners = [], []
    for index, (name, profile) in enumerate(spec.profiles.items()):
        width = max(4, len(str(profile.count)))
        ids.extend(f"{name}_{number:0{width}d}" for number in range(1, profile.count + 1))
        owners.extend([index] * profile.count)
    return np.array(ids, dtype=object), np.array(owners)


def pick_owners(spec: _TableSpec, frame: Frame) -> None:
    """Choose each row's profile and (if profiles have a count) individual at random."""
    profiles = list(spec.profiles.items())
    if profiles:
        frame.profile = _pick_profiles(spec, frame.n, frame.seed)
        if spec.has_ids:
            frame.individual = _pick_individuals(frame, profiles, frame.seed)


def set_series(frame: Frame) -> None:
    if frame.individual is not None:
        frame.profile = frame.individual_profile[frame.individual]
        frame.series = frame.individual
    else:
        frame.series = np.zeros(frame.n, dtype=np.int64)


def _pick_profiles(spec: _TableSpec, n: int, seed: int) -> np.ndarray:
    names = list(spec.profiles)
    if spec.rows.from_ is None:
        weights = np.ones(len(names))
    else:
        weights = np.array([spec.rows.from_[name] for name in names], dtype=float)
    return rng_for(seed, "rows", "profiles").choice(len(names), size=n, p=weights / weights.sum())


def _pick_individuals(frame: Frame, profiles: list[tuple[str, Profile]], seed: int) -> np.ndarray:
    individual = np.empty(frame.n, dtype=np.int64)
    first = 0
    for index, (name, profile) in enumerate(profiles):
        rows = np.flatnonzero(frame.profile == index)
        rng = rng_for(seed, "rows", "individuals", name)
        if profile.popularity == "skewed":
            # A few individuals account for most rows; shuffled so they aren't just the lowest IDs.
            weights = 1.0 / np.arange(1, profile.count + 1)
            rng.shuffle(weights)
            picks = rng.choice(profile.count, size=len(rows), p=weights / weights.sum())
        else:
            picks = rng.integers(0, profile.count, size=len(rows))
        individual[rows] = first + picks
        first += profile.count
    return individual


def datetime64(value) -> np.datetime64:
    return np.datetime64(value.replace(tzinfo=None), "ms")
