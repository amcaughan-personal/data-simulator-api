# data-simulator-api

Describe the kinds of things in your data and how each column is distributed; get realistic synthetic rows back.

## Example

Card transactions from two kinds of card. Premium cards spend more and are declined less, and 80% of transactions come from standard cards.

```json
{
  "seed": 42,
  "profiles": {
    "standard_card": {
      "count": 32,
      "columns": {
        "amount":   {"lognormal": {"median": 35, "sigma": 0.8}, "round": 2},
        "items":    {"poisson": {"mean": 2}},
        "declined": {"bernoulli": 0.03}
      }
    },
    "premium_card": {
      "count": 8,
      "columns": {
        "amount":   {"lognormal": {"median": 60, "sigma": 0.6}, "round": 2},
        "items":    {"poisson": {"mean": 4}},
        "declined": {"bernoulli": 0.01}
      }
    }
  },
  "common_columns": {
    "channel": {"categorical": {"in_store": 0.6, "online": 0.4}}
  },
  "rows": {
    "count": 200,
    "between": ["2026-03-01", "2026-03-08"],
    "from": {"standard_card": 0.8, "premium_card": 0.2}
  },
  "profile_column": "card_type",
  "id_column": "card_id"
}
```

| timestamp | card_id | card_type | channel | amount | items | declined |
|---|---|---|---|---|---|---|
| 2026-03-01T00:28:43Z | standard_card_0007 | standard_card | online | 13.35 | 1 | 0 |
| 2026-03-01T00:47:17Z | standard_card_0004 | standard_card | in_store | 66.03 | 2 | 0 |
| 2026-03-01T01:03:32Z | standard_card_0002 | standard_card | in_store | 36.12 | 2 | 0 |
| 2026-03-01T01:12:11Z | premium_card_0001 | premium_card | in_store | 47.55 | 3 | 1 |
| 2026-03-01T01:17:46Z | standard_card_0031 | standard_card | in_store | 30.86 | 3 | 0 |

Same spec and seed, same data.

## How a spec works

**`profiles`**: the kinds of things in the data. Each profile lists the same columns, with its own distribution for each (`null` means always empty for that profile). With a `count`, a profile is a pool of individuals, and each row gets an ID (`premium_card_0001`). Every row also records its profile, which doubles as ground truth.

**`common_columns`**: columns that work the same for every row. A dataset with one kind of thing only needs these.

**`rows`**: how many rows there are and when they happen.

| `rows` | Gives you |
|---|---|
| `{"count": 500}` | 500 rows |
| `{"count": 500, "from": {"a": 0.8, "b": 0.2}}` | 80% of rows from profile `a`, 20% from `b` |
| `{"count": 1000, "between": ["2026-01-01", "2026-02-01"]}` | rows at random times |
| `{"every": "1h", "count": 168}` | a regular time series |
| `{"one_each": true}` | one row per individual, e.g. a table of institutions |
| `{"every": "1h", "count": 24, "one_each": true}` | a time series per individual, e.g. sensors |

**Columns**: the main key says what the values are.

| Column | Values |
|---|---|
| `{"normal": {"mean": 50, "stddev": 10}}` | bell curve |
| `{"lognormal": {"median": 35, "sigma": 0.8}}` | positive and right-skewed, like prices |
| `{"uniform": {"low": 0, "high": 1}}` | anywhere in a range |
| `{"exponential": {"mean": 5}}` | waiting times |
| `{"poisson": {"mean": 3}}` | counts |
| `{"bernoulli": 0.3}` | 1 with 30% chance, else 0 |
| `{"categorical": {"west": 0.75, "east": 0.25}}` | picked with these probabilities (adding up to 1); a plain list means equally likely |
| `{"constant": 21}` | always the same |
| `{"sequence": {"start": 1}}` | 1, 2, 3, ... |

Optional adjustments, applied in this order:

| Key | Does |
|---|---|
| `"per": "id"` | one value per individual (e.g. each sensor's calibration offset) |
| `"trend": {"growth": 0.01, "per": "1d"}` | grows 1% a day; `{"linear": 5, "per": "1d"}` adds 5 a day |
| `"seasonality": [{"period": "1d", "amplitude": 400, "peak": "14h"}]` | daily cycle peaking at 2pm (UTC) |
| `"multiply_column"` / `"add_column"` | multiply by (or add) an earlier column: `"offset"`, or a value looked up from one: `{"region": {"west": 1.2}}` |
| `"noise": {"normal": {"stddev": 5}}` | also `uniform`, `random_walk`, or `{"poisson": true}` for counts |
| `"min"`, `"max"`, `"round"` | clip and round |
| `"missing": 0.05` | leave 5% of values empty |
| `"anomalies": [{"name": "spike", "multiply": 3, "chance": 0.01}]` | something unusual on some rows (see below) |

`multiply_column` and `add_column` can only reference columns listed earlier (common columns come first), so reference loops are impossible.

### Anomalies

An anomaly changes some values (`multiply`, `add`, or `set`, where `null` empties the value) on rows picked by `chance`, by a time window (`between`), or both. Each affected row records the anomaly's name in an `anomaly` column, so the data comes with ground truth for analysis or model training:

```json
"anomalies": [
  {"name": "sensor_dead", "set": null, "chance": 0.03},
  {"name": "heatwave", "add": 8, "between": ["2026-01-01T12:00:00Z", "2026-01-01T17:00:00Z"]}
]
```

Anomalies apply to rows, not to individuals. For whole kinds of unusual things (say, fraudulent cards), use a rare profile instead.

## CSV

Send `Accept: text/csv` to get CSV instead of JSON. The seed and row count come back as `X-Seed` and `X-Row-Count` headers.

```bash
curl -X POST http://127.0.0.1:8000/v1/datasets -H "Accept: text/csv" -H "Content-Type: application/json" -d @spec.json > data.csv
```

## Limits

Every response is kept small, so a tiny request can't ask for a huge table:

| Limit | Value |
|---|---|
| Cells per response (rows × columns) | 100,000 (about 3 MB of JSON) |
| Columns | 100 |
| Profiles | 50 |
| Individuals across all profiles | 50,000 |
| Text values (constants, categories) | 100 characters; 1,000 categories |

Requests over a limit get a `422` saying which limit was hit.

## Run it locally

```bash
uv sync
uv run uvicorn data_simulator.api.app:app --reload   # open http://127.0.0.1:8000/docs
uv run pytest
```

The `/docs` page has four runnable examples: transactions, institutions, a sensor fleet, and web traffic.

## Layout

```
src/data_simulator/
  spec.py              the spec: every option, validated (also drives /docs)
  engine/              rows.py → columns.py → output.py
  api/app.py           FastAPI app: GET /health, POST /v1/datasets
  lambda_handler.py    AWS Lambda entry point
tests/
infra/                 Terraform/Terragrunt for AWS (being reworked)
```

## Status

Being rebuilt in small steps. Next: a public deployment with cost controls.

## License

MIT
