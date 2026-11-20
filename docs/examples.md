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
  "seed": 34,
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

The first 10 rows:

| timestamp | card_id | card_type | channel | amount | items | declined |
|---|---|---|---|---|---|---|
| 2026-03-01T00:43:13Z | premium_card_0006 | premium_card | in_store | 35.37 | 6 | 0 |
| 2026-03-01T03:09:27Z | standard_card_0030 | standard_card | in_store | 40.98 | 2 | 0 |
| 2026-03-01T03:16:53Z | standard_card_0021 | standard_card | in_store | 41.0 | 1 | 0 |
| 2026-03-01T05:19:05Z | standard_card_0020 | standard_card | in_store | 16.94 | 1 | 1 |
| 2026-03-01T05:26:02Z | standard_card_0029 | standard_card | in_store | 84.43 | 3 | 0 |
| 2026-03-01T06:14:11Z | premium_card_0002 | premium_card | online | 92.47 | 2 | 0 |
| 2026-03-01T07:09:57Z | standard_card_0016 | standard_card | online | 36.89 | 1 | 0 |
| 2026-03-01T08:40:25Z | premium_card_0003 | premium_card | online | 66.39 | 3 | 0 |
| 2026-03-01T08:50:14Z | standard_card_0010 | standard_card | online | 11.45 | 4 | 0 |
| 2026-03-01T09:01:15Z | standard_card_0032 | standard_card | in_store | 128.93 | 3 | 0 |

## One row per institution

Three profiles with their own size distributions; `one_each` gives one row per individual.

```json
{
  "seed": 1,
  "profiles": {
    "bank":         {"count": 12, "columns": {"employees": {"lognormal": {"median": 1000, "sigma": 0.9}, "round": 0}, "is_public": {"bernoulli": 0.5}}},
    "credit_union": {"count": 8,  "columns": {"employees": {"lognormal": {"median": 160, "sigma": 0.7}, "round": 0},  "is_public": {"constant": 0}}},
    "insurer":      {"count": 5,  "columns": {"employees": {"lognormal": {"median": 400, "sigma": 0.9}, "round": 0},  "is_public": {"bernoulli": 0.4}}}
  },
  "common_columns": {"region": {"categorical": ["west", "midwest", "south", "northeast"]}},
  "rows": {"one_each": true}
}
```

10 of the 25 rows, from each kind of institution:

| id | profile | region | employees | is_public |
|---|---|---|---|---|
| bank_0001 | bank | northeast | 1649 | 1 |
| bank_0002 | bank | midwest | 4562 | 1 |
| bank_0003 | bank | west | 524 | 0 |
| bank_0004 | bank | northeast | 1108 | 0 |
| credit_union_0001 | credit_union | west | 276 | 0 |
| credit_union_0002 | credit_union | south | 253 | 0 |
| credit_union_0003 | credit_union | south | 126 | 0 |
| insurer_0001 | insurer | northeast | 335 | 1 |
| insurer_0002 | insurer | midwest | 911 | 0 |
| insurer_0003 | insurer | midwest | 404 | 1 |

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

All five sensors at 11:00 and 12:00, when the outdoor heatwave starts:

| timestamp | id | profile | calibration_offset | temperature_c | anomaly |
|---|---|---|---|---|---|
| 2026-01-01T11:00:00Z | indoor_0001 | indoor | -0.05 |  | sensor_dead |
| 2026-01-01T11:00:00Z | indoor_0002 | indoor | -0.24 | 20.67 |  |
| 2026-01-01T11:00:00Z | indoor_0003 | indoor | -0.51 | 20.52 |  |
| 2026-01-01T11:00:00Z | outdoor_0001 | outdoor | 0.27 | 14.31 |  |
| 2026-01-01T11:00:00Z | outdoor_0002 | outdoor | -0.17 | 13.85 |  |
| 2026-01-01T12:00:00Z | indoor_0001 | indoor | -0.05 | 20.7 |  |
| 2026-01-01T12:00:00Z | indoor_0002 | indoor | -0.24 | 20.66 |  |
| 2026-01-01T12:00:00Z | indoor_0003 | indoor | -0.51 | 20.57 |  |
| 2026-01-01T12:00:00Z | outdoor_0001 | outdoor | 0.27 | 23.68 | heatwave |
| 2026-01-01T12:00:00Z | outdoor_0002 | outdoor | -0.17 | 23.8 | heatwave |

## Web traffic with growth and cycles

One time series, no profiles: growing 1% a day, busiest at 2pm and midweek, with whole-number counts.

