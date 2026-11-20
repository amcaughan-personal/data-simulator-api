"""Generate a dataset from a spec.

The steps, in order:
1. Lay out rows: count, timestamps, and which entity a row belongs to (`rows.py`).
2. Build each entity's attribute table (`entities.py`).
3. Generate columns left to right, so effects can depend on earlier columns (`columns.py`).
4. Convert to JSON-ready rows (`output.py`).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from data_simulator.engine.columns import generate_column
from data_simulator.engine.entities import EntityTable, assign_rows, build_entity_table
from data_simulator.engine.frame import Frame, GenerationError
from data_simulator.engine.output import to_rows
from data_simulator.engine.rows import layout_rows
from data_simulator.rng import new_seed, rng_for
from data_simulator.spec import DatasetSpec, EntityColumn

__all__ = ["GenerationError", "generate"]


def generate(spec: DatasetSpec, max_rows: int | None = None) -> dict[str, Any]:
    if max_rows is not None and spec.row_count > max_rows:
        raise GenerationError(f"spec would produce {spec.row_count} rows; the limit is {max_rows}")

    seed = spec.seed if spec.seed is not None else new_seed()
    frame = layout_rows(spec, seed)
    tables = {entity.name: build_entity_table(entity, seed) for entity in spec.entities}

    names: list[str] = []
    if frame.timestamps is not None:
        frame.columns[spec.rows.timestamp_column] = frame.timestamps
        names.append(spec.rows.timestamp_column)

    for column in spec.columns:
        if isinstance(column, EntityColumn):
            values = _entity_values(column, frame, tables[column.entity], seed)
        else:
            values = generate_column(column, frame, rng_for(seed, "column", column.name))
        frame.columns[column.name] = values
        names.append(column.name)

    return {
        "name": spec.name,
        "description": spec.description,
        "seed": seed,
        "row_count": frame.n,
        "columns": names,
        "rows": to_rows(frame, names),
    }


def _entity_values(column: EntityColumn, frame: Frame, table: EntityTable, seed: int) -> np.ndarray:
    if column.entity not in frame.entity_rows:
        frame.entity_rows[column.entity] = assign_rows(table.spec, frame.n, seed)
    rows = frame.entity_rows[column.entity]

    if column.attribute is None:
        values = table.ids[rows]
    else:
        values = table.attributes.columns[column.attribute][rows]
        if column.attribute in table.attributes.integer_columns:
            frame.integer_columns.add(column.name)

    if column.missing_rate > 0:
        missing = rng_for(seed, "column", column.name, "missing").random(frame.n) < column.missing_rate
        if values.dtype == object:
            values = values.copy()
            values[missing] = None
        else:
            values = np.where(missing, np.nan, values)
    return values
