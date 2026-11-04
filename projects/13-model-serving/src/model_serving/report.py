"""Report stage: assemble metrics.json + evaluation_metadata.json + report.

Pure assembly over committed stage artifacts (train_run.json, bench_run.json,
docker_run.json) — no retraining, no re-scoring, the same discipline as 08/12.
The electricity cost framing follows experiment 08: measured throughput,
declared wattage, $/kWh assumption.
"""

import json
import os
import platform
from pathlib import Path
from typing import Any

import numpy as np
from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_html, save_json
from portfolio_eval.report import EvalReport, figures_from_json, mermaid_blocks_from_story

import model_serving
from model_serving.config import ServingConfig
from model_serving.figures import build_figures

log = get_logger(__name__)

REPORT_TITLE = "13 — Model API Serving & Docker Deployment (champion MLP, UCI Bike Sharing)"

LIMITS = [
    "Single laptop, no GPU, one uvicorn worker, one model: absolute numbers "
    "do not transfer; the paired native-vs-ONNX deltas and the shape of the "
    "curves are the transferable read.",
    "The load driver runs on the same machine as the service — localhost "
    "latency has no network term, and the CPU is shared between driver and "
    "service under high concurrency.",
    "Fresh-process RSS is the steady state after warm-up, not a peak under "
    "load; the image size is the uncompressed on-disk total.",
    "Cost per 1k predictions uses measured throughput with a declared 65 W "
    "system draw (no wall meter) and $0.30 per kWh — an assumption, stated "
    "next to the number, not a measurement.",
]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{path} missing — run the earlier stages first")
    payload: dict[str, Any] = json.loads(path.read_text())
    return payload


def cost_per_1k_usd(throughput_rps: float, cfg: ServingConfig) -> float:
    """Electricity per 1k predictions: measured rps, declared watts + $/kWh."""
    hours_per_1k = 1000.0 / throughput_rps / 3600.0
    return hours_per_1k * cfg.cost.system_load_watts / 1000.0 * cfg.cost.usd_per_kwh


def assemble_metrics(cfg: ServingConfig) -> dict[str, Any]:
    """Merge the stage artifacts into the committed metrics.json shape."""
    train = _read_json(cfg.reports_dir / "train_run.json")
    bench = _read_json(cfg.data_dir / "bench_run.json")
    docker = _read_json(cfg.reports_dir / "docker_run.json")

    serving: dict[str, Any] = {}
    for backend, block in bench["backends"].items():
        serving[backend] = {
            "concurrency": block["concurrency"],
            "batch": block["batch"],
            "rss_mb": block["rss_mb"],
        }
    knee = f"c{cfg.bench.concurrency_levels[min(2, len(cfg.bench.concurrency_levels) - 1)]}"
    cost = {
        "usd_per_kwh": cfg.cost.usd_per_kwh,
        "system_load_watts": cfg.cost.system_load_watts,
        "throughput_basis": (
            f"median-of-repeats throughput at concurrency {knee[1:]} "
            f"(the saturation knee on this host)"
        ),
        "cost_per_1k_predictions_usd": {
            backend: cost_per_1k_usd(serving[backend]["concurrency"][knee]["throughput_rps"], cfg)
            for backend in serving
        },
    }
    return {
        "champion": train["champion"],
        "reproduction": train["reproduction"],
        "parity": train["parity"],
        "selection": train["selection"],
        "example_row": train["example_row"],
        "serving": serving,
        "docker": docker,
        "cost": cost,
        "bench_protocol": {
            "seed": bench["seed"],
            "concurrency_levels": bench["concurrency_levels"],
            "requests_per_concurrency": bench["requests_per_concurrency"],
            "warmup_requests_excluded": bench["warmup_requests"],
            "repeats_median_of": bench["repeats"],
            "batch_sizes": bench["batch_sizes"],
            "batch_requests_per_size": bench["batch_requests_per_size"],
            "rss_probes": len(bench["backends"]["native"]["rss_mb"]["probes"]),
            "paired_payloads": (
                "both backends see byte-identical request streams (seeded probe grid)"
            ),
            "bench_runtime_s": bench["bench_runtime_s"],
        },
        "_meta": {
            "limits": LIMITS,
            "stages": {
                "train_runtime_s": train["train_runtime_s"],
                "bench_runtime_s": bench["bench_runtime_s"],
                "docker_runtime_s": docker.get("docker_runtime_s"),
            },
        },
    }


