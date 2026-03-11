import json
import os
from datetime import datetime, timezone


def _json_response(status_code: int, payload: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def handler(event, context):
    event = event or {}

    route = event.get("rawPath") or event.get("path") or event.get("action") or "health"

    if route in ("/health", "health"):
        return _json_response(
            200,
            {
                "status": "ok",
                "service": "data-simulator-api",
                "environment": os.getenv("ENVIRONMENT", "unknown"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    if route in ("/simulate", "simulate"):
        return _json_response(
            200,
            {
                "status": "ok",
                "series": [0.1, 0.5, 0.9],
                "count": 3,
                "note": "dummy payload",
            },
        )

    return _json_response(
        404,
        {
            "status": "error",
            "message": f"unknown route: {route}",
        },
    )
