"""Independent P1 single-JD understanding, without legacy stages or services."""
from .runtime import understand

analyze = understand

__all__ = ["analyze", "understand"]