def _versions() -> dict[str, str]:
    import fastapi
    import onnx
    import onnxruntime  # type: ignore[import-untyped]  # onnxruntime ships no stubs
    import pandas
    import plotly
    import sklearn
    import torch
    import uvicorn

    return {
        "python": platform.python_version(),
        "model_serving": model_serving.__version__,
        "torch": torch.__version__,
        "onnx": onnx.__version__,
        "onnxruntime": onnxruntime.__version__,
        "fastapi": fastapi.__version__,
        "uvicorn": uvicorn.__version__,
        "scikit-learn": sklearn.__version__,
        "plotly": plotly.__version__,
        "pandas": pandas.__version__,
        "numpy": np.__version__,
    }


def build_evaluation_metadata(cfg: ServingConfig, metrics: dict[str, Any]) -> dict[str, Any]:
    """The evaluation_metadata.json record (protocol, versions, hardware)."""
    return {
        "protocol": (
            "Champion re-derivation: experiment 12's committed recipe (same sha256-pinned "
            "UCI hour.csv, same feature contract, same MLP architecture + hyperparameters, "
            "seed 42), scored once on the frozen 8-week test window; reproduction gate "
            "|ΔMAE| ≤ params reproduction_tolerance. Serving: native torch vs ONNX Runtime "
            "behind one FastAPI service, warmed at startup; parity gate on a seeded probe "
            "grid (max-abs, standardized-y space) before any serving stage may run. "
            "Benchmark: real subprocess service per backend, warm-up excluded, ~300 "
            "requests per concurrency cell (1/4/16/64), median of 3 repeats, batch sizes "
            "1/8/32/128, fresh-process RSS probes, byte-identical seeded payload streams. "
            "Docker: multi-stage build from the repo-root context, model baked in, image "
            "size + layer breakdown measured with the daemon, compose smoke against "
            "/health /ready /predict."
        ),
        "seed": cfg.seed,
        "versions": _versions(),
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count() or 0,
        },
        "limits": LIMITS,
    }


def _latency_table(metrics: dict[str, Any]) -> str:
    lines = [
        "| backend | concurrency | p50 s | p95 s | p99 s | throughput req/s | errors |",
        "|---|---|---|---|---|---|---|",
    ]
    for backend in ("native", "onnx"):
        cells = metrics["serving"][backend]["concurrency"]
        for cell in cells.values():
            lines.append(
                f"| {backend} | {cell['cell'][1:]} | {cell['p50_s']:.4f} | "
                f"{cell['p95_s']:.4f} | {cell['p99_s']:.4f} | "
                f"{cell['throughput_rps']:.1f} | {cell['n_requests'] * cell['error_rate']:.0f}/"
                f"{cell['n_requests']} |"
            )
    return "\n".join(lines)


def _batch_table(metrics: dict[str, Any]) -> str:
    lines = [
        "| backend | batch size | p50 s/request | throughput rows/s | errors |",
        "|---|---|---|---|---|",
    ]
    for backend in ("native", "onnx"):
        cells = metrics["serving"][backend]["batch"]
        for cell in cells.values():
            lines.append(
                f"| {backend} | {cell['cell'][1:]} | {cell['p50_s']:.4f} | "
                f"{cell['throughput_rps']:.1f} | "
                f"{cell['n_requests'] * cell['error_rate']:.0f}/{cell['n_requests']} |"
            )
    return "\n".join(lines)


def _footprint_table(metrics: dict[str, Any]) -> str:
    docker = metrics["docker"]
    rss = {b: metrics["serving"][b]["rss_mb"] for b in ("native", "onnx")}
    cost = metrics["cost"]["cost_per_1k_predictions_usd"]
    lines = [
        "| item | native | onnx |",
        "|---|---|---|",
        f"| fresh-process RSS (MB, median of probes) | {rss['native']['median']:.0f} | "
        f"{rss['onnx']['median']:.0f} |",
        f"| cost per 1k predictions (USD, declared 65 W / $0.30 per kWh) | "
        f"{cost['native']:.6f} | {cost['onnx']:.6f} |",
    ]
    if docker.get("measured"):
        lines.append(
            f"| docker image total (MB, measured) | {docker['total_mb']:.0f} | "
            f"base {docker['base_python_slim_mb']:.0f} + venv {docker['venv_mb']:.0f} + "
            f"model {docker['models_mb']:.1f} |"
        )
    else:
        lines.append("| docker image total (MB) | not measured (daemon unavailable) | — |")
    return "\n".join(lines)


