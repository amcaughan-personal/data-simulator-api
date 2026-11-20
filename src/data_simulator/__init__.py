"""Generate realistic synthetic datasets from a small JSON spec."""

from data_simulator.engine import generate, generate_window
from data_simulator.spec import DatasetSpec, StreamSpec, StreamWindowRequest, Window

__all__ = ["DatasetSpec", "StreamSpec", "StreamWindowRequest", "Window", "generate", "generate_window"]
