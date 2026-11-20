# Examples

Complete specs and the first rows they produce. Each runs on the
[/docs](https://d1dfbd1pkurhz5.cloudfront.net/docs) page; [Using the API](api.md) explains
every option.

- [Card transactions](#card-transactions): two profiles, rows at random times
- [One row per institution](#one-row-per-institution): an entity table
- [Hourly readings per sensor, with anomalies](#hourly-readings-per-sensor-with-anomalies): a time series per individual
- [Web traffic with growth and cycles](#web-traffic-with-growth-and-cycles): one time series
- [Card fraud as a rare profile](#card-fraud-as-a-rare-profile): anomalies as a rare kind of thing
- [Survey responses](#survey-responses): no profiles, no time
- [Daily sales per store](#daily-sales-per-store): a fixed per-store size, weekly cycle, a holiday spike
- [Service latency with an outage](#service-latency-with-an-outage): long-tailed latencies, an outage window
- [Patients where some columns don't apply](#patients-where-some-columns-dont-apply): null columns, missing values

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
        "items":    {"poisson": {"mean": 2}, "min": 1},
        "declined": {"bernoulli": 0.03}
      }
    },
    "premium_card": {
      "count": 8,
      "columns": {
        "amount":   {"lognormal": {"median": 60, "sigma": 0.6}, "round": 2},
        "items":    {"poisson": {"mean": 4}, "min": 1},
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

## Card fraud as a rare profile

Fraud isn't a tweak to normal transactions; it's a different kind of behaviour. Here it's a profile drawn for 1% of rows, with large amounts, night-time hours and mostly foreign merchants, while a few normal cards account for most activity (`skewed`). The `label` column is the ground truth a fraud model would train on.

```json
{
  "seed": 21,
  "profiles": {
    "normal": {
      "count": 500,
      "popularity": "skewed",
      "columns": {
        "amount": {
          "lognormal": {
            "median": 40,
            "sigma": 0.9
          },
          "round": 2
        },
        "hour": {
          "normal": {
            "mean": 14,
            "stddev": 4
          },
          "min": 0,
          "max": 23,
          "round": 0
        },
        "is_foreign": {
          "bernoulli": 0.03
        }
      }
    },
    "fraud": {
      "count": 5,
      "columns": {
        "amount": {
          "lognormal": {
            "median": 400,
            "sigma": 0.5
          },
          "round": 2
        },
        "hour": {
          "normal": {
            "mean": 3,
            "stddev": 2
          },
          "min": 0,
          "max": 23,
          "round": 0
        },
        "is_foreign": {
          "bernoulli": 0.7
        }
      }
    }
  },
  "common_columns": {
    "merchant_type": {
      "categorical": {
        "grocery": 0.4,
        "retail": 0.35,
        "online": 0.25
      }
    }
  },
  "rows": {
    "count": 5000,
    "from": {
      "normal": 0.99,
      "fraud": 0.01
    }
  },
  "profile_column": "label",
  "id_column": "card_id"
}
```

| card_id | label | merchant_type | amount | hour | is_foreign |
|---|---|---|---|---|---|
| normal_0434 | normal | online | 26.66 | 9 | 0 |
| normal_0110 | normal | grocery | 19.36 | 13 | 0 |
| normal_0269 | normal | grocery | 87.33 | 16 | 0 |
| fraud_0001 | fraud | online | 531.02 | 3 | 1 |
| fraud_0001 | fraud | online | 270.18 | 7 | 0 |

## Survey responses

The simplest kind of dataset: no profiles and no time, just independent rows. Scores are a bell curve clipped to 1–10 and rounded, and 30% of respondents left no comment.

```json
{
  "seed": 5,
  "common_columns": {
    "response_id": {
      "sequence": {
        "start": 1001
      }
    },
    "age_group": {
      "categorical": {
        "18-29": 0.25,
        "30-44": 0.3,
        "45-64": 0.3,
        "65+": 0.15
      }
    },
    "satisfaction": {
      "normal": {
        "mean": 7.2,
        "stddev": 1.8
      },
      "min": 1,
      "max": 10,
      "round": 0
    },
    "would_recommend": {
      "bernoulli": 0.68
    },
    "comment_length": {
      "exponential": {
        "mean": 40
      },
      "round": 0,
      "missing": 0.3
    }
  },
  "rows": {
    "count": 400
  }
}
```

| response_id | age_group | satisfaction | would_recommend | comment_length |
|---|---|---|---|---|
| 1001 | 18-29 | 4 | 0 |  |
| 1002 | 45-64 | 5 | 1 | 3 |
| 1003 | 45-64 | 5 | 0 | 11 |
| 1004 | 18-29 | 7 | 1 |  |
| 1005 | 30-44 | 10 | 1 | 92 |

## Daily sales per store

A daily series for each of 4 stores. Each store gets a size fixed for its whole history (`"per": "store_id"`) that its sales multiply by. Sales grow 0.2% a day, peak on Saturdays, and jump 2.5× over a holiday weekend, labelled `holiday_rush`.

```json
{
  "seed": 8,
  "profiles": {
    "store": {
      "count": 4,
      "columns": {
        "size": {
          "lognormal": {
            "median": 1,
            "sigma": 0.3
          },
          "per": "store_id",
          "round": 2
        },
        "sales": {
          "constant": 5000,
          "trend": {
            "growth": 0.002,
            "per": "1d"
          },
          "seasonality": [
            {
              "period": "7d",
              "amplitude": 1200,
              "peak": "5d"
            }
          ],
          "multiply_column": "size",
          "noise": {
            "normal": {
              "stddev": 300
            }
          },
          "min": 0,
          "round": 0,
          "anomalies": [
            {
              "name": "holiday_rush",
              "multiply": 2.5,
              "between": [
                "2026-11-27T00:00:00Z",
                "2026-11-30T00:00:00Z"
              ]
            }
          ]
        }
      }
    }
  },
  "rows": {
    "every": "1d",
    "count": 90,
    "start": "2026-10-01T00:00:00Z",
    "one_each": true
  },
  "id_column": "store_id"
}
```

| timestamp | store_id | profile | size | sales | anomaly |
|---|---|---|---|---|---|
| 2026-10-01T00:00:00Z | store_0001 | store | 1.27 | 5724 |  |
| 2026-10-02T00:00:00Z | store_0001 | store | 1.27 | 6925 |  |
| 2026-10-03T00:00:00Z | store_0001 | store | 1.27 | 8041 |  |
| 2026-11-27T00:00:00Z | store_0001 | store | 1.27 | 20430 | holiday_rush |
| 2026-11-27T00:00:00Z | store_0002 | store | 1.27 | 20575 | holiday_rush |

## Service latency with an outage

Request logs at random times over an afternoon. Latencies are exponential, so most are fast with a long tail (median about 83 ms, p99 about 580 ms); `/checkout` is 2.5× slower through a lookup on the endpoint. A 20-minute outage empties the latency of every request in that window.

```json
{
  "seed": 13,
  "common_columns": {
    "endpoint": {
      "categorical": {
        "/search": 0.5,
        "/checkout": 0.2,
        "/profile": 0.3
      }
    },
    "latency_ms": {
      "exponential": {
        "mean": 120
      },
      "multiply_column": {
        "endpoint": {
          "/checkout": 2.5
        }
      },
      "min": 5,
      "round": 1,
      "anomalies": [
        {
          "name": "outage",
          "set": null,
          "between": [
            "2026-02-10T14:00:00Z",
            "2026-02-10T14:20:00Z"
          ]
        }
      ]
    },
    "is_error": {
      "bernoulli": 0.01
    }
  },
  "rows": {
    "count": 3000,
    "between": [
      "2026-02-10T12:00:00Z",
      "2026-02-10T18:00:00Z"
    ]
  }
}
```

| timestamp | endpoint | latency_ms | is_error | anomaly |
|---|---|---|---|---|
| 2026-02-10T12:00:04Z | /checkout | 146.5 | 0 |  |
| 2026-02-10T12:00:15Z | /search | 101.2 | 0 |  |
| 2026-02-10T12:00:33Z | /profile | 187.6 | 0 |  |
| 2026-02-10T14:00:11Z | /search |  | 0 | outage |
| 2026-02-10T14:00:11Z | /search |  | 0 | outage |

## Patients where some columns don't apply

One row per patient. Both groups declare the same columns, but `insulin_units` is `null` for healthy patients: the column exists, it just never has a value for them. Lab results are sometimes missing, more often for healthy patients who are tested less.

```json
{
  "seed": 30,
  "profiles": {
    "healthy": {
      "count": 60,
      "columns": {
        "fasting_glucose": {
          "normal": {
            "mean": 90,
            "stddev": 8
          },
          "round": 0
        },
        "hba1c": {
          "normal": {
            "mean": 5.2,
            "stddev": 0.3
          },
          "round": 1,
          "missing": 0.4
        },
        "insulin_units": null
      }
    },
    "diabetic": {
      "count": 40,
      "columns": {
        "fasting_glucose": {
          "normal": {
            "mean": 160,
            "stddev": 30
          },
          "round": 0
        },
        "hba1c": {
          "normal": {
            "mean": 7.8,
            "stddev": 1.1
          },
          "round": 1,
          "missing": 0.1
        },
        "insulin_units": {
          "poisson": {
            "mean": 30
          }
        }
      }
    }
  },
  "common_columns": {
    "age": {
      "normal": {
        "mean": 55,
        "stddev": 15
      },
      "min": 18,
      "max": 95,
      "round": 0
    },
    "sex": {
      "categorical": [
        "F",
        "M"
      ]
    }
  },
  "rows": {
    "one_each": true
  },
  "id_column": "patient_id",
  "profile_column": "group"
}
```

| patient_id | group | age | sex | fasting_glucose | hba1c | insulin_units |
|---|---|---|---|---|---|---|
| healthy_0001 | healthy | 67 | M | 88 | 5.4 |  |
| healthy_0002 | healthy | 87 | M | 87 | 5.6 |  |
| diabetic_0001 | diabetic | 60 | F | 163 | 8.0 | 33 |
| diabetic_0002 | diabetic | 51 | F | 165 | 7.2 | 28 |
