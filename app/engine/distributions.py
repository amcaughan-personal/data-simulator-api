from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from app.api.models import DistributionGenerateRequest, DistributionSampleRequest


DEFAULT_DISTRIBUTION_PARAMETERS: dict[str, dict[str, float]] = {
    "bernoulli": {"probability": 0.5},
    "categorical": {},
    "exponential": {"rate": 1.0},
    "lognormal": {"mean": 0.0, "stddev": 1.0},
    "normal": {"mean": 0.0, "stddev": 1.0},
    "poisson": {"rate": 1.0},
    "uniform": {"low": 0.0, "high": 1.0},
}


SUPPORTED_DISTRIBUTION_PARAMETERS: dict[str, tuple[str, ...]] = {
    "bernoulli": ("probability",),
    "categorical": ("values", "weights"),
    "exponential": ("rate",),
    "lognormal": ("mean", "stddev"),
    "normal": ("mean", "stddev"),
    "poisson": ("rate",),
    "uniform": ("low", "high"),
}


def resolve_distribution_parameter(distribution: str, parameters: dict[str, Any], parameter: str) -> float:
    if parameter in parameters:
        return float(parameters[parameter])

    defaults = DEFAULT_DISTRIBUTION_PARAMETERS.get(distribution, {})
    if parameter in defaults:
        return defaults[parameter]

    supported_parameters = ", ".join(SUPPORTED_DISTRIBUTION_PARAMETERS.get(distribution, ()))
    raise ValueError(
        f"unsupported parameter {parameter!r} for distribution {distribution!r}; "
        f"supported parameters: {supported_parameters}"
    )


def _normalize_weights(values: Sequence[Any], weights: Sequence[float] | None) -> np.ndarray | None:
    if weights is None:
        return None

    if len(values) != len(weights):
        raise ValueError(
            "categorical weights must match the number of values; "
            f"got {len(weights)} weights for {len(values)} values"
        )

    weights_array = np.asarray(weights, dtype=float)
    total = weights_array.sum()
    if total <= 0:
        raise ValueError(f"categorical weights must sum to a positive value; got sum={total}")

    return weights_array / total


def _require_non_negative(name: str, value: float) -> None:
    if value < 0:
        raise ValueError(f"{name} must be >= 0; got {value}")


def _require_positive(name: str, value: float) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be > 0; got {value}")


def _require_probability(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0.0 and 1.0 inclusive; got {value}")


def sample_distribution(
    distribution: str,
    parameters: dict[str, Any],
    count: int,
    seed: int | None = None,
) -> list[Any]:
    rng = np.random.default_rng(seed)

    if distribution == "normal":
        mean = float(parameters.get("mean", 0.0))
        stddev = float(parameters.get("stddev", 1.0))
        _require_non_negative("normal.stddev", stddev)
        return rng.normal(loc=mean, scale=stddev, size=count).tolist()

    if distribution == "uniform":
        low = float(parameters.get("low", 0.0))
        high = float(parameters.get("high", 1.0))
        if high <= low:
            raise ValueError(f"uniform.high must be greater than uniform.low; got low={low}, high={high}")
        return rng.uniform(low=low, high=high, size=count).tolist()

    if distribution == "lognormal":
        mean = float(parameters.get("mean", 0.0))
        stddev = float(parameters.get("stddev", 1.0))
        _require_non_negative("lognormal.stddev", stddev)
        return rng.lognormal(mean=mean, sigma=stddev, size=count).tolist()

    if distribution == "exponential":
        rate = float(parameters.get("rate", 1.0))
        _require_positive("exponential.rate", rate)
        scale = 1.0 / rate
        return rng.exponential(scale=scale, size=count).tolist()

    if distribution == "poisson":
        rate = float(parameters.get("rate", 1.0))
        _require_non_negative("poisson.rate", rate)
        return rng.poisson(lam=rate, size=count).tolist()

    if distribution == "bernoulli":
        probability = float(parameters.get("probability", 0.5))
        _require_probability("bernoulli.probability", probability)
        return rng.binomial(n=1, p=probability, size=count).tolist()

    if distribution == "categorical":
        values = parameters.get("values")
        if not values:
            raise ValueError("categorical distributions require a non-empty values list in parameters.values")

        weights = _normalize_weights(values, parameters.get("weights"))
        return rng.choice(values, size=count, p=weights).tolist()

    supported_distributions = ", ".join(sorted(DEFAULT_DISTRIBUTION_PARAMETERS))
    raise ValueError(
        f"unsupported distribution {distribution!r}; supported distributions: {supported_distributions}"
    )


def summarize_samples(samples: Sequence[Any]) -> dict[str, Any]:
    if not samples:
        return {"count": 0}

    summary: dict[str, Any] = {"count": len(samples)}

    numeric_samples = [sample for sample in samples if isinstance(sample, (int, float, np.integer, np.floating))]
    if len(numeric_samples) == len(samples):
        numeric_array = np.asarray(samples, dtype=float)
        summary.update(
            {
                "min": float(numeric_array.min()),
                "max": float(numeric_array.max()),
                "mean": float(numeric_array.mean()),
                "stddev": float(numeric_array.std(ddof=0)),
            }
        )
    else:
        values, counts = np.unique(np.asarray(samples, dtype=object), return_counts=True)
        summary["value_counts"] = {str(value): int(count) for value, count in zip(values.tolist(), counts.tolist())}

    return summary


def build_distribution_generate_response(request: DistributionGenerateRequest) -> dict[str, Any]:
    samples = sample_distribution(
        distribution=request.distribution,
        parameters=request.parameters,
        count=request.count,
        seed=request.seed,
    )

    payload = {
        "distribution": request.distribution,
        "parameters": request.parameters,
        "count": request.count,
        "seed": request.seed,
        "samples": samples,
    }
    if request.summary:
        payload["summary"] = summarize_samples(samples)

    return payload


def build_distribution_sample_response(request: DistributionSampleRequest) -> dict[str, Any]:
    sample = sample_distribution(
        distribution=request.distribution,
        parameters=request.parameters,
        count=1,
        seed=request.seed,
    )[0]

    return {
        "distribution": request.distribution,
        "parameters": request.parameters,
        "seed": request.seed,
        "sample": sample,
    }