def report_core(cfg: ServingConfig) -> Path:
    """metrics.json + evaluation_metadata.json + figures + report.html + results.md."""
    metrics = assemble_metrics(cfg)
    (cfg.reports_dir).mkdir(parents=True, exist_ok=True)
    (cfg.reports_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    metadata = build_evaluation_metadata(cfg, metrics)
    (cfg.reports_dir / "evaluation_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    figs = build_figures(metrics)
    for name, fig in figs.items():
        save_json(fig, cfg.reports_dir / "figures" / f"{name}.json")
        save_html(fig, cfg.reports_dir / "figures" / f"{name}.html")

    champion = metrics["champion"]
    reproduction = metrics["reproduction"]
    parity = metrics["parity"]
    report = EvalReport(title=REPORT_TITLE)
    report.add_html(
        "Champion re-derivation (experiment 12's recipe, seed 42)",
        "<p>Test MAE <b>{:.4f}</b> against experiment 12's committed <b>{:.4f}</b> — "
        "reproduction |Δ| = {:.6g} (tolerance {:.3g}). Validation MAE {:.4f}; best epoch "
        "{}/{}. Feature contract re-derived: {} selected; pruned {}.</p>".format(
            champion["test_mae"],
            reproduction["expected_test_mae"],
            reproduction["abs_diff"],
            reproduction["tolerance"],
            champion["val_mae"],
            champion["best_epoch"],
            champion["epochs_run"],
            ", ".join(metrics["selection"]["selected"]),
            metrics["selection"]["pruned_pairs"],
        ),
    )
    report.add_html(
        "ONNX parity gate",
        "<p>Max-abs deviation of the raw network output on the seeded {}-row probe grid: "
        "<b>{:.3g}</b> (tolerance {:.3g}, opset {}) — end-to-end that is {:.4g} rentals. "
        "Gate enforced in the train stage; serving stages never run on a failed gate.</p>".format(
            parity["n_probe"],
            parity["max_abs_scaled"],
            parity["tolerance"],
            parity["opset"],
            parity["max_abs_rentals"],
        ),
    )
    report.add_markdown_table(
        "Concurrency sweep — median of repeats (warm-up excluded)", _latency_table(metrics)
    )
    report.add_markdown_table("Batch curve — /predict/batch", _batch_table(metrics))
    report.add_markdown_table("Footprint + cost", _footprint_table(metrics))
    first_plotly = True
    for name, fig in figures_from_json(cfg.reports_dir / "figures").items():
        report.add_figure(name.replace("_", " ").title(), fig, include_plotlyjs=first_plotly)
        first_plotly = False
    for heading, code in mermaid_blocks_from_story(Path(__file__).resolve().parents[2]).items():
        report.add_mermaid(heading, code)
    report.write(cfg.reports_dir / "report.html")

    docker = metrics["docker"]
    if docker.get("measured"):
        docker_line = (
            f"Image `{docker.get('image_ref', '?')}` total {docker['total_mb']:.0f} MB "
            f"(base {docker['base_python_slim_mb']:.0f} + venv {docker['venv_mb']:.0f} + "
            f"model {docker['models_mb']:.1f}); compose smoke passed: "
            f"{docker.get('compose_smoke', {}).get('passed')}."
        )
    else:
        docker_line = "Docker daemon unavailable — image size not measured."
    (cfg.reports_dir / "results.md").write_text(
        f"# {REPORT_TITLE}\n\n"
        f"## Protocol\n\n{metadata['protocol']}\n\n"
        f"## Champion + gates\n\n"
        f"- Reproduction: derived test MAE {champion['test_mae']:.4f} vs committed "
        f"{reproduction['expected_test_mae']:.4f} (|Δ| = {reproduction['abs_diff']:.6g}).\n"
        f"- Parity: max-abs {parity['max_abs_scaled']:.3g} on {parity['n_probe']} probe rows "
        f"(tolerance {parity['tolerance']:.3g}, opset {parity['opset']}).\n\n"
        f"## Concurrency sweep\n\n{_latency_table(metrics)}\n\n"
        f"## Batch curve\n\n{_batch_table(metrics)}\n\n"
        f"## Footprint + cost\n\n{_footprint_table(metrics)}\n\n"
        f"## Docker\n\n{docker_line}\n\n"
        f"## Limits\n\n" + "\n".join(f"- {line}" for line in LIMITS) + "\n\n"
        "Figures: `reports/figures/` (JSON + HTML). Full record: `reports/metrics.json`, "
        "`reports/evaluation_metadata.json`, `reports/train_run.json`, "
        "`data/bench_run.json`, `reports/docker_run.json`.\n"
    )
    log.info("report: metrics + figures + report.html + results.md -> %s", cfg.reports_dir)
    return cfg.reports_dir / "report.html"
