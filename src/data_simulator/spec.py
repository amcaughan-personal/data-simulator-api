"""The dataset and stream specs.

A dataset is made of rows. Rows can come from one or more *profiles* (kinds of things,
e.g. standard and premium cards), each describing its own columns with distributions.
`common_columns` apply to every row regardless of profile.

A stream uses the same profiles and columns, but its rows never end: callers fetch any
time window of it, and every window is consistent with every other.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from data_simulator.durations import Duration

Name = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=64)]
Text = Annotated[str, Field(max_length=100)]

# Size limits. With the cell limit applied at request time, these keep every response small.
MAX_COLUMNS = 100
MAX_PROFILES = 50
MAX_INDIVIDUALS = 50_000
MAX_CATEGORIES = 1_000

DEFAULT_START = datetime(2026, 1, 1, tzinfo=UTC)

# Streams: at most 60,000 rows an hour, and windows within 10 years of the stream's start.
MAX_STREAM_ROWS_PER_HOUR = 60_000
MAX_STREAM_SPAN = timedelta(days=3653)


class _Model(BaseModel):
    # allow_inf_nan=False: Python's JSON parser accepts NaN and Infinity; reject them.
    model_config = ConfigDict(
        extra="forbid", validate_default=True, populate_by_name=True, allow_inf_nan=False
    )


def _exactly_one(model: BaseModel, keys: tuple[str, ...], what: str) -> str:
    present = [key for key in keys if key in model.model_fields_set]
    if len(present) != 1:
        found = ", ".join(present) or "none"
        raise ValueError(f"{what} needs exactly one of: {', '.join(keys)} (found: {found})")
    return present[0]


def _check_probabilities(probabilities: dict[str, float], what: str) -> None:
    if any(p < 0 for p in probabilities.values()) or abs(sum(probabilities.values()) - 1) > 1e-6:
        total = round(sum(probabilities.values()), 6)
        raise ValueError(f"{what} must be non-negative and add up to 1 (they add up to {total})")


# --------------------------------------------------------------------------------------
# Distribution parameters
# --------------------------------------------------------------------------------------


class NormalParams(_Model):
    mean: float = 0.0
    stddev: float = Field(1.0, gt=0)


class LogNormalParams(_Model):
    """Right-skewed positive values, like prices or salaries."""

    median: float = Field(1.0, gt=0)
    sigma: float = Field(0.5, gt=0, description="Spread on the log scale; 0.5 is moderately skewed.")


class UniformParams(_Model):
    low: float = 0.0
    high: float = 1.0

    @model_validator(mode="after")
    def _check_range(self) -> UniformParams:
        if self.high <= self.low:
            raise ValueError("uniform: high must be greater than low")
        return self


class MeanParams(_Model):
    mean: float = Field(1.0, ge=0)


class SequenceParams(_Model):
    start: int = 1
    step: int = 1


# --------------------------------------------------------------------------------------
# Time patterns and noise
# --------------------------------------------------------------------------------------


class Trend(_Model):
    """`{"linear": 5, "per": "1d"}` adds 5 per day; `{"growth": 0.01, "per": "1d"}` grows 1% a day."""

    linear: float | None = None
    growth: float | None = Field(None, gt=-1)
    per: Duration = "1d"

    @model_validator(mode="after")
    def _check_kind(self) -> Trend:
        _exactly_one(self, ("linear", "growth"), "trend")
        return self


class Cycle(_Model):
    """A repeating up-and-down pattern, e.g. daily traffic peaking at 2pm.

    Cycles line up with Monday 00:00 UTC, so a daily `peak` of '14h' is 2pm and a weekly
    `peak` of '5d' is Saturday.
    """

    period: Duration
    amplitude: float = Field(..., description="How far above (and below) the value the cycle swings.")
    peak: Duration = Field("0s", description="Time into the cycle where it is highest.")


class NormalNoise(_Model):
    stddev: float = Field(..., gt=0)


class UniformNoise(_Model):
    width: float = Field(..., gt=0, description="Values move by up to ±width/2.")


class RandomWalkNoise(_Model):
    step: float = Field(..., gt=0, description="Standard deviation of each step.")


class Noise(_Model):
    """Exactly one of: `{"normal": {"stddev": 5}}`, `{"uniform": {"width": 4}}`,
    `{"random_walk": {"step": 0.2}}` (wanders over time), `{"poisson": true}` (whole-number counts)."""

    normal: NormalNoise | None = None
    uniform: UniformNoise | None = None
    random_walk: RandomWalkNoise | None = None
    poisson: Literal[True] | None = None

    @model_validator(mode="after")
    def _check_kind(self) -> Noise:
        _exactly_one(self, ("normal", "uniform", "random_walk", "poisson"), "noise")
        return self


class Anomaly(_Model):
    """Something unusual on some rows, recorded in the anomaly column.

    `{"name": "spike", "multiply": 3, "chance": 0.01}` triples 1% of values;
    `{"name": "outage", "set": null, "between": ["2026-01-01T10:00:00Z", "2026-01-01T12:00:00Z"]}`
    empties every value in that window.
    """

    name: Name
    multiply: float | None = None
    add: float | None = None
    set: Text | int | float | bool | None = Field(None, description="Replace the value; null empties it.")
    chance: float | None = Field(None, ge=0, le=1, description="Chance that each row is affected.")
    between: tuple[datetime, datetime] | None = Field(None, description="Only rows in this time window.")

    @model_validator(mode="after")
    def _check(self) -> Anomaly:
        _exactly_one(self, ("multiply", "add", "set"), f"anomaly {self.name}")
        if self.chance is None and self.between is None:
            raise ValueError(f"anomaly {self.name}: set 'chance', 'between', or both")
        if self.between is not None:
            start, end = (_as_utc(value) for value in self.between)
            if end <= start:
                raise ValueError(f"anomaly {self.name}: 'between' end must be after start")
            self.between = (start, end)
        return self


# An earlier numeric column (`"offset"`) or a category lookup (`{"tier": {"premium": 1.8}}`).
Dependency = Name | dict[Name, dict[str, float]]


# --------------------------------------------------------------------------------------
# Columns
# --------------------------------------------------------------------------------------

NUMERIC_KINDS = ("normal", "lognormal", "uniform", "exponential", "poisson", "constant", "sequence")
OTHER_KINDS = ("categorical", "bernoulli")
COLUMN_KINDS = NUMERIC_KINDS + OTHER_KINDS


class ColumnSpec(_Model):
    """One column. Its main key says what the values are; the rest adjusts them.

    `{"lognormal": {"median": 35, "sigma": 0.8}, "round": 2}`
    """

    # What the values are: exactly one of these.
    normal: NormalParams | None = None
    lognormal: LogNormalParams | None = None
    uniform: UniformParams | None = None
    exponential: MeanParams | None = None
    poisson: MeanParams | None = None
    constant: Text | int | float | bool | None = None
    sequence: SequenceParams | None = None
    categorical: (
        Annotated[list[Text], Field(max_length=MAX_CATEGORIES)]
        | Annotated[dict[Text, float], Field(max_length=MAX_CATEGORIES)]
        | None
    ) = Field(
        None,
        description="A list (equally likely) or probabilities adding up to 1: {'west': 0.75, 'east': 0.25}.",
    )
    bernoulli: float | None = Field(None, ge=0, le=1, description="Chance of a 1 (otherwise 0).")

    # Adjustments.
    per: Name | None = Field(None, description="Fix the value per individual, e.g. 'id'.")
    trend: Trend | None = Field(None, description="Needs rows with timestamps.")
    seasonality: list[Cycle] = Field(
        default_factory=list, max_length=10, description="Needs rows with timestamps."
    )
    multiply_column: Dependency | None = Field(
        None, description="An earlier numeric column, or a category lookup."
    )
    add_column: Dependency | None = Field(
        None, description="An earlier numeric column, or a category lookup."
    )
    noise: Noise | None = None
    min: float | None = None
    max: float | None = None
    round: int | None = Field(None, ge=0, le=10, description="Decimal places; 0 gives whole numbers.")
    missing: float = Field(0.0, ge=0, le=1, description="Fraction of values left empty.")
    anomalies: list[Anomaly] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _check(self) -> ColumnSpec:
        kind = _exactly_one(self, COLUMN_KINDS, "a column")
        numeric_only = ("trend", "multiply_column", "add_column", "noise", "min", "max", "round")
        if kind in OTHER_KINDS or (kind == "constant" and not _is_number(self.constant)):
            used = [key for key in numeric_only if key in self.model_fields_set]
            if self.seasonality:
                used.append("seasonality")
            if used:
                raise ValueError(f"{', '.join(used)} only apply to numeric columns, not {kind}")
        if self.per is not None and (
            {"trend", "multiply_column", "add_column", "noise"} & self.model_fields_set
        ):
            raise ValueError(
                "a column fixed with 'per' can't also use trend, multiply_column, add_column or noise"
            )
        if self.min is not None and self.max is not None and self.max < self.min:
            raise ValueError("max must be >= min")
        if isinstance(self.categorical, dict):
            _check_probabilities(self.categorical, "categorical probabilities")
        for anomaly in self.anomalies:
            if not self.is_numeric and (anomaly.multiply is not None or anomaly.add is not None):
                raise ValueError(f"anomaly {anomaly.name}: multiply and add only apply to numeric columns")
            if self.is_numeric and anomaly.set is not None and not _is_number(anomaly.set):
                raise ValueError(
                    f"anomaly {anomaly.name}: a numeric column can only be set to a number or null"
                )
        return self

    @property
    def kind(self) -> str:
        return next(key for key in COLUMN_KINDS if key in self.model_fields_set)

    @property
    def is_numeric(self) -> bool:
        """True when values are numbers (Bernoulli gives 0/1); categorical and text constants aren't."""
        if self.kind == "constant":
            return _is_number(self.constant)
        return self.kind != "categorical"

    @property
    def uses_time(self) -> bool:
        return self.trend is not None or bool(self.seasonality)

    @property
    def dependencies(self) -> list[str]:
        refs: list[str] = []
        for dependency in (self.multiply_column, self.add_column):
            if isinstance(dependency, str):
                refs.append(dependency)
            elif isinstance(dependency, dict):
                refs.extend(dependency)
        return refs


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


