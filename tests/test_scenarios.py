import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.api.models import PresetPreviewRequest, ScenarioPreviewRequest
from app.api.router import handle_request
from app.engine.presets import build_preset_preview
from app.engine.scenario import preview_scenario


class ScenarioEngineTest(unittest.TestCase):
    def test_preview_scenario_applies_labels(self):
        request = ScenarioPreviewRequest.model_validate(
            {
                "name": "simple_preview",
                "seed": 11,
                "row_count": 6,
                "time": {"frequency_seconds": 60},
                "fields": [
                    {
                        "name": "value",
                        "generator": {
                            "kind": "distribution",
                            "distribution": "normal",
                            "parameters": {"mean": 5.0, "stddev": 1.0},
                        },
                    }
                ],
                "injectors": [
                    {
                        "kind": "point_spike",
                        "injector_id": "spike_1",
                        "field": "value",
                        "index": 2,
                        "scale": 10.0,
                    }
                ],
            }
        )

        payload = preview_scenario(request)

        self.assertEqual(payload["scenario_name"], "simple_preview")
        self.assertEqual(payload["row_count"], 6)
        self.assertEqual(payload["label_summary"]["anomalous_rows"], 1)
        self.assertTrue(payload["rows"][2]["__is_anomaly"])
        self.assertEqual(payload["rows"][2]["__labels"][0]["injector_id"], "spike_1")

    def test_preset_preview_builds_rows(self):
        request = build_preset_preview(
            "transaction_benchmark",
            PresetPreviewRequest(seed=3, row_count=12, overrides={}),
        )

        payload = preview_scenario(request)

        self.assertEqual(payload["scenario_name"], "transaction_benchmark")
        self.assertEqual(payload["row_count"], 12)
        self.assertIn("amount", payload["fields"])

    def test_handler_routes_scenario_preview(self):
        event = {
            "action": "scenario_preview",
            "name": "handler_preview",
            "seed": 9,
            "row_count": 3,
            "time": {"frequency_seconds": 60},
            "fields": [
                {
                    "name": "status",
                    "generator": {
                        "kind": "categorical",
                        "values": ["ok", "warn"],
                        "weights": [0.8, 0.2],
                    },
                }
            ],
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(payload["scenario_name"], "handler_preview")
        self.assertEqual(len(payload["rows"]), 3)

    def test_handler_routes_preset_preview(self):
        event = {
            "action": "preset_preview",
            "preset_id": "iot_sensor_benchmark",
            "seed": 5,
            "row_count": 8,
        }

        response = handle_request(event)
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(payload["scenario_name"], "iot_sensor_benchmark")
        self.assertEqual(len(payload["rows"]), 8)


if __name__ == "__main__":
    unittest.main()
