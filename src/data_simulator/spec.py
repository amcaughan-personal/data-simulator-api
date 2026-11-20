"""The dataset spec: a small JSON document describing what one row is and how each column behaves."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from data_simulator.durations import Duration

Name = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=64)]

DEFAULT_START = datetime(2026, 1, 1, tzinfo=UTC)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)


# --------------------------------------------------------------------------------------
# Distributions: where a numeric value starts before effects and noise
# --------------------------------------------------------------------------------------


class Normal(_Model):
    dist: Literal["normal"]
    mean: float = 0.0
    stddev: float = Field(1.0, gt=0)


class LogNormal(_Model):
    """Right-skewed positive values such as prices or incomes."""

    dist: Literal["lognormal"]
    median: float = Field(1.0, gt=0)
    sigma: float = Field(0.5, gt=0, description="Spread on the log scale; 0.5 is moderately skewed.")


class Uniform(_Model):
    dist: Literal["uniform"]
    low: float = 0.0
    high: float = 1.0

    @model_validator(mode="after")
    def _check_range(self) -> Uniform:
        if self.high <= self.low:
            raise ValueError("uniform: high must be greater than low")
        return self


class Exponential(_Model):
    dist: Literal["exponential"]
    mean: float = Field(1.0, gt=0)


class Poisson(_Model):
    """Non-negative whole-number counts."""

    dist: Literal["poisson"]
    mean: float = Field(1.0, ge=0)


Distribution = Annotated[Normal | LogNormal | Uniform | Exponential | Poisson, Field(discriminator="dist")]


# --------------------------------------------------------------------------------------
# Row shape
# --------------------------------------------------------------------------------------


class RowsSpec(_Model):
    """What one row represents.

    - `{"count": 500}`: 500 independent rows
    - `{"one_per": "users"}`: one row per entity, e.g. a users table
    - `{"count": 1000, "between": ["2026-01-01", "2026-02-01"]}`: events at random times
    - `{"every": "1h", "count": 168}`: a regular time series
    - `{"every": "1h", "count": 168, "one_per": "devices"}`: one time series per entity
    """

    count: int | None = Field(None, ge=1, le=100_000, description="Rows, or time steps when `every` is set.")
    one_per: Name | None = Field(None, description="Entity to emit one row (or one series) per.")
    every: Duration | None = Field(None, description="Interval between time steps, e.g. '15m', '1h', '1d'.")
    start: datetime = Field(DEFAULT_START, description="First timestamp when `every` is set.")
    between: tuple[datetime, datetime] | None = Field(None, description="Random timestamps in this range.")
    timestamp_column: Name = "timestamp"

    @model_validator(mode="after")
    def _check_shape(self) -> RowsSpec:
        if self.every is not None:
            if self.count is None:
                raise ValueError("rows: 'every' needs 'count' (the number of time steps)")
            if self.between is not None:
                raise ValueError("rows: use either 'every' or 'between', not both")
            if self.every.total_seconds() <= 0:
                raise ValueError("rows: 'every' must be positive")
        elif self.between is not None:
            if self.count is None or self.one_per is not None:
                raise ValueError("rows: 'between' needs 'count' and can't be combined with 'one_per'")
            start, end = self.between
            if end <= start:
                raise ValueError("rows: 'between' end must be after start")
        elif self.one_per is not None:
            if self.count is not None:
                raise ValueError(
                    "rows: 'one_per' alone emits one row per entity; drop 'count' or add 'every'"
                )
        elif self.count is None:
            raise ValueError("rows: set 'count', 'one_per', or 'every' + 'count'")

        self.start = _as_utc(self.start)
        if self.between is not None:
            self.between = (_as_utc(self.between[0]), _as_utc(self.between[1]))
        return self

    @property
    def has_timestamps(self) -> bool:
        return self.every is not None or self.between is not None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


# --------------------------------------------------------------------------------------
# Numeric building blocks
# --------------------------------------------------------------------------------------


class Effect(_Model):
    """Make a value depend on an earlier column.

    - By category: `{"field": "plan", "op": "multiply", "values": {"premium": 1.8}}`
      (categories not listed are left unchanged)
    - By a numeric column: `{"field": "device_bias", "op": "multiply"}` multiplies by that
      column's value; `"op": "add"` adds it.
    """

    field: Name
    op: Literal["multiply", "add"] = "multiply"
    values: dict[str, float] | None = None


class LinearTrend(_Model):
    """Add `change` every `per`: `{"kind": "linear", "change": 5, "per": "1d"}`."""

    kind: Literal["linear"]
    change: float
    per: Duration = "1d"


class GrowthTrend(_Model):
    """Grow the base by `rate` every `per`, compounding: 0.02 = 2% per period."""

    kind: Literal["growth"]
    rate: float = Field(..., gt=-1)
    per: Duration = "1d"


Trend = Annotated[LinearTrend | GrowthTrend, Field(discriminator="kind")]


class Cycle(_Model):
    """A repeating up-and-down pattern, e.g. daily traffic peaking at 2pm.

    Cycles line up with Monday 00:00 UTC, so a daily `peak` of '14h' is 2pm and a weekly
    `peak` of '5d' is Saturday.
    """

    period: Duration
    amplitude: float = Field(..., description="How far above (and below) the base the cycle swings.")
    peak: Duration = Field("0s", description="Time into the cycle where it is highest.")


class NormalNoise(_Model):
    kind: Literal["normal"]
    stddev: float = Field(..., gt=0)
    relative: bool = Field(False, description="Treat stddev as a fraction of the value (e.g. 0.05 = 5%).")


class UniformNoise(_Model):
    kind: Literal["uniform"]
    width: float = Field(..., gt=0, description="Total width; values move by up to ±width/2.")


class RandomWalkNoise(_Model):
    """Wandering noise that accumulates over rows (per entity for per-entity series)."""

    kind: Literal["random_walk"]
    step: float = Field(..., gt=0, description="Standard deviation of each step.")


class PoissonNoise(_Model):
    """Turn the value into a whole-number count drawn around it."""

    kind: Literal["poisson"]


Noise = Annotated[NormalNoise | UniformNoise | RandomWalkNoise | PoissonNoise, Field(discriminator="kind")]


# --------------------------------------------------------------------------------------
# Column types
# --------------------------------------------------------------------------------------


class _Column(_Model):
    name: Name
    missing_rate: float = Field(0.0, ge=0, le=1, description="Fraction of values left empty.")


class NumericColumn(_Column):
    """`value = base + trend + seasonality`, then effects, then noise; clipped and rounded."""

    type: Literal["numeric"]
    base: float | Distribution = Field(0.0, description="A constant or a distribution to draw from.")
    trend: Trend | None = Field(None, description="Needs rows with timestamps.")
    seasonality: list[Cycle] = Field(default_factory=list, description="Needs rows with timestamps.")
    effects: list[Effect] = Field(default_factory=list)
    noise: Noise | None = None
    min: float | None = None
    max: float | None = None
    decimals: int | None = Field(None, ge=0, le=10, description="Round to this many decimals; 0 gives ints.")

    @model_validator(mode="after")
    def _check_bounds(self) -> NumericColumn:
        if self.min is not None and self.max is not None and self.max < self.min:
            raise ValueError(f"{self.name}: max must be >= min")
        return self


class CategoricalColumn(_Column):
    """Pick from a list of values, optionally weighted: `{"west": 3, "east": 1}`."""

    type: Literal["categorical"]
    values: list[str] | dict[str, float] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _check_weights(self) -> CategoricalColumn:
        weights = self.values.values() if isinstance(self.values, dict) else [1.0]
        if any(weight < 0 for weight in weights) or sum(weights) <= 0:
            raise ValueError(f"{self.name}: weights must be non-negative and not all zero")
        return self


class FlagColumn(_Column):
    """A 0/1 column that is 1 with the given probability (effects adjust the probability)."""

    type: Literal["flag"]
    probability: float = Field(..., ge=0, le=1)
    effects: list[Effect] = Field(default_factory=list)


class EntityColumn(_Column):
    """The ID of the entity on this row, or one of its attributes."""

    type: Literal["entity"]
    entity: Name
    attribute: Name | None = Field(None, description="Omit for the entity ID.")


class SequenceColumn(_Column):
    type: Literal["sequence"]
    start: int = 1
    step: int = 1


class ConstantColumn(_Column):
    type: Literal["constant"]
    value: str | int | float | bool | None


Column = Annotated[
    NumericColumn | CategoricalColumn | FlagColumn | EntityColumn | SequenceColumn | ConstantColumn,
    Field(discriminator="type"),
]


# --------------------------------------------------------------------------------------
# Entities and the dataset
# --------------------------------------------------------------------------------------


class EntitySpec(_Model):
    """A pool of things rows can refer to: users, institutions, devices, products."""

    name: Name
    count: int = Field(..., ge=1, le=10_000, description="IDs are the name plus a number: device_0001, ...")
    popularity: Literal["uniform", "skewed"] = Field(
        "uniform", description="'skewed' makes a few entities appear in many more rows than the rest."
    )
    attributes: list[Column] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_attributes(self) -> EntitySpec:
        names: list[str] = []
        for attribute in self.attributes:
            if isinstance(attribute, EntityColumn):
                raise ValueError(f"entity {self.name}: attributes can't be entity references")
            if _uses_time(attribute):
                raise ValueError(
                    f"entity {self.name}: attribute {attribute.name} can't use trend or seasonality"
                )
            _check_effect_sources(attribute, names, f"entity {self.name}")
            names.append(attribute.name)
        _check_unique(names, f"entity {self.name} attribute")
        return self


class DatasetSpec(_Model):
    name: Name = "dataset"
    description: str | None = Field(None, max_length=500)
    seed: int | None = Field(None, ge=0, description="Same seed, same data. Omit for a random seed.")
    rows: RowsSpec
    entities: list[EntitySpec] = Field(default_factory=list)
    columns: list[Column] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _check_references(self) -> DatasetSpec:
        entities = {entity.name: entity for entity in self.entities}
        _check_unique([entity.name for entity in self.entities], "entity")

        if self.rows.one_per is not None and self.rows.one_per not in entities:
            raise ValueError(f"rows.one_per: unknown entity {self.rows.one_per!r}")

        names = [self.rows.timestamp_column] if self.rows.has_timestamps else []
        for column in self.columns:
            if isinstance(column, EntityColumn):
                entity = entities.get(column.entity)
                if entity is None:
                    raise ValueError(f"{column.name}: unknown entity {column.entity!r}")
                attributes = {attribute.name for attribute in entity.attributes}
                if column.attribute is not None and column.attribute not in attributes:
                    raise ValueError(f"{column.name}: entity {column.entity!r} has no {column.attribute!r}")
            if _uses_time(column) and not self.rows.has_timestamps:
                raise ValueError(
                    f"{column.name}: trend and seasonality need timestamps; set rows.every or rows.between"
                )
            _check_effect_sources(column, names, "columns")
            names.append(column.name)
        _check_unique(names, "column")
        return self

    @property
    def row_count(self) -> int:
        entity_counts = {entity.name: entity.count for entity in self.entities}
        per_entity = entity_counts[self.rows.one_per] if self.rows.one_per else 1
        steps = self.rows.count if self.rows.count is not None else 1
        return steps * per_entity


def _uses_time(column: Any) -> bool:
    return isinstance(column, NumericColumn) and (column.trend is not None or bool(column.seasonality))


def _check_effect_sources(column: Any, earlier: list[str], where: str) -> None:
    for effect in getattr(column, "effects", []):
        if effect.field not in earlier:
            raise ValueError(
                f"{where}: {column.name} has an effect on {effect.field!r}, which must be an earlier column"
            )


def _check_unique(names: list[str], what: str) -> None:
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ValueError(f"duplicate {what} name {name!r}")
        seen.add(name)
