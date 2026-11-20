"""A ready-made spec of a given size, for testing pipelines without designing a data model.

Column 1 is `id` (1, 2, 3, ...); the rest cycle through a decimal (normal), a whole
number (Poisson) and a category, so every common type appears.
"""

from __future__ import annotations

from typing import Any

from data_simulator.spec import DatasetSpec

_KINDS: list[tuple[str, dict[str, Any]]] = [
    ("number", {"normal": {"mean": 100, "stddev": 15}, "round": 2}),
    ("count", {"poisson": {"mean": 5}}),
    ("category", {"categorical": ["a", "b", "c", "d"]}),
]


def simple_spec(rows: int, columns: int, seed: int | None) -> DatasetSpec:
    defined: dict[str, Any] = {"id": {"sequence": {}}}
    for index in range(columns - 1):
        kind, column = _KINDS[index % len(_KINDS)]
        defined[f"{kind}_{index // len(_KINDS) + 1}"] = column
    return DatasetSpec.model_validate(
        {"name": "simple", "seed": seed, "rows": {"count": rows}, "common_columns": defined}
    )