```json
{
  "seed": 1,
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

The first day from 08:00 to 17:00, rising to the afternoon peak:

| timestamp | page_views |
|---|---|
| 2026-03-02T08:00:00Z | 1048 |
| 2026-03-02T09:00:00Z | 1079 |
| 2026-03-02T10:00:00Z | 1185 |
| 2026-03-02T11:00:00Z | 1262 |
| 2026-03-02T12:00:00Z | 1308 |
| 2026-03-02T13:00:00Z | 1372 |
| 2026-03-02T14:00:00Z | 1481 |
| 2026-03-02T15:00:00Z | 1450 |
| 2026-03-02T16:00:00Z | 1459 |
| 2026-03-02T17:00:00Z | 1287 |

## Card fraud as a rare profile

Fraud isn't a tweak to normal transactions; it's a different kind of behaviour. Here it's a profile drawn for 1% of rows, with large amounts, night-time hours and mostly foreign merchants, while a few normal cards account for most activity (`skewed`). The `label` column is the ground truth a fraud model would train on.

```json
{
  "seed": 2,
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

7 normal and 3 fraudulent transactions:

| card_id | label | merchant_type | amount | hour | is_foreign |
|---|---|---|---|---|---|
| normal_0452 | normal | online | 200.74 | 19 | 0 |
| normal_0187 | normal | online | 166.46 | 17 | 0 |
| normal_0029 | normal | online | 18.8 | 18 | 0 |
| normal_0495 | normal | retail | 38.54 | 12 | 0 |
| normal_0013 | normal | retail | 30.3 | 11 | 0 |
| normal_0208 | normal | online | 39.37 | 14 | 0 |
| normal_0262 | normal | retail | 66.02 | 12 | 0 |
| fraud_0004 | fraud | grocery | 211.69 | 3 | 1 |
| fraud_0002 | fraud | retail | 468.15 | 4 | 1 |
| fraud_0002 | fraud | online | 727.6 | 4 | 1 |

## Survey responses

The simplest kind of dataset: no profiles and no time, just independent rows. Scores are a bell curve clipped to 1–10 and rounded, and 30% of respondents left no comment.

```json
{
  "seed": 1,
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

The first 10 responses:

| response_id | age_group | satisfaction | would_recommend | comment_length |
|---|---|---|---|---|
| 1001 | 65+ | 6 | 1 | 3 |
| 1002 | 45-64 | 8 | 1 | 16 |
| 1003 | 18-29 | 5 | 1 | 123 |
| 1004 | 18-29 | 7 | 1 | 76 |
| 1005 | 18-29 | 9 | 0 | 114 |
| 1006 | 18-29 | 8 | 1 |  |
| 1007 | 18-29 | 9 | 0 |  |
| 1008 | 30-44 | 10 | 0 |  |
| 1009 | 45-64 | 6 | 1 | 30 |
| 1010 | 18-29 | 9 | 1 | 23 |

## Daily sales per store

A daily series for each of 4 stores. Each store gets a size fixed for its whole history (`"per": "store_id"`) that its sales multiply by. Sales grow 0.2% a day, peak on Saturdays, and jump 2.5× over a holiday weekend, labelled `holiday_rush`.

```json
{
  "seed": 2,
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

All four stores the day before and the first days of the holiday rush:

| timestamp | store_id | profile | size | sales | anomaly |
|---|---|---|---|---|---|
| 2026-11-26T00:00:00Z | store_0001 | store | 1.26 | 6933 |  |
| 2026-11-26T00:00:00Z | store_0002 | store | 0.94 | 4902 |  |
| 2026-11-26T00:00:00Z | store_0003 | store | 0.65 | 3984 |  |
| 2026-11-26T00:00:00Z | store_0004 | store | 0.86 | 4942 |  |
| 2026-11-27T00:00:00Z | store_0001 | store | 1.26 | 20292 | holiday_rush |
| 2026-11-27T00:00:00Z | store_0002 | store | 0.94 | 14890 | holiday_rush |
| 2026-11-27T00:00:00Z | store_0003 | store | 0.65 | 11600 | holiday_rush |
| 2026-11-27T00:00:00Z | store_0004 | store | 0.86 | 12918 | holiday_rush |
| 2026-11-28T00:00:00Z | store_0001 | store | 1.26 | 22750 | holiday_rush |
| 2026-11-28T00:00:00Z | store_0002 | store | 0.94 | 17300 | holiday_rush |

## Service latency with an outage

Request logs at random times over an afternoon. Latencies are exponential, so most are fast with a long tail (median about 83 ms, p99 about 580 ms); `/checkout` is 2.5× slower through a lookup on the endpoint. A 20-minute outage empties the latency of every request in that window.

```json
{
  "seed": 2,
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

The 10 requests around the start of the outage:

| timestamp | endpoint | latency_ms | is_error | anomaly |
|---|---|---|---|---|
| 2026-02-10T13:59:38Z | /checkout | 220.1 | 0 |  |
| 2026-02-10T13:59:48Z | /profile | 309.7 | 0 |  |
| 2026-02-10T13:59:53Z | /profile | 98.7 | 0 |  |
| 2026-02-10T13:59:55Z | /search | 94.5 | 0 |  |
| 2026-02-10T13:59:56Z | /profile | 20.8 | 0 |  |
| 2026-02-10T14:00:03Z | /checkout |  | 0 | outage |
| 2026-02-10T14:00:04Z | /search |  | 0 | outage |
| 2026-02-10T14:00:08Z | /search |  | 0 | outage |
| 2026-02-10T14:00:24Z | /profile |  | 1 | outage |
| 2026-02-10T14:00:25Z | /search |  | 0 | outage |

## Patients where some columns don't apply

One row per patient. Both groups declare the same columns, but `insulin_units` is `null` for healthy patients: the column exists, it just never has a value for them. Lab results are sometimes missing, more often for healthy patients who are tested less.

```json
{
  "seed": 9,
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

5 healthy and 5 diabetic patients:

| patient_id | group | age | sex | fasting_glucose | hba1c | insulin_units |
|---|---|---|---|---|---|---|
| healthy_0001 | healthy | 42 | F | 97 | 5.5 |  |
| healthy_0002 | healthy | 62 | M | 73 | 5.4 |  |
| healthy_0003 | healthy | 63 | F | 81 | 5.3 |  |
| healthy_0004 | healthy | 49 | M | 96 |  |  |
| healthy_0005 | healthy | 18 | M | 78 | 4.9 |  |
| diabetic_0001 | diabetic | 40 | M | 169 | 8.3 | 21 |
| diabetic_0002 | diabetic | 73 | M | 103 | 8.4 | 21 |
| diabetic_0003 | diabetic | 46 | M | 163 | 5.8 | 35 |
| diabetic_0004 | diabetic | 62 | M | 138 | 8.6 | 28 |
| diabetic_0005 | diabetic | 54 | F | 148 | 6.7 | 33 |
