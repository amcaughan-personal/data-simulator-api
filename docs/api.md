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

## Streams: fetch any time window

`POST /v1/datasets` returns one complete dataset. `POST /v1/streams/window` instead treats the spec as an **endless stream** and returns one time window of it, so a pipeline can fetch hour after hour:

```json
{
  "stream": {
    "seed": 3,
    "rows": {"every": "15m", "one_each": true},
    "profiles": {"sensor": {"count": 4, "columns": {
      "calibration_offset": {"normal": {"stddev": 0.8}, "per": "id", "round": 2},
      "temperature_c": {"constant": 21, "seasonality": [{"period": "1d", "amplitude": 2.5, "peak": "15h"}],
                        "add_column": "calibration_offset", "noise": {"normal": {"stddev": 0.3}}, "round": 2}}}},
    "common_columns": {"reading_id": {"sequence": {}}}
  },
  "window": {"from": "2026-03-01T09:00:00Z", "to": "2026-03-01T09:30:00Z"}
}
```

| timestamp | id | profile | reading_id | calibration_offset | temperature_c |
|---|---|---|---|---|---|
| 2026-03-01T09:00:00Z | sensor_0001 | sensor | 22801 | -0.94 | 20.43 |
| 2026-03-01T09:00:00Z | sensor_0002 | sensor | 22802 | 0.22 | 21.35 |
| 2026-03-01T09:00:00Z | sensor_0003 | sensor | 22803 | 0.48 | 21.45 |
| 2026-03-01T09:00:00Z | sensor_0004 | sensor | 22804 | -0.25 | 20.6 |
| 2026-03-01T09:15:00Z | sensor_0001 | sensor | 22805 | -0.94 | 20.33 |
| ... | | | | | |

**The guarantee:** the same stream and seed always give the same rows. Fetching 09:00–10:00 and then 10:00–11:00 returns exactly what 09:00–11:00 would, and each individual keeps its fixed (`per`) values in every window. A window includes rows with `from <= timestamp < to`.

The stream spec is a dataset spec with a different `rows`:

| `rows` | Gives |
|---|---|
| `{"rate": 120, "per": "1h"}` | events at random times, about 120 an hour (`from` shares profiles as in datasets) |
| `{"every": "15m"}` | a regular time series |
| `{"every": "15m", "one_each": true}` | a series per individual |

- **`seed` is required**: it defines the stream.
- **`start`** (default `2026-01-01`) is when the stream begins. Windows can't start earlier, and must end within 10 years of it. Trends count from `start`.
- **`sequence` columns number rows from `start`**, so a row has the same number whichever window returned it: a reliable key for deduplicating.
- **`random_walk` noise isn't available**: each value would depend on every step since the start.
- Streams are limited to 60,000 rows an hour; each window is limited by cells, like datasets.

The response is a dataset response plus `start` and `window`. CSV works the same way.

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
| Stream rate | 60,000 rows an hour; windows within 10 years of `start` |
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
