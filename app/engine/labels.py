from __future__ import annotations

from collections.abc import Sequence
from typing import Any


LABELS_KEY = "__labels"
IS_ANOMALY_KEY = "__is_anomaly"


def initialize_labels(rows: Sequence[dict[str, Any]]) -> None:
    for row in rows:
        row[IS_ANOMALY_KEY] = False
        row[LABELS_KEY] = []


def add_label(row: dict[str, Any], label: dict[str, Any]) -> None:
    row[IS_ANOMALY_KEY] = True
    row[LABELS_KEY].append(label)


def summarize_labels(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    total_anomalous_rows = 0
    anomaly_counts: dict[str, int] = {}

    for row in rows:
        labels = row.get(LABELS_KEY, [])
        if labels:
            total_anomalous_rows += 1
        for label in labels:
            anomaly_type = label["anomaly_type"]
            anomaly_counts[anomaly_type] = anomaly_counts.get(anomaly_type, 0) + 1

    return {
        "anomalous_rows": total_anomalous_rows,
        "anomaly_counts": anomaly_counts,
    }
