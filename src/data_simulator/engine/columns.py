"""Generate the values for one column."""

from __future__ import annotations

import numpy as np

from data_simulator.engine.frame import Frame, GenerationError
from data_simulator.spec import (
    CategoricalColumn,
    Column,
    ConstantColumn,
    Distribution,
    Effect,
    Exponential,
    FlagColumn,
    GrowthTrend,
    LinearTrend,
    LogNormal,
    Noise,
    Normal,
    NormalNoise,
    NumericColumn,
    Poisson,
    PoissonNoise,
    RandomWalkNoise,
    SequenceColumn,
    Uniform,
    UniformNoise,
)

# Seasonal cycles line up with this Monday at 00:00 UTC.
CYCLE_ANCHOR = np.datetime64("2024-01-01T00:00:00", "ms")


def generate_column(column: Column, frame: Frame, rng: np.random.Generator) -> np.ndarray:
    """Return one value per row. Numeric columns are floats with NaN for missing values;
    everything else is an object array with None for missing values."""
    match column:
        case NumericColumn():
            values = _numeric(column, frame, rng)
        case CategoricalColumn():
            values = _categorical(column, frame.n, rng)
        case FlagColumn():
            values = _flag(column, frame, rng)
        case SequenceColumn():
            values = (column.start + column.step * np.arange(frame.n)).astype(float)
        case ConstantColumn():
            values = np.full(frame.n, column.value, dtype=object)
        case _:
            raise GenerationError(f"{column.name}: unsupported column type {column.type!r}")

    if _is_integer(column):
        frame.integer_columns.add(column.name)
    return _apply_missing(values, column.missing_rate, rng)


def _numeric(column: NumericColumn, frame: Frame, rng: np.random.Generator) -> np.ndarray:
    if isinstance(column.base, int | float):
        values = np.full(frame.n, float(column.base))
    else:
        values = draw(column.base, frame.n, rng)

    if column.trend is not None or column.seasonality:
        values = _add_time_patterns(values, column, frame)

    for effect in column.effects:
        values = apply_effect(values, effect, frame, column.name)

    if column.noise is not None:
        values = _add_noise(values, column.noise, frame, rng)

    if column.min is not None or column.max is not None:
        values = np.clip(values, column.min, column.max)
    if column.decimals is not None:
        values = np.round(values, column.decimals)
    return values


def _add_time_patterns(values: np.ndarray, column: NumericColumn, frame: Frame) -> np.ndarray:
    one_second = np.timedelta64(1, "s")
    trend = column.trend
    if trend is not None:
        periods = (frame.timestamps - frame.time_origin) / one_second / trend.per.total_seconds()
        if isinstance(trend, LinearTrend):
            values = values + trend.change * periods
        elif isinstance(trend, GrowthTrend):
            values = values * (1 + trend.rate) ** periods

    seconds = (frame.timestamps - CYCLE_ANCHOR) / one_second
    for cycle in column.seasonality:
        phase = (seconds - cycle.peak.total_seconds()) / cycle.period.total_seconds()
        values = values + cycle.amplitude * np.cos(2 * np.pi * phase)
    return values


def draw(distribution: Distribution, n: int, rng: np.random.Generator) -> np.ndarray:
    match distribution:
        case Normal():
            return rng.normal(distribution.mean, distribution.stddev, n)
        case LogNormal():
            return rng.lognormal(np.log(distribution.median), distribution.sigma, n)
        case Uniform():
            return rng.uniform(distribution.low, distribution.high, n)
        case Exponential():
            return rng.exponential(distribution.mean, n)
        case Poisson():
            return rng.poisson(distribution.mean, n).astype(float)
    raise GenerationError(f"unsupported distribution {distribution.dist!r}")


def apply_effect(values: np.ndarray, effect: Effect, frame: Frame, target: str) -> np.ndarray:
    source = frame.columns[effect.field]
    neutral = 1.0 if effect.op == "multiply" else 0.0

    if effect.values is not None:
        lookup = effect.values
        amounts = np.array(
            [lookup.get(str(value), neutral) if value is not None else neutral for value in source]
        )
    else:
        if source.dtype == object:
            raise GenerationError(
                f"{target}: effect on {effect.field!r} needs 'values' because that column isn't numeric"
            )
        amounts = np.nan_to_num(source, nan=neutral)

    return values * amounts if effect.op == "multiply" else values + amounts


def _add_noise(values: np.ndarray, noise: Noise, frame: Frame, rng: np.random.Generator) -> np.ndarray:
    match noise:
        case NormalNoise():
            scale = noise.stddev * np.abs(values) if noise.relative else noise.stddev
            return values + rng.normal(0.0, 1.0, values.shape) * scale
        case UniformNoise():
            return values + rng.uniform(-noise.width / 2, noise.width / 2, values.shape)
        case RandomWalkNoise():
            steps = rng.normal(0.0, noise.step, values.shape)
            walk = np.empty_like(values)
            for series in np.unique(frame.series):
                rows = np.flatnonzero(frame.series == series)
                walk[rows] = np.cumsum(steps[rows])
            return values + walk
        case PoissonNoise():
            return rng.poisson(np.clip(values, 0, None)).astype(float)
    raise GenerationError(f"unsupported noise {noise.kind!r}")


def _categorical(column: CategoricalColumn, n: int, rng: np.random.Generator) -> np.ndarray:
    if isinstance(column.values, dict):
        choices = list(column.values)
        weights = np.array(list(column.values.values()), dtype=float)
        probabilities = weights / weights.sum()
    else:
        choices, probabilities = column.values, None
    picked = rng.choice(len(choices), size=n, p=probabilities)
    return np.array(choices, dtype=object)[picked]


def _flag(column: FlagColumn, frame: Frame, rng: np.random.Generator) -> np.ndarray:
    probability = np.full(frame.n, column.probability)
    for effect in column.effects:
        probability = apply_effect(probability, effect, frame, column.name)
    return (rng.random(frame.n) < np.clip(probability, 0.0, 1.0)).astype(float)


def _is_integer(column: Column) -> bool:
    if isinstance(column, FlagColumn | SequenceColumn):
        return True
    if isinstance(column, NumericColumn):
        if column.decimals == 0 or isinstance(column.noise, PoissonNoise):
            return True
        plain_count = isinstance(column.base, Poisson) and not column.effects and column.noise is None
        return plain_count and column.decimals is None
    return False


def _apply_missing(values: np.ndarray, rate: float, rng: np.random.Generator) -> np.ndarray:
    if rate <= 0:
        return values
    missing = rng.random(values.shape[0]) < rate
    if values.dtype == object:
        values = values.copy()
        values[missing] = None
    else:
        values = np.where(missing, np.nan, values)
    return values
