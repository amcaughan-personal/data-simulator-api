"""Lay out rows: how many there are, their timestamps, and which entity each belongs to."""

from __future__ import annotations

import numpy as np

from data_simulator.engine.frame import Frame
from data_simulator.rng import rng_for
from data_simulator.spec import DatasetSpec


def layout_rows(spec: DatasetSpec, seed: int) -> Frame:
    rows = spec.rows
    entity_counts = {entity.name: entity.count for entity in spec.entities}
    per_entity = entity_counts[rows.one_per] if rows.one_per else 1
    frame = Frame(n=spec.row_count, seed=seed)

    if rows.every is not None:
        # A regular time series; with one_per, every entity gets a row at every step,
        # ordered by time and then by entity.
        step_index = np.arange(frame.n) // per_entity
        start = _datetime64(rows.start)
        frame.timestamps = start + step_index * _timedelta64(rows.every.total_seconds())
        if rows.one_per:
            entity_index = np.arange(frame.n) % per_entity
            frame.entity_rows[rows.one_per] = entity_index
            frame.series = entity_index
    elif rows.between is not None:
        rng = rng_for(seed, "rows", "timestamps")
        start, end = rows.between
        span_ms = (end - start).total_seconds() * 1000
        offsets = np.sort(rng.uniform(0, span_ms, size=frame.n)).astype(np.int64)
        frame.timestamps = _datetime64(start) + offsets.astype("timedelta64[ms]")
    elif rows.one_per:
        frame.entity_rows[rows.one_per] = np.arange(frame.n)

    return frame


def _datetime64(value) -> np.datetime64:
    return np.datetime64(value.replace(tzinfo=None), "ms")


def _timedelta64(seconds: float) -> np.timedelta64:
    return np.timedelta64(int(round(seconds * 1000)), "ms")
