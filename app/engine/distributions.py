from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from app.api.models import DistributionSampleRequest


def _get_parameter(parameters: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in parameters:
            return parameters[name]
    return default


def _normalize_weights(values: Sequence[Any], weights: Sequence[float] | None) -> np.ndarray | None:
    if weights is None:
        return None

    if len(values) != len(weights):
        raise ValueError("weights must match the number of categorical values")

    weights_array = np.asarray(weights, dtype=float)
    total = weights_array.sum()
    if total <= 0:
        raise ValueError("categorical weights must sum to a positive value")

    return weights_array / total


def sample_distribution(
    distribution: str,
    parameters: dict[str, Any],
    count: int,
    seed: int | None = None,
) -> list[Any]:
    rng = np.random.default_rng(seed)

    if distribution == "normal":
        mean = float(_get_parameter(parameters, "mean", "loc", default=0.0))
        stddev = float(_get_parameter(parameters, "stddev", "sigma", "scale", default=1.0))
        return rng.normal(loc=mean, scale=stddev, size=count).tolist()

    if distribution == "uniform":
        low = float(_get_parameter(parameters, "low", "min", default=0.0))
        high = float(_get_parameter(parameters, "high", "max", default=1.0))
        return rng.uniform(low=low, high=high, size=count).tolist()

    if distribution == "lognormal":
        mean = float(_get_parameter(parameters, "mean", default=0.0))
        sigma = float(_get_parameter(parameters, "sigma", "stddev", default=1.0))
        return rng.lognormal(mean=mean, sigma=sigma, size=count).tolist()

    if distribution == "exponential":
        rate = _get_parameter(parameters, "rate")
        scale = float(_get_parameter(parameters, "scale", default=1.0 if rate is None else 1.0 / float(rate)))
        return rng.exponential(scale=scale, size=count).tolist()

    if distribution == "poisson":
        lam = float(_get_parameter(parameters, "lam", "lambda", "rate", default=1.0))
        return rng.poisson(lam=lam, size=count).tolist()

    if distribution == "bernoulli":
        probability = float(_get_parameter(parameters, "p", "probability", default=0.5))
        return rng.binomial(n=1, p=probability, size=count).tolist()

    if distribution == "categorical":
        values = _get_parameter(parameters, "values")
        if not values:
            raise ValueError("categorical distributions require a non-empty values list")

        weights = _normalize_weights(values, _get_parameter(parameters, "weights", default=None))
        return rng.choice(values, size=count, p=weights).tolist()

    raise ValueError(f"unsupported distribution: {distribution}")


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


def build_distribution_response(request: DistributionSampleRequest) -> dict[str, Any]:
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