# --------------------------------------------------------------------------------------
# Profiles and rows
# --------------------------------------------------------------------------------------


class Profile(_Model):
    """One kind of thing. With `count`, it is a pool of individuals that get IDs."""

    count: int | None = Field(None, ge=1, le=10_000, description="Number of individuals; gives rows an ID.")
    popularity: Literal["uniform", "skewed"] = Field(
        "uniform", description="'skewed' makes a few individuals appear in far more rows than the rest."
    )
    columns: dict[Name, ColumnSpec | None] = Field(
        ..., description="Same column names in every profile; null means always empty for this profile."
    )


class RowsSpec(_Model):
    """What the rows are.

    - `{"count": 500}`: 500 rows
    - `{"count": 1000, "between": ["2026-01-01", "2026-02-01"]}`: rows at random times
    - `{"every": "1h", "count": 168}`: a regular time series
    - `{"one_each": true}`: one row per individual (profiles need a count)
    - `{"every": "1h", "count": 24, "one_each": true}`: a time series per individual
    """

    count: int | None = Field(None, ge=1, le=100_000, description="Rows, or time steps when `every` is set.")
    every: Duration | None = Field(None, description="Interval between time steps, e.g. '15m', '1h', '1d'.")
    start: datetime = Field(DEFAULT_START, description="First timestamp when `every` is set.")
    between: tuple[datetime, datetime] | None = Field(None, description="Random timestamps in this range.")
    one_each: bool = Field(False, description="One row (or one series) per individual.")
    from_: dict[Name, float] | None = Field(
        None,
        alias="from",
        description="Share of rows from each profile, adding up to 1: {'standard': 0.8, 'premium': 0.2}.",
    )
    timestamp_column: Name = "timestamp"

    @model_validator(mode="after")
    def _check_shape(self) -> RowsSpec:
        if self.every is not None and self.between is not None:
            raise ValueError("rows: use either 'every' or 'between', not both")
        if self.every is not None and self.count is None:
            raise ValueError("rows: 'every' needs 'count' (the number of time steps)")
        if self.one_each:
            if self.between is not None or self.from_ is not None:
                raise ValueError("rows: 'one_each' can't be combined with 'between' or 'from'")
            if self.count is not None and self.every is None:
                raise ValueError("rows: 'one_each' gives one row per individual; drop 'count' or add 'every'")
        elif self.count is None:
            raise ValueError("rows: set 'count' (or 'one_each': true)")
        if self.between is not None and self.between[1] <= self.between[0]:
            raise ValueError("rows: 'between' end must be after start")
        if self.from_ is not None:
            _check_probabilities(self.from_, "rows: 'from' shares")

        self.start = _as_utc(self.start)
        if self.between is not None:
            self.between = (_as_utc(self.between[0]), _as_utc(self.between[1]))
        return self

    @property
    def has_timestamps(self) -> bool:
        return self.every is not None or self.between is not None


