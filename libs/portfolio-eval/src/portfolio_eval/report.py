"""HTML evaluation report builder: metrics tables + embedded interactive figures.

Reports are served from the repository (``GET /projects/{id}/report``) and the
sibling ``figures/*.html`` files are gitignored — a report that only *links*
them ships dead links in production. Figures are therefore embedded as Plotly
divs (the plotly.js bundle loaded from CDN once per report), which keeps every
committed report.html self-contained and interactive."""

import html as html_mod
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import plotly.graph_objects as go
import yaml  # type: ignore[import-untyped]
from portfolio_core.plotting import save_html

from portfolio_eval.metrics import MetricResult, RunResult

_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — evaluation report</title>
<style>
body {{ font-family: Inter, system-ui, sans-serif; background: #0f172a; color: #e2e8f0;
       max-width: 1100px; margin: 2rem auto; padding: 0 1rem; }}
h1 {{ color: #2dd4bf; }} h2 {{ color: #38bdf8; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #334155; padding: 0.4rem 0.8rem; text-align: left; }}
th {{ background: #1e293b; }}
code {{ background: #1e293b; padding: 0.1rem 0.35rem; border-radius: 4px; }}
.mermaid {{ background: #f8fafc; border-radius: 8px; padding: 1rem; margin: 0.5rem 0;
           overflow-x: auto; }}
</style>
<script type="module">
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.js";
mermaid.initialize({{ startOnLoad: true, theme: "neutral" }});
</script>
</head><body>
<h1>{title}</h1>
{sections}
</body></html>
"""

_MERMAID_FENCE_RE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)


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

    def add_figure(
        self,
        heading: str,
        fig: go.Figure,
        *,
        include_plotlyjs: bool,
        caption: str | None = None,
    ) -> None:
        """Embed a Plotly figure as an interactive div (CDN bundle only on the
        first figure of the report), with an optional lead-in caption."""
        div = fig.to_html(
            full_html=False,
            include_plotlyjs="cdn" if include_plotlyjs else False,
            config={"displaylogo": False},
        )
        lead = f"<p>{caption}</p>" if caption else ""
        self.add_html(heading, lead + div)

    def add_mermaid(self, heading: str, code: str) -> None:
        """Embed a Mermaid diagram; rendered client-side by the CDN module."""
        self.add_html(heading, f'<pre class="mermaid">{html_mod.escape(code)}</pre>')

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
        first_plotly = True
        for name, fig in (figures or {}).items():
            # The standalone .html stays on disk for the API figure route; the
            # report itself embeds the div so committed reports self-contain.
            save_html(fig, self.figures_dir / f"{name}.html")
            report.add_figure(name.replace("_", " ").title(), fig, include_plotlyjs=first_plotly)
            first_plotly = False
        (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
        report.write(out_dir / "report.html")
        return report


# --- offline rebuild from committed artifacts -----------------------------------


def runs_from_metrics(reports_dir: Path) -> list[RunResult]:
    """Reconstruct RunResults from a committed metrics.json (run → metrics map)."""
    metrics = json.loads((Path(reports_dir) / "metrics.json").read_text(encoding="utf-8"))
    runs: list[RunResult] = []
    for name, values in metrics.items():
        if name.startswith("_") or name == "detail" or not isinstance(values, dict):
            continue
        runs.append(
            RunResult(
                name=name,
                metrics=[
                    MetricResult(name=k, value=v)
                    for k, v in values.items()
                    if isinstance(v, (int, float)) and not isinstance(v, bool)
                ],
            )
        )
    return runs


def figures_from_json(figures_dir: Path) -> dict[str, go.Figure]:
    """Load committed Plotly JSON payloads back as Figures (offline rebuild)."""
    figs: dict[str, go.Figure] = {}
    for f in sorted(Path(figures_dir).glob("*.json")):
        figs[f.stem] = go.Figure(json.loads(f.read_text(encoding="utf-8")))
    return figs


def mermaid_blocks_from_story(project_dir: Path) -> dict[str, str]:
    """Extract ```mermaid diagrams from a project's story.yaml, keyed by a
    display heading (``{section}: diagram n``). Lets a report carry the same
    diagrams as the case study without hand-duplicating them."""
    story_path = Path(project_dir) / "story.yaml"
    if not story_path.exists():
        return {}
    data = yaml.safe_load(story_path.read_text(encoding="utf-8"))
    blocks: dict[str, str] = {}
    for section in data.get("sections", []):
        text = section.get("text_md") or ""
        for i, m in enumerate(_MERMAID_FENCE_RE.finditer(text), 1):
            heading = f"{section['id']} diagram {i}"
            blocks[heading] = m.group(1).strip()
    return blocks
