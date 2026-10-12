"""portfolio-eval: reusable evaluation harness (ML + RAG)."""

from portfolio_eval.metrics import Metric, MetricResult, compare_runs
from portfolio_eval.report import EvalReport, ReportBuilder

__all__ = ["EvalReport", "Metric", "MetricResult", "ReportBuilder", "compare_runs"]
__version__ = "0.1.0"
