"""12 — Tabular ML & Deep Learning Lifecycle (UCI Bike Sharing, hourly)."""

__version__ = "0.1.0"

# Import lightgbm before torch: on macOS both bundle/need libomp, and if
# torch's copy loads first, unpickling a fitted LGBMRegressor segfaults in
# Booster.__setstate__ (dual OpenMP runtimes; documented in
# projects/05-ml-pipeline-churn/DESIGN.md). Loading lightgbm's dylib first
# makes dyld share one runtime for both. Every entry into this package goes
# through this __init__, so the order holds for CLI, stages and tests.
import lightgbm as _lightgbm  # noqa: F401