class StreamRows(_Model):
    """What the stream's rows are.

    - `{"rate": 120, "per": "1h"}`: events at random times, about 120 an hour
    - `{"every": "1h"}`: a regular time series
    - `{"every": "1h", "one_each": true}`: a time series per individual
    """

    rate: float | None = Field(None, gt=0, description="Average number of rows per `per`, at random times.")
    per: Duration = "1h"
    every: Duration | None = Field(None, description="Interval between time steps, e.g. '15m', '1h', '1d'.")
    one_each: bool = Field(False, description="One series per individual (with `every`).")
    from_: dict[Name, float] | None = Field(
        None,
        alias="from",
        description="Share of rows from each profile, adding up to 1: {'standard': 0.8, 'premium': 0.2}.",
    )
    timestamp_column: Name = "timestamp"

    @model_validator(mode="after")
    def _check_shape(self) -> StreamRows:
        kind = _exactly_one(self, ("rate", "every"), "stream rows")
        if kind == "rate":
            if self.per.total_seconds() < 1:
                raise ValueError("rows: 'per' must be at least 1s")
            per_hour = self.rate * 3600 / self.per.total_seconds()
            if per_hour > MAX_STREAM_ROWS_PER_HOUR:
                raise ValueError(
                    f"rows: at most {MAX_STREAM_ROWS_PER_HOUR:,} rows an hour (this is {per_hour:,.0f})"
                )
            if self.one_each:
                raise ValueError("rows: 'one_each' needs 'every' (a series per individual)")
        elif self.every.total_seconds() < 1:
            raise ValueError("rows: 'every' must be at least 1s")
        if self.one_each and self.from_ is not None:
            raise ValueError("rows: 'one_each' can't be combined with 'from'")
        if self.from_ is not None:
            _check_probabilities(self.from_, "rows: 'from' shares")
        return self

    @property
    def has_timestamps(self) -> bool:
        return True


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


