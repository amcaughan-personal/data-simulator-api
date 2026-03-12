#!/usr/bin/env bash

set -euo pipefail

FUNCTION_NAME="${1:-data-simulator-api-dev}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

invoke_lambda() {
  local name="$1"
  local payload="$2"
  local output_file="$TMP_DIR/${name}.json"

  aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --cli-binary-format raw-in-base64-out \
    --payload "$payload" \
    "$output_file" \
    >/dev/null

  echo "$output_file"
}

assert_json() {
  local output_file="$1"
  local label="$2"
  local assertion="$3"

  python3 - "$output_file" "$label" "$assertion" <<'PY'
import json
import sys

output_path, label, assertion = sys.argv[1:4]

with open(output_path, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

namespace = {"json": json, "payload": payload}
safe_builtins = {"len": len}
if not eval(assertion, {"__builtins__": safe_builtins}, namespace):
    print(f"{label} failed")
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(1)

print(f"{label} passed")
PY
}

echo "Running Lambda smoke tests against ${FUNCTION_NAME}"

health_output="$(invoke_lambda "health" '{"action":"/health"}')"
assert_json "$health_output" "health" \
  'payload["statusCode"] == 200 and json.loads(payload["body"])["status"] == "ok"'

distribution_output="$(invoke_lambda "distribution_generate" '{
  "action": "/v1/distributions/generate",
  "distribution": "normal",
  "parameters": {
    "mean": 10.0,
    "stddev": 2.0
  },
  "count": 5,
  "seed": 42,
  "summary": true
}')"
assert_json "$distribution_output" "distribution_generate" \
  'payload["statusCode"] == 200 and (lambda body: body["count"] == 5 and len(body["samples"]) == 5 and "summary" in body)(json.loads(payload["body"]))'

scenario_sample_output="$(invoke_lambda "scenario_sample" '{
  "action": "/v1/scenarios/sample",
  "name": "smoke_sample",
  "seed": 11,
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
  "mutations": [
    {
      "mutation_id": "always_scale",
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
}')"
assert_json "$scenario_sample_output" "scenario_sample" \
  'payload["statusCode"] == 200 and (lambda body: body["scenario_name"] == "smoke_sample" and body["row"]["__is_anomaly"] is True)(json.loads(payload["body"]))'

preset_generate_output="$(invoke_lambda "preset_generate" '{
  "action": "/v1/presets/transaction_benchmark/generate",
  "seed": 7,
  "row_count": 10,
  "overrides": {
    "anomaly_rate": 0.2,
    "regime_start_index": 5
  }
}')"
assert_json "$preset_generate_output" "preset_generate" \
  'payload["statusCode"] == 200 and (lambda body: body["scenario_name"] == "transaction_benchmark" and body["row_count"] == 10 and "amount" in body["fields"])(json.loads(payload["body"]))'

echo "All Lambda smoke tests passed"
