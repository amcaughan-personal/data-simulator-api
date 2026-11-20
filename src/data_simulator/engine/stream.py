"""Lay out the rows of a stream window.

A stream is cut into fixed time buckets, counted from its start. Each bucket's rows are
generated from the stream seed and the bucket's number only, never from the window
asked for, so any window is the same rows whichever request it came from. A window
lays out every bucket it touches and keeps the rows inside it.

- `rate` streams: each bucket gets a random number of events at random times.
- `every` streams: each bucket holds a fixed number of time steps.

Bucket sizes come from the spec (about 1,000 rows each), not from the window.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Iterator
from datetime import datetime

import numpy as np

from data_simulator.engine.frame import Frame
from data_simulator.engine.rows import create_individuals, datetime64, pick_owners, set_series
from data_simulator.rng import rng_for
from data_simulator.spec import StreamSpec

BUCKET_ROWS = 1024  # rows per bucket, roughly
MIN_BUCKET_MS = 60_000  # rate streams: buckets between 1 minute...
MAX_BUCKET_MS = MIN_BUCKET_MS * 2**15  # ...and about 23 days
COUNT_CHUNK = 1024  # rate streams: bucket sizes are drawn this many at a time


def stream_layouts(spec: StreamSpec, start: datetime, end: datetime) -> Iterator[tuple[Frame, np.ndarray]]:
    """Each bucket overlapping [start, end) as a laid-out frame, plus which rows are inside."""
    ids, individual_profile = create_individuals(spec) if spec.has_ids else (None, None)
    origin = datetime64(spec.start)
    from_ms = _ms(start, spec.start)
    to_ms = _ms(end, spec.start)

    def new_frame(bucket: int, n: int) -> Frame:
        bucket_seed = int(rng_for(spec.seed, "stream", "bucket", bucket).integers(2**62))
        return Frame(
            n=n,
            seed=bucket_seed,
            fixed_seed=spec.seed,
            profile_names=list(spec.profiles),
            ids=ids,
            individual_profile=individual_profile,
            time_origin=origin,
        )

    if spec.rows.every is not None:
        yield from _steps(spec, new_frame, origin, from_ms, to_ms, ids)
    else:
        yield from _events(spec, new_frame, origin, from_ms, to_ms)


def _steps(spec, new_frame, origin, from_ms, to_ms, ids) -> Iterator[tuple[Frame, np.ndarray]]:
    every_ms = round(spec.rows.every.total_seconds() * 1000)
    series_count = len(ids) if spec.rows.one_each else 1
    steps_per_bucket = 2 ** int(math.log2(max(1, BUCKET_ROWS // series_count)))

    first_step = -(-from_ms // every_ms)  # first step at or after `from`
    end_step = -(-to_ms // every_ms)  # first step at or after `to`
    if end_step <= first_step:
        return

    for bucket in range(first_step // steps_per_bucket, (end_step - 1) // steps_per_bucket + 1):
        bucket_steps = bucket * steps_per_bucket + np.arange(steps_per_bucket)
        frame = new_frame(bucket, steps_per_bucket * series_count)
        if spec.rows.one_each:
            # Every individual at every step, ordered by time.
            step = np.repeat(bucket_steps, series_count)
            frame.individual = np.tile(np.arange(series_count), steps_per_bucket)
            frame.row_numbers = step * series_count + frame.individual
        else:
            step = bucket_steps
            frame.row_numbers = step
            pick_owners(spec, frame)
        set_series(frame)
        frame.timestamps = origin + (step * every_ms).astype("timedelta64[ms]")
        yield frame, (step >= first_step) & (step < end_step)


def _events(spec, new_frame, origin, from_ms, to_ms) -> Iterator[tuple[Frame, np.ndarray]]:
    rows = spec.rows
    per_ms = rows.rate / (rows.per.total_seconds() * 1000)
    target = BUCKET_ROWS / per_ms
    bucket_ms = min(MAX_BUCKET_MS, MIN_BUCKET_MS * 2 ** int(math.log2(max(1.0, target / MIN_BUCKET_MS))))
    expected = per_ms * bucket_ms

    @functools.cache
    def sizes(chunk: int) -> np.ndarray:
        return rng_for(spec.seed, "stream", "sizes", chunk).poisson(expected, COUNT_CHUNK)

    first, last = from_ms // bucket_ms, (to_ms - 1) // bucket_ms
    # Row numbers continue from the start of the stream: count every earlier bucket's rows.
    first_chunk = first // COUNT_CHUNK
    row_number = sum(int(sizes(chunk).sum()) for chunk in range(first_chunk))
    row_number += int(sizes(first_chunk)[: first % COUNT_CHUNK].sum())

    for bucket in range(first, last + 1):
        n = int(sizes(bucket // COUNT_CHUNK)[bucket % COUNT_CHUNK])
        frame = new_frame(bucket, n)
        offsets = np.sort(rng_for(frame.seed, "rows", "timestamps").integers(0, bucket_ms, n))
        bucket_offsets = bucket * bucket_ms + offsets
        frame.timestamps = origin + bucket_offsets.astype("timedelta64[ms]")
        frame.row_numbers = row_number + np.arange(n)
        row_number += n
        pick_owners(spec, frame)
        set_series(frame)
        yield frame, (bucket_offsets >= from_ms) & (bucket_offsets < to_ms)


def _ms(value: datetime, origin: datetime) -> int:
    return round((value - origin).total_seconds() * 1000)