# --------------------------------------------------------------------------------------
# Datasets and streams
# --------------------------------------------------------------------------------------


class _TableSpec(_Model):
    """What datasets and streams share: profiles, columns and their validation."""

    name: Name = "dataset"
    description: str | None = Field(None, max_length=500)
    seed: int | None = None
    rows: RowsSpec | StreamRows
    profiles: dict[Name, Profile] = Field(default_factory=dict, max_length=MAX_PROFILES)
    common_columns: dict[Name, ColumnSpec] = Field(default_factory=dict)
    profile_column: Name = "profile"
    id_column: Name = "id"
    anomaly_column: Name = "anomaly"

    @model_validator(mode="after")
    def _check(self) -> _TableSpec:
        self._check_profiles()
        if not self.column_order:
            raise ValueError("define at least one column in common_columns or profiles")
        if len(self.column_order) > MAX_COLUMNS:
            raise ValueError(f"{len(self.column_order)} columns defined; the limit is {MAX_COLUMNS}")
        individuals = sum(profile.count or 0 for profile in self.profiles.values())
        if individuals > MAX_INDIVIDUALS:
            raise ValueError(
                f"profiles have {individuals} individuals in total; the limit is {MAX_INDIVIDUALS}"
            )

        if self.rows.one_each and not self.has_ids:
            raise ValueError("rows.one_each needs every profile to have a count")
        if self.rows.from_ is not None and set(self.rows.from_) != set(self.profiles):
            raise ValueError("rows.from must list every profile, and only those")

        earlier = list(self.generated_columns)
        for name in self.column_order:
            if name in earlier:
                raise ValueError(f"column name {name!r} is used twice")
            for spec in self.specs_for(name):
                self._check_column(name, spec, earlier)
            earlier.append(name)
        if self.has_anomalies and self.anomaly_column in earlier:
            raise ValueError(f"column name {self.anomaly_column!r} is used twice")
        return self

    def _check_profiles(self) -> None:
        if not self.profiles:
            return
        counts = [profile.count is not None for profile in self.profiles.values()]
        if any(counts) and not all(counts):
            raise ValueError("either every profile has a count or none do")

        first_name, first = next(iter(self.profiles.items()))
        for name, profile in self.profiles.items():
            if set(profile.columns) != set(first.columns):
                missing = sorted(set(first.columns) - set(profile.columns))
                extra = sorted(set(profile.columns) - set(first.columns))
                raise ValueError(
                    f"profile {name!r} must declare the same columns as {first_name!r} "
                    f"(missing: {missing or 'none'}, extra: {extra or 'none'}); use null for an empty column"
                )
        overlap = sorted(set(first.columns) & set(self.common_columns))
        if overlap:
            raise ValueError(f"{overlap} are in both common_columns and profiles")

    def _check_column(self, name: str, spec: ColumnSpec | None, earlier: list[str]) -> None:
        if spec is None:
            return
        if spec.uses_time and not self.rows.has_timestamps:
            raise ValueError(f"{name}: trend and seasonality need timestamps; set rows.every or rows.between")
        if any(anomaly.between for anomaly in spec.anomalies) and not self.rows.has_timestamps:
            raise ValueError(
                f"{name}: anomalies with 'between' need timestamps; set rows.every or rows.between"
            )
        if spec.per is not None and (not self.has_ids or spec.per != self.id_column):
            raise ValueError(f"{name}: 'per' must be {self.id_column!r}, and profiles need a count")
        for ref in spec.dependencies:
            if ref not in earlier:
                raise ValueError(f"{name}: depends on {ref!r}, which must be an earlier column")

    @property
    def has_ids(self) -> bool:
        return bool(self.profiles) and all(profile.count is not None for profile in self.profiles.values())

    @property
    def generated_columns(self) -> list[str]:
        """Columns the engine adds itself: timestamp, id, profile."""
        names = [self.rows.timestamp_column] if self.rows.has_timestamps else []
        if self.has_ids:
            names.append(self.id_column)
        if self.profiles:
            names.append(self.profile_column)
        return names

    @property
    def has_anomalies(self) -> bool:
        return any(spec and spec.anomalies for name in self.column_order for spec in self.specs_for(name))

    @property
    def output_columns(self) -> list[str]:
        """Every column in the response, in order: generated, defined, then the anomaly label."""
        anomaly = [self.anomaly_column] if self.has_anomalies else []
        return [*self.generated_columns, *self.column_order, *anomaly]

    @property
    def column_order(self) -> list[str]:
        """Common columns first, then profile columns in the order the first profile lists them."""
        profile_columns = list(next(iter(self.profiles.values())).columns) if self.profiles else []
        return [*self.common_columns, *profile_columns]

    def specs_for(self, name: str) -> list[ColumnSpec | None]:
        if name in self.common_columns:
            return [self.common_columns[name]]
        return [profile.columns[name] for profile in self.profiles.values()]

    @property
    def column_count(self) -> int:
        return len(self.output_columns)


