from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


DistributionName = Literal[
    "bernoulli",
    "categorical",
    "exponential",
    "lognormal",
    "normal",
    "poisson",
    "uniform",
]


class DistributionSampleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distribution: DistributionName
    parameters: dict[str, Any] = Field(default_factory=dict)
    count: int = Field(default=1, ge=1, le=5000)
    seed: int | None = None
    summary: bool = False


class TimeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: datetime = Field(default_factory=datetime.utcnow)
    frequency_seconds: int = Field(default=60, ge=1)


class DistributionGeneratorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["distribution"]
    distribution: DistributionName
    parameters: dict[str, Any] = Field(default_factory=dict)


class ConstantGeneratorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["constant"]
    value: Any


class CategoricalGeneratorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["categorical"]
    values: list[Any]
    weights: list[float] | None = None

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, weights: list[float] | None, info) -> list[float] | None:
        if weights is None:
            return weights

        values = info.data.get("values", [])
        if len(weights) != len(values):
            raise ValueError("weights must match the length of values")
        return weights


GeneratorSpec = Annotated[
    DistributionGeneratorSpec | ConstantGeneratorSpec | CategoricalGeneratorSpec,
    Field(discriminator="kind"),
]


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    generator: GeneratorSpec
    nullable: bool = False


class PointSpikeInjectorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["point_spike"]
    injector_id: str
    field: str
    mode: Literal["index", "rate"] = "index"
    index: int | None = Field(default=None, ge=0)
    rate: float | None = Field(default=None, gt=0.0, le=1.0)
    value: float | int | None = None
    offset: float | None = None
    scale: float | None = None
    severity: float = Field(default=1.0, ge=0.0)

    @field_validator("index")
    @classmethod
    def validate_index_mode(cls, index: int | None, info) -> int | None:
        mode = info.data.get("mode", "index")
        if mode == "index" and index is None:
            raise ValueError("index is required when mode is 'index'")
        return index

    @field_validator("rate")
    @classmethod
    def validate_rate_mode(cls, rate: float | None, info) -> float | None:
        mode = info.data.get("mode", "index")
        if mode == "rate" and rate is None:
            raise ValueError("rate is required when mode is 'rate'")
        return rate


class LevelShiftInjectorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["level_shift"]
    injector_id: str
    field: str
    start_index: int = Field(ge=0)
    end_index: int | None = Field(default=None, ge=0)
    offset: float
    severity: float = Field(default=1.0, ge=0.0)


class MissingBurstInjectorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["missing_burst"]
    injector_id: str
    field: str
    mode: Literal["window", "rate"] = "window"
    start_index: int | None = Field(default=None, ge=0)
    end_index: int | None = Field(default=None, ge=0)
    rate: float | None = Field(default=None, gt=0.0, le=1.0)
    severity: float = Field(default=1.0, ge=0.0)

    @field_validator("start_index")
    @classmethod
    def validate_window_mode(cls, start_index: int | None, info) -> int | None:
        mode = info.data.get("mode", "window")
        if mode == "window" and start_index is None:
            raise ValueError("start_index is required when mode is 'window'")
        return start_index

    @field_validator("rate")
    @classmethod
    def validate_missing_rate_mode(cls, rate: float | None, info) -> float | None:
        mode = info.data.get("mode", "window")
        if mode == "rate" and rate is None:
            raise ValueError("rate is required when mode is 'rate'")
        return rate


class StuckValueInjectorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["stuck_value"]
    injector_id: str
    field: str
    start_index: int = Field(ge=0)
    end_index: int | None = Field(default=None, ge=0)
    value: float | int | str | None = None
    severity: float = Field(default=1.0, ge=0.0)


InjectorSpec = Annotated[
    PointSpikeInjectorSpec
    | LevelShiftInjectorSpec
    | MissingBurstInjectorSpec
    | StuckValueInjectorSpec,
    Field(discriminator="kind"),
]


class ScenarioGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    name: str = "scenario"
    description: str | None = None
    seed: int | None = None
    row_count: int = Field(default=100, ge=1, le=5000)
    time: TimeSpec = Field(default_factory=TimeSpec)
    fields: list[FieldSpec]
    injectors: list[InjectorSpec] = Field(default_factory=list)


class PresetGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int | None = None
    row_count: int = Field(default=100, ge=1, le=5000)
    overrides: dict[str, Any] = Field(default_factory=dict)
