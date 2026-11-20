"""Entity pools: generate each entity's attributes, then assign rows to entities."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from data_simulator.engine.columns import generate_column
from data_simulator.engine.frame import Frame
from data_simulator.rng import rng_for
from data_simulator.spec import EntitySpec


@dataclass
class EntityTable:
    spec: EntitySpec
    ids: np.ndarray
    attributes: Frame


def build_entity_table(entity: EntitySpec, seed: int) -> EntityTable:
    width = max(4, len(str(entity.count)))
    ids = np.array([f"{entity.name}_{index:0{width}d}" for index in range(1, entity.count + 1)], dtype=object)

    attributes = Frame(n=entity.count, seed=seed)
    for attribute in entity.attributes:
        rng = rng_for(seed, "entity", entity.name, attribute.name)
        attributes.columns[attribute.name] = generate_column(attribute, attributes, rng)

    return EntityTable(spec=entity, ids=ids, attributes=attributes)


def assign_rows(entity: EntitySpec, n: int, seed: int) -> np.ndarray:
    """Pick an entity for each of `n` rows, honouring the entity's popularity."""
    rng = rng_for(seed, "entity", entity.name, "assignment")
    if entity.popularity == "uniform":
        return rng.integers(0, entity.count, size=n)

    # Zipf-like: a handful of entities account for a large share of rows. Shuffle so the
    # popular ones aren't simply the lowest IDs.
    weights = 1.0 / np.arange(1, entity.count + 1)
    rng.shuffle(weights)
    return rng.choice(entity.count, size=n, p=weights / weights.sum())
