"""Scheduled smoke test: the same requests as scripts/smoke-test.sh, against the public URL.

CloudWatch Synthetics runs this on a schedule; raising an exception marks the run failed.
"""

import json
import os
import urllib.request

BASE_URL = os.environ["API_URL"].rstrip("/")

CHECKS = [
    ("health", "GET", "/health", None, None),
    ("simple dataset", "GET", "/v1/datasets/simple?rows=3&columns=4&seed=1", None, 3),
    (
        "dataset",
        "POST",
        "/v1/datasets",
        {"seed": 1, "rows": {"count": 5}, "common_columns": {"x": {"normal": {}}}},
        5,
    ),
    (
        "stream window",
        "POST",
        "/v1/streams/window",
        {
            "stream": {"seed": 1, "rows": {"every": "15m"}, "common_columns": {"x": {"normal": {}}}},
            "window": {"from": "2026-03-01T09:00:00Z", "to": "2026-03-01T10:00:00Z"},
        },
        4,
    ),
]


def check(name, method, path, body, expected_rows):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        BASE_URL + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read())
    if expected_rows is not None and len(payload["rows"]) != expected_rows:
        raise AssertionError(f"{name}: expected {expected_rows} rows, got {len(payload['rows'])}")
    print(f"ok   {name}")


def handler(event, context):
    failures = []
    for name, method, path, body, expected_rows in CHECKS:
        try:
            check(name, method, path, body, expected_rows)
        except Exception as error:  # report every failing check, not just the first
            print(f"FAIL {name}: {error}")
            failures.append(name)
    if failures:
        raise RuntimeError(f"failed: {', '.join(failures)}")
