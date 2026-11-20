#!/usr/bin/env bash
# Check that a deployed API answers its main endpoints:
#
#   scripts/smoke-test.sh https://example.cloudfront.net
set -euo pipefail

base_url="${1%/}"
failures=0

check() {
  local name="$1" expected_rows="$2"
  shift 2
  local body status
  body=$(mktemp)
  status=$(curl -sS -o "$body" -w '%{http_code}' --max-time 20 "$@")
  if [[ "$status" != 200 ]]; then
    echo "FAIL $name: HTTP $status: $(head -c 300 "$body")"
    failures=$((failures + 1))
  elif [[ "$expected_rows" != - ]] && [[ "$(jq '.rows | length' "$body")" != "$expected_rows" ]]; then
    echo "FAIL $name: expected $expected_rows rows"
    failures=$((failures + 1))
  else
    echo "ok   $name"
  fi
  rm -f "$body"
}

check "health" - "$base_url/health"
check "simple dataset" 3 "$base_url/v1/datasets/simple?rows=3&columns=4&seed=1"
check "dataset" 5 -X POST "$base_url/v1/datasets" -H 'Content-Type: application/json' \
  -d '{"seed": 1, "rows": {"count": 5}, "common_columns": {"x": {"normal": {}}}}'
check "stream window" 4 -X POST "$base_url/v1/streams/window" -H 'Content-Type: application/json' \
  -d '{"stream": {"seed": 1, "rows": {"every": "15m"}, "common_columns": {"x": {"normal": {}}}},
       "window": {"from": "2026-03-01T09:00:00Z", "to": "2026-03-01T10:00:00Z"}}'

if ((failures > 0)); then
  echo "$failures smoke test(s) failed against $base_url" >&2
  exit 1
fi
