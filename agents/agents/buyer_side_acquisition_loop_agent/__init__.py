"""Independent, runnable buyer-side acquisition loop agent."""

from .full_pipeline import run_full_pipeline
from .runtime import run_case

__all__ = ["run_case", "run_full_pipeline"]
