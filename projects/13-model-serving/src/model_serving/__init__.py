"""Model API serving & Docker deployment — experiment 13.

Serves the champion tabular MLP re-derived from experiment 12's committed
recipe: native torch + ONNX Runtime behind a small FastAPI service, an async
load harness, and a multi-stage Docker build.
"""

__version__ = "0.1.0"
