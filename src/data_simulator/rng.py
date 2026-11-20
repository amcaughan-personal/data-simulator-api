"""Deterministic random number generators.

Every part of a dataset (each field, each entity attribute, row timing) draws from its
own generator derived from the dataset seed and a stable name. That keeps output
reproducible, and adding or removing one field doesn't change the values of the others.
"""

from __future__ import annotations

import hashlib
import json
import secrets

import numpy as np


def new_seed() -> int:
    return secrets.randbelow(2**31)


def rng_for(seed: int, *parts: object) -> np.random.Generator:
    payload = json.dumps([seed, *parts], separators=(",", ":"), default=str)
    digest = hashlib.blake2b(payload.encode("utf-8"), digest_size=8).digest()
    return np.random.default_rng(int.from_bytes(digest, "big"))
