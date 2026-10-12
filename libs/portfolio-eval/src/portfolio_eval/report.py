"""HTML evaluation report builder: metrics tables + embedded plotly figures."""

import json
from dataclasses import dataclass, field
from pathlib import Path

import plotly.graph_objects as go
from portfolio_core.plotting import save_html

from portfolio_eval.metrics import RunResult

_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{title} — evaluation report</title>
<style>
body {{ font-family: Inter, system-ui, sans-serif; background: #0f172a; color: #e2e8f0;
       max-width: 1100px; margin: 2rem auto; padding: 0 1rem; }}
h1 {{ color: #2dd4bf; }} h2 {{ color: #38bdf8; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #334155; padding: 0.4rem 0.8rem; text-align: left; }}
th {{ background: #1e293b; }}
code {{ background: #1e293b; padding: 0.1rem 0.35rem; border-radius: 4px; }}
</style></head><body>
<h1>{title}</h1>
{sections}
</body></html>
"""


@dataclass
class EvalReport:
    """Assembled report; renders to standalone HTML."""

    title: str
    sections: list[str] = field(default_factory=list)

    def add_markdown_table(self, heading: str, markdown: str) -> None:
        lines = [
            line
            for line in markdown.splitlines()
            if line.strip().startswith("|") and not set(line) <= {"|", "-", " ", ":"}
        ]
        rows: list[str] = []
        for line_no, line in enumerate(lines):
            tag = "th" if line_no == 0 else "td"
            cells = "".join(f"<{tag}>{c.strip()}</{tag}>" for c in line.strip("|").split("|"))
            rows.append(f"<tr>{cells}</tr>")
        self.sections.append(f"<h2>{heading}</h2><table>{''.join(rows)}</table>")

    def add_html(self, heading: str, html: str) -> None:
        self.sections.append(f"<h2>{heading}</h2>{html}")

    def write(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_HTML.format(title=self.title, sections="\n".join(self.sections)))
        return p


@dataclass
class ReportBuilder:
    """Convenience pipeline: runs → markdown table + figures → report + metrics.json."""

    title: str
    runs: list[RunResult] = field(default_factory=list)
    figures_dir: Path = Path("reports/figures")

    def add_run(self, run: RunResult) -> None:
        self.runs.append(run)

    def build(self, out_dir: Path, figures: dict[str, go.Figure] | None = None) -> EvalReport:
        from portfolio_eval.ml import RunComparison

        out_dir.mkdir(parents=True, exist_ok=True)
        report = EvalReport(title=self.title)
        report.add_markdown_table("Metrics", RunComparison(self.runs).to_markdown())
        metrics: dict[str, dict[str, float]] = {}
        for run in self.runs:
            metrics[run.name] = {m.name: m.value for m in run.metrics}
        for name, fig in (figures or {}).items():
            html_path = save_html(fig, self.figures_dir / f"{name}.html")
            report.add_html(
                name.replace("_", " ").title(),
                f'<p><a href="figures/{html_path.name}">interactive figure</a> '
                f"(<code>{html_path.name}</code>)</p>",
            )
        (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
        report.write(out_dir / "report.html")
        return report
