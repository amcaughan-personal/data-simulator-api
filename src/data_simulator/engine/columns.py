"""Generate the values of one column for a group of rows."""

from __future__ import annotations

import numpy as np

from data_simulator.engine.frame import Frame, GenerationError
from data_simulator.spec import ColumnSpec, Dependency

# Seasonal cycles line up with this Monday at 00:00 UTC.
CYCLE_ANCHOR = np.datetime64("2024-01-01T00:00:00", "ms")


def column_values(
    spec: ColumnSpec, rows: np.ndarray, frame: Frame | None, rng: np.random.Generator
) -> np.ndarray:
    """Values for the given row positions.

    `frame` is None when drawing one value per individual (columns with `per`), in which
    case only the distribution, min/max and rounding apply.
    """
    values = _base(spec, rows, rng)
    if not spec.is_numeric:
        return values

    if frame is not None:
        if spec.uses_time:
            values = _add_time_patterns(values, spec, frame.timestamps[rows], frame.time_origin)
        if spec.multiply_by is not None:
            values = values * _dependency(spec.multiply_by, frame, rows, neutral=1.0)
        if spec.add is not None:
            values = values + _dependency(spec.add, frame, rows, neutral=0.0)
        if spec.noise is not None:
            values = _add_noise(values, spec, frame.series[rows], rng)

    if spec.min is not None or spec.max is not None:
        values = np.clip(values, spec.min, spec.max)
    if spec.round is not None:
        values = np.round(values, spec.round)
    return values


def is_integer(spec: ColumnSpec) -> bool:
    if spec.kind in ("bernoulli", "sequence") or spec.round == 0:
        return True
    if spec.noise is not None and spec.noise.poisson:
        return True
    adjusted = (
        spec.uses_time or spec.multiply_by is not None or spec.add is not None or spec.noise is not None
    )
    if spec.kind == "poisson":
        return not adjusted and spec.round is None
    return spec.kind == "constant" and isinstance(spec.constant, int) and not adjusted


def _base(spec: ColumnSpec, rows: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    n = len(rows)
    match spec.kind:
        case "normal":
            return rng.normal(spec.normal.mean, spec.normal.stddev, n)
        case "lognormal":
            return rng.lognormal(np.log(spec.lognormal.median), spec.lognormal.sigma, n)
        case "uniform":
            return rng.uniform(spec.uniform.low, spec.uniform.high, n)
        case "exponential":
            return rng.exponential(spec.exponential.mean, n)
        case "poisson":
            return rng.poisson(spec.poisson.mean, n).astype(float)
        case "sequence":
            return (spec.sequence.start + spec.sequence.step * rows).astype(float)
        case "constant":
            if spec.is_numeric:
                return np.full(n, float(spec.constant))
            return np.full(n, spec.constant, dtype=object)
        case "bernoulli":
            return (rng.random(n) < spec.bernoulli).astype(float)
        case "categorical":
            choices = spec.categorical
            if isinstance(choices, dict):
                weights = np.array(list(choices.values()), dtype=float)
                picked = rng.choice(len(choices), size=n, p=weights / weights.sum())
                return np.array(list(choices), dtype=object)[picked]
            return np.array(choices, dtype=object)[rng.integers(0, len(choices), n)]
    raise GenerationError(f"unsupported column kind {spec.kind!r}")


def _add_time_patterns(
    values: np.ndarray, spec: ColumnSpec, timestamps: np.ndarray, origin: np.datetime64
) -> np.ndarray:
    one_second = np.timedelta64(1, "s")
    if spec.trend is not None:
        periods = (timestamps - origin) / one_second / spec.trend.per.total_seconds()
        if spec.trend.linear is not None:
            values = values + spec.trend.linear * periods
        else:
            values = values * (1 + spec.trend.growth) ** periods

    seconds = (timestamps - CYCLE_ANCHOR) / one_second
    for cycle in spec.seasonality:
        phase = (seconds - cycle.peak.total_seconds()) / cycle.period.total_seconds()
        values = values + cycle.amplitude * np.cos(2 * np.pi * phase)
    return values


def _dependency(dependency: Dependency, frame: Frame, rows: np.ndarray, neutral: float) -> np.ndarray:
    if isinstance(dependency, str):
        source = frame.columns[dependency][rows]
        if source.dtype == object:
            raise GenerationError(
                f"{dependency!r} isn't numeric; use a lookup like {{{dependency!r}: {{...}}}}"
            )
        return np.nan_to_num(source, nan=neutral)

    result = np.full(len(rows), neutral)
    for column, lookup in dependency.items():
        source = frame.columns[column][rows]
        factors = np.array(
            [lookup.get(str(value), neutral) if value is not None else neutral for value in source]
        )
        result = result * factors if neutral == 1.0 else result + factors
    return result


def _add_noise(
    values: np.ndarray, spec: ColumnSpec, series: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    noise = spec.noise
    if noise.normal is not None:
        return values + rng.normal(0.0, noise.normal.stddev, len(values))
    if noise.uniform is not None:
        half = noise.uniform.width / 2
        return values + rng.uniform(-half, half, len(values))
    if noise.random_walk is not None:
        steps = rng.normal(0.0, noise.random_walk.step, len(values))
        walk = np.empty_like(values)
        for one_series in np.unique(series):
            members = np.flatnonzero(series == one_series)
            walk[members] = np.cumsum(steps[members])
        return values + walk
    return rng.poisson(np.clip(values, 0, None)).astype(float)
