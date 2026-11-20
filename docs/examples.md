# Examples

Complete specs and the first rows they produce. Each runs on the
[/docs](https://d1dfbd1pkurhz5.cloudfront.net/docs) page; [Using the API](api.md) explains
every option.

- [Card transactions](#card-transactions): two profiles, rows at random times
- [One row per institution](#one-row-per-institution): an entity table
- [Hourly readings per sensor, with anomalies](#hourly-readings-per-sensor-with-anomalies): a time series per individual
- [Web traffic with growth and cycles](#web-traffic-with-growth-and-cycles): one time series

## Card transactions

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

## One row per institution

Three profiles with their own size distributions; `one_each` gives one row per individual.

```json
{
  "seed": 7,
  "profiles": {
    "bank":         {"count": 12, "columns": {"employees": {"lognormal": {"median": 1000, "sigma": 0.9}, "round": 0}, "is_public": {"bernoulli": 0.5}}},
    "credit_union": {"count": 8,  "columns": {"employees": {"lognormal": {"median": 160, "sigma": 0.7}, "round": 0},  "is_public": {"constant": 0}}},
    "insurer":      {"count": 5,  "columns": {"employees": {"lognormal": {"median": 400, "sigma": 0.9}, "round": 0},  "is_public": {"bernoulli": 0.4}}}
  },
  "common_columns": {"region": {"categorical": ["west", "midwest", "south", "northeast"]}},
  "rows": {"one_each": true}
}
```

| id | profile | region | employees | is_public |
|---|---|---|---|---|
| bank_0001 | bank | midwest | 613 | 0 |
| bank_0002 | bank | midwest | 353 | 1 |
| credit_union_0001 | credit_union | west | 61 | 0 |
| credit_union_0002 | credit_union | midwest | 148 | 0 |
| insurer_0001 | insurer | west | 197 | 0 |

## Hourly readings per sensor, with anomalies

Each sensor gets a fixed calibration offset (`"per": "id"`) that its temperature adds. Outdoor sensors follow a daily cycle and see an afternoon heatwave; indoor sensors sometimes go dead.

```json
{
  "seed": 3,
  "profiles": {
    "indoor":  {"count": 3, "columns": {"temperature_c": {"constant": 21, "add_column": "calibration_offset", "noise": {"random_walk": {"step": 0.1}}, "round": 2,
                                                            "anomalies": [{"name": "sensor_dead", "set": null, "chance": 0.03}]}}},
    "outdoor": {"count": 2, "columns": {"temperature_c": {"constant": 12, "add_column": "calibration_offset", "seasonality": [{"period": "1d", "amplitude": 5, "peak": "15h"}],
                                                            "noise": {"normal": {"stddev": 0.5}}, "round": 2,
                                                            "anomalies": [{"name": "heatwave", "add": 8, "between": ["2026-01-01T12:00:00Z", "2026-01-01T17:00:00Z"]}]}}}
  },
  "common_columns": {"calibration_offset": {"normal": {"mean": 0, "stddev": 0.8}, "per": "id", "round": 2}},
  "rows": {"every": "1h", "count": 24, "one_each": true}
}
```

| timestamp | id | profile | calibration_offset | temperature_c | anomaly |
|---|---|---|---|---|---|
| 2026-01-01T10:00:00Z | outdoor_0001 | outdoor | 0.27 | 13.16 |  |
| 2026-01-01T11:00:00Z | outdoor_0001 | outdoor | 0.27 | 14.31 |  |
| 2026-01-01T12:00:00Z | outdoor_0001 | outdoor | 0.27 | 23.68 | heatwave |
| 2026-01-01T13:00:00Z | outdoor_0001 | outdoor | 0.27 | 23.73 | heatwave |
| 2026-01-01T14:00:00Z | outdoor_0001 | outdoor | 0.27 | 24.52 | heatwave |
| 2026-01-01T10:00:00Z | indoor_0002 | indoor | -0.24 |  | sensor_dead |

## Web traffic with growth and cycles

One time series, no profiles: growing 1% a day, busiest at 2pm and midweek, with whole-number counts.

```json
{
  "seed": 11,
  "common_columns": {
    "page_views": {
      "constant": 1000,
      "trend": {"growth": 0.01, "per": "1d"},
      "seasonality": [{"period": "1d", "amplitude": 400, "peak": "14h"}, {"period": "7d", "amplitude": 150, "peak": "2d"}],
      "noise": {"poisson": true}
    }
  },
  "rows": {"every": "1h", "count": 336, "start": "2026-03-02T00:00:00Z"}
}
```

| timestamp | page_views |
|---|---|
| 2026-03-02T10:00:00Z | 1177 |
| 2026-03-02T11:00:00Z | 1349 |
| 2026-03-02T12:00:00Z | 1352 |
| 2026-03-02T13:00:00Z | 1366 |
| 2026-03-02T14:00:00Z | 1455 |
| 2026-03-02T15:00:00Z | 1515 |
