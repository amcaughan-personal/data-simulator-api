import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.api.models import DistributionSampleRequest
from app.engine.distributions import build_distribution_response


class DistributionEngineTest(unittest.TestCase):
    def test_normal_distribution_response_is_deterministic(self):
        request = DistributionSampleRequest(
            distribution="normal",
            parameters={"mean": 10.0, "stddev": 2.0},
            count=3,
            seed=42,
            summary=True,
        )

        payload = build_distribution_response(request)

        self.assertEqual(payload["distribution"], "normal")
        self.assertEqual(payload["count"], 3)
        self.assertEqual(payload["seed"], 42)
        self.assertEqual(len(payload["samples"]), 3)
        self.assertIn("summary", payload)
        self.assertIn("mean", payload["summary"])

    def test_categorical_distribution_returns_requested_values(self):
        request = DistributionSampleRequest(
            distribution="categorical",
            parameters={"values": ["a", "b"], "weights": [0.75, 0.25]},
            count=10,
            seed=7,
            summary=True,
        )

        payload = build_distribution_response(request)

        self.assertTrue(all(value in {"a", "b"} for value in payload["samples"]))
        self.assertIn("value_counts", payload["summary"])


if __name__ == "__main__":
    unittest.main()
