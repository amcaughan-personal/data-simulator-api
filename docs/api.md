# Using the API

`POST /v1/datasets` takes a JSON spec and returns rows. This page is the reference;
[Examples](examples.md) walks through complete specs and their output, and the interactive
docs at [/docs](https://d1dfbd1pkurhz5.cloudfront.net/docs) run them.

- [How a spec works](#how-a-spec-works): profiles, rows, columns, adjustments
- [Anomalies](#anomalies)
- [Response format and CSV](#response-format-and-csv)
- [Limits and errors](#limits-and-errors)

## How a spec works

**`profiles`**: the kinds of things in the data. Each profile lists the same columns, with its own distribution for each (`null` means always empty for that profile). With a `count`, a profile is a pool of individuals, and each row gets an ID (`premium_card_0001`). Every row also records its profile, which doubles as ground truth. Rename those columns with `profile_column` and `id_column`.

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

**Adjustments**, applied in this order:

| Key | Does |
|---|---|
| `"per": "id"` | one value per individual (e.g. each sensor's calibration offset) |
| `"trend": {"growth": 0.01, "per": "1d"}` | grows 1% a day; `{"linear": 5, "per": "1d"}` adds 5 a day |
| `"seasonality": [{"period": "1d", "amplitude": 400, "peak": "14h"}]` | daily cycle peaking at 2pm (UTC); cycles line up with Monday 00:00 UTC, so a weekly `"peak": "2d"` is Wednesday |
| `"multiply_column"` / `"add_column"` | multiply by (or add) an earlier column: `"offset"`, or a value looked up from one: `{"region": {"west": 1.2}}` |
| `"noise": {"normal": {"stddev": 5}}` | also `uniform`, `random_walk`, or `{"poisson": true}` for counts |
| `"min"`, `"max"`, `"round"` | clip and round |
| `"missing": 0.05` | leave 5% of values empty |
| `"anomalies": [...]` | something unusual on some rows ([below](#anomalies)) |

`multiply_column` and `add_column` can only reference columns listed earlier (common columns come first), so reference loops are impossible. Trend and seasonality need rows with timestamps.

## Anomalies

An anomaly changes some values (`multiply`, `add`, or `set`, where `null` empties the value) on rows picked by `chance`, by a time window (`between`), or both. Each affected row records the anomaly's name in an `anomaly` column (rename it with `anomaly_column`), so the data comes with ground truth for analysis or model training:

```json
"anomalies": [
  {"name": "sensor_dead", "set": null, "chance": 0.03},
  {"name": "heatwave", "add": 8, "between": ["2026-01-01T12:00:00Z", "2026-01-01T17:00:00Z"]}
]
```

Anomalies apply to rows, not to individuals. For whole kinds of unusual things (say, fraudulent cards), use a rare profile instead.

## Response format and CSV

JSON responses carry the data plus what's needed to reproduce it:

```json
{"name": "...", "description": "...", "seed": 42, "row_count": 200, "columns": ["..."], "rows": [{"...": "..."}]}
```

Omit `seed` to get a random one; it comes back in the response, so any result can be regenerated.

Send `Accept: text/csv` to get CSV instead. The seed and row count come back as `X-Seed` and `X-Row-Count` headers.

```bash
curl -X POST https://d1dfbd1pkurhz5.cloudfront.net/v1/datasets \
  -H "Accept: text/csv" -H "Content-Type: application/json" -d @spec.json > data.csv
```

## Limits and errors

Every response is kept small, so a tiny request can't ask for a huge table:

| Limit | Value |
|---|---|
| Cells per response (rows × columns) | 100,000 (about 3 MB of JSON) |
| Columns | 100 |
| Profiles | 50 |
| Individuals across all profiles | 50,000 |
| Text values (constants, categories) | 100 characters; 1,000 categories |
| Request body | 64 KB |
| Requests per IP | 100 per 5 minutes |

| Status | Means |
|---|---|
| `422` | the spec is invalid or over a limit; the body says where and why |
| `413` | request body over 64 KB |
| `403` | too many requests from your IP; try again in a few minutes |
| `405` | only `GET` and `POST` are supported |
