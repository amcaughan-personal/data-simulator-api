"""Generate realistic synthetic datasets from a small JSON spec."""

from data_simulator.engine import generate
from data_simulator.spec import DatasetSpec

__all__ = ["DatasetSpec", "generate"]
