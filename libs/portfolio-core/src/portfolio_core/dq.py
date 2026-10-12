"""Data-quality gates as data, not prints. Failing gates halt the pipeline
loudly: DQGateError with the full report attached (platform.md §Contracts)."""

from pydantic import BaseModel, Field

from portfolio_core.schemas import PortfolioBaseModel


class DQCheck(BaseModel):
    """Result of one data-quality check."""

    name: str
    column: str | None = None
    passed: bool
    metric: float | None = Field(default=None, description="Observed value (e.g. null rate).")
    threshold: float | None = Field(default=None, description="Limit the check enforces.")
    detail: str = ""


class DQGateError(RuntimeError):
    """Raised when any gate fails; carries the persisted report."""

    def __init__(self, report: "DQReport") -> None:
        failed = [c.name for c in report.checks if not c.passed]
        super().__init__(
            f"DQ gates failed: {', '.join(failed)} ({len(failed)} of {len(report.checks)})"
        )
        self.report = report


class DQReport(PortfolioBaseModel):
    """Aggregated, serializable data-quality report."""

    dataset: str
    n_rows: int = Field(ge=0)
    checks: list[DQCheck] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def n_failed(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    def add(self, check: DQCheck) -> None:
        self.checks.append(check)

    def check_null_rate(self, column: str, null_rate: float, max_null_rate: float) -> None:
        self.add(
            DQCheck(
                name="null_rate",
                column=column,
                passed=null_rate <= max_null_rate,
                metric=null_rate,
                threshold=max_null_rate,
                detail=f"null_rate({column})={null_rate:.4f} <= {max_null_rate:.4f}",
            )
        )

    def check_range(
        self, column: str, min_observed: float, max_observed: float, lo: float, hi: float
    ) -> None:
        passed = min_observed >= lo and max_observed <= hi
        self.add(
            DQCheck(
                name="range",
                column=column,
                passed=passed,
                detail=f"{column} in [{min_observed}, {max_observed}] vs allowed [{lo}, {hi}]",
            )
        )

    def check_freshness(self, newest_date: str, min_date: str) -> None:
        passed = newest_date >= min_date
        self.add(
            DQCheck(
                name="freshness",
                passed=passed,
                detail=f"newest={newest_date} >= required {min_date}",
            )
        )

    def raise_if_failed(self) -> None:
        """Halt the pipeline loudly if any gate failed."""
        if not self.passed:
            raise DQGateError(self)

    def to_markdown(self) -> str:
        lines = [
            "| check | column | passed | metric | threshold | detail |",
            "|---|---|---|---|---|---|",
        ]
        for c in self.checks:
            lines.append(
                f"| {c.name} | {c.column or '-'} | {'✅' if c.passed else '❌'} "
                f"| {c.metric if c.metric is not None else '-'} "
                f"| {c.threshold if c.threshold is not None else '-'} | {c.detail} |"
            )
        return "\n".join(lines)
