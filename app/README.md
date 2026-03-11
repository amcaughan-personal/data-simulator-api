# Application Runtime

This package contains the Lambda application code for the data simulator API.

## Structure

- `handler.py`
  Lambda entrypoint
- `api/models.py`
  typed request and scenario models
- `api/router.py`
  route resolution and request handling
- `engine/distributions.py`
  primitive distribution sampling and summaries
- `engine/scenario.py`
  scenario generation
- `engine/injectors.py`
  anomaly and benchmark injection logic
- `engine/presets.py`
  built-in preset scenarios
- `requirements.in`
  direct runtime dependencies
- `requirements.txt`
  pinned runtime dependency lockfile

## Current API Surface

- `/health`
- `/v1/distributions/sample`
- `/v1/distributions/generate`
- `/v1/scenarios/sample`
- `/v1/scenarios/generate`
- `/v1/presets`
- `/v1/presets/{preset_id}/generate`

## Sample Requests

### Health

```json
{
  "action": "/health"
}
```

### Distribution Sample

```json
{
  "action": "/v1/distributions/sample",
  "distribution": "normal",
  "parameters": {
    "mean": 10.0,
    "stddev": 2.0
  },
  "seed": 42
}
```

### Distribution Generate

```json
{
  "action": "/v1/distributions/generate",
  "distribution": "normal",
  "parameters": {
    "mean": 10.0,
    "stddev": 2.0
  },
  "count": 5,
  "seed": 42,
  "summary": true
}
```

### Scenario Sample

`/v1/scenarios/sample` returns one event and only accepts stateless injectors. Right now that means rate-based selection with any supported mutation.

```json
{
  "action": "/v1/scenarios/sample",
  "name": "simple_sample",
  "seed": 11,
  "time": {
    "frequency_seconds": 60
  },
  "fields": [
    {
      "name": "value",
      "generator": {
        "kind": "distribution",
        "distribution": "normal",
        "parameters": {
          "mean": 5.0,
          "stddev": 1.0
        }
      }
    }
  ],
  "injectors": [
    {
      "injector_id": "always_scale",
      "field": "value",
      "selection": {
        "kind": "rate",
        "rate": 1.0
      },
      "mutation": {
        "kind": "scale",
        "factor": 2.0
      }
    }
  ]
}
```

### Scenario Generate

```json
{
  "action": "/v1/scenarios/generate",
  "name": "simple_generate",
  "seed": 11,
  "row_count": 100,
  "time": {
    "frequency_seconds": 60
  },
  "fields": [
    {
      "name": "value",
      "generator": {
        "kind": "distribution",
        "distribution": "normal",
        "parameters": {
          "mean": 5.0,
          "stddev": 1.0
        }
      }
    },
    {
      "name": "status",
      "generator": {
        "kind": "categorical",
        "values": ["ok", "warn"],
        "weights": [0.8, 0.2]
      }
    }
  ],
  "injectors": [
    {
      "injector_id": "random_spikes",
      "field": "value",
      "selection": {
        "kind": "rate",
        "rate": 0.03
      },
      "mutation": {
        "kind": "scale",
        "factor": 10.0
      }
    }
  ]
}
```

### List Presets

```json
{
  "action": "/v1/presets"
}
```

### Preset Generate

```json
{
  "action": "/v1/presets/transaction_benchmark/generate",
  "seed": 3,
  "row_count": 12,
  "overrides": {
    "anomaly_rate": 0.08,
    "regime_start_index": 6
  }
}
```

### Lambda Invoke Example

```bash
aws lambda invoke \
  --function-name data-simulator-api-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{"action":"/v1/distributions/generate","distribution":"normal","parameters":{"mean":10.0,"stddev":2.0},"count":5,"seed":42,"summary":true}' \
  /tmp/data-simulator-sample.json
```

## Design Notes

- `handler.py` should stay thin.
- request validation belongs in `api`
- simulation logic belongs in `engine`
- preset definitions should compose the engine rather than bypass it
