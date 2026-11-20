# data-simulator-api

Describe a dataset in a few lines of JSON, get realistic synthetic rows back.

```json
{
  "seed": 7,
  "rows": {"one_per": "institution"},
  "entities": [{"name": "institution", "count": 25}],
  "columns": [
    {"name": "institution_id", "type": "entity", "entity": "institution"},
    {"name": "type", "type": "categorical", "values": {"bank": 5, "credit_union": 3, "insurer": 2}},
    {"name": "region", "type": "categorical", "values": ["west", "midwest", "south", "northeast"]},
    {
      "name": "employees",
      "type": "numeric",
      "base": {"dist": "lognormal", "median": 400, "sigma": 0.9},
      "effects": [{"field": "type", "op": "multiply", "values": {"bank": 2.5, "credit_union": 0.4}}],
      "decimals": 0
    },
    {"name": "is_public", "type": "flag", "probability": 0.3}
  ]
}
```

```json
{"institution_id": "institution_0001", "type": "credit_union", "region": "northeast", "employees": 172, "is_public": 0}
{"institution_id": "institution_0002", "type": "bank", "region": "midwest", "employees": 2320, "is_public": 0}
{"institution_id": "institution_0003", "type": "credit_union", "region": "midwest", "employees": 173, "is_public": 0}
```

## What a spec can describe

**Rows**: what one row is.

| `rows` | Gives you |
|---|---|
| `{"count": 500}` | 500 independent rows |
| `{"one_per": "user"}` | one row per entity, e.g. a users table |
| `{"count": 1000, "between": ["2026-01-01", "2026-02-01"]}` | events at random times |
| `{"every": "1h", "count": 168}` | a regular time series |
| `{"every": "1h", "count": 168, "one_per": "device"}` | one time series per entity |

**Entities**: pools of things rows refer to (users, cards, devices), each with its own attributes. `"popularity": "skewed"` makes a few of them show up far more often.

**Columns**: `numeric`, `categorical`, `flag` (0/1), `entity` (an ID or attribute), `sequence`, `constant`. A numeric value is:

```
base (a constant or a distribution)  →  × / + effects from earlier columns  →  + noise  →  clip, round, gaps
```

The same spec and seed always produce the same data.

## Run it locally

```bash
uv sync
uv run uvicorn data_simulator.api.app:app --reload   # http://127.0.0.1:8000/docs
uv run pytest
```

Or without the API:

```python
from data_simulator import DatasetSpec, generate

spec = DatasetSpec.model_validate({"rows": {"count": 3}, "columns": [{"name": "x", "type": "numeric"}]})
dataset = generate(spec)
```

## Layout

```
src/data_simulator/
  spec.py              the spec: every option, validated (also drives the /docs page)
  engine/              rows.py → entities.py → columns.py → output.py
  api/app.py           FastAPI app: GET /health, POST /v1/datasets
  lambda_handler.py    AWS Lambda entry point
tests/
infra/                 Terraform/Terragrunt for AWS (being reworked)
```

## Status

The app is being rebuilt in small steps. Next: trend and seasonality, anomalies with labels, a preset gallery, then a public deployment with cost controls.

## License

MIT