class DatasetSpec(_TableSpec):
    """A finite dataset: `POST /v1/datasets`."""

    seed: int | None = Field(None, ge=0, description="Same seed, same data. Omit for a random seed.")
    rows: RowsSpec

    @property
    def row_count(self) -> int:
        if self.rows.one_each:
            individuals = sum(profile.count or 0 for profile in self.profiles.values())
            return individuals * (self.rows.count or 1)
        return self.rows.count or 0


class StreamSpec(_TableSpec):
    """An endless dataset: `POST /v1/streams/window` returns any time window of it."""

    name: Name = "stream"
    seed: int = Field(..., ge=0, description="Required: the seed defines the stream.")
    rows: StreamRows
    start: datetime = Field(
        DEFAULT_START, description="When the stream begins. Trends and sequence numbers count from here."
    )

    @model_validator(mode="after")
    def _check_stream(self) -> StreamSpec:
        self.start = _as_utc(self.start)
        for name in self.column_order:
            for spec in self.specs_for(name):
                if spec is not None and spec.noise is not None and spec.noise.random_walk is not None:
                    raise ValueError(
                        f"{name}: random_walk noise isn't available in streams "
                        "(each value would depend on every step since the start)"
                    )
        return self


class Window(_Model):
    """A time range: rows with `from <= timestamp < to`."""

    from_: datetime = Field(..., alias="from")
    to: datetime

    @model_validator(mode="after")
    def _check(self) -> Window:
        self.from_, self.to = _as_utc(self.from_), _as_utc(self.to)
        if self.to <= self.from_:
            raise ValueError("window: 'to' must be after 'from'")
        return self


class StreamWindowRequest(_Model):
    stream: StreamSpec
    window: Window

    @model_validator(mode="after")
    def _check(self) -> StreamWindowRequest:
        if self.window.from_ < self.stream.start:
            raise ValueError("window: 'from' can't be before the stream's start")
        if self.window.to > self.stream.start + MAX_STREAM_SPAN:
            raise ValueError("window: 'to' must be within 10 years of the stream's start")
        return self
