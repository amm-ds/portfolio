"""Typer entrypoints: one command per DVC stage plus interactive runs.

Typical session (from the project directory, Ollama running)::

    uv run python -m inference_serving.cli prepare   # materialize prompts.json
    uv run python -m inference_serving.cli bench      # bounded run (~<45 min)
    uv run python -m inference_serving.cli bench --full  # + extra arms (~hours)
    uv run python -m inference_serving.cli report     # offline figures + report.html
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import Annotated

import httpx
import typer

from inference_serving import bench as bench_mod
from inference_serving import quality as quality_mod
from inference_serving import report as report_mod
from inference_serving.config import BenchConfig, ModelSpec, load_config
from inference_serving.schemas import BenchRun, CellResult

app = typer.Typer(help=__doc__, add_completion=False)


@app.command()
def prepare(config: str = "params.yaml") -> None:
    """Prepare stage: materialize the fixed prompt suite into data/prompts.json."""
    cfg = load_config(Path(config))
    cfg.prompts_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [p.model_dump() for p in bench_mod.PROMPTS]
    cfg.prompts_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    typer.echo(f"prompts ready: {len(payload)} fixed prompts at {cfg.prompts_path}")


@app.command()
def bench(
    config: str = "params.yaml",
    full: Annotated[
        bool, typer.Option("--full", help="Run all arms incl. extra quants/engines.")
    ] = False,
) -> None:
    """Bench stage: async load benchmark against Ollama → data/bench_run.json."""
    cfg = load_config(Path(config))
    cells = bench_mod.plan_cells(cfg, full) + bench_mod.plan_quality_cells(cfg, full)
    typer.echo(
        f"bench: {len(cells)} cells "
        f"({len(set(m.name for m, _ in cells))} models), "
        f"concurrency {cfg.concurrency(full)}, {cfg.repeats} repeats/cell — starting"
    )

    def _show(cell: CellResult) -> None:
        typer.echo(
            f"  {cell.model} c={cell.concurrency}: p95={cell.p95_latency_s or -1:.2f}s "
            f"tok/s={cell.agg_tok_per_s or -1:.1f} valid={cell.schema_valid_rate:.2f} "
            f"fail={cell.n_failures}"
        )

    run = asyncio.run(bench_mod.run_bench(cfg, full=full, on_cell=_show))
    cfg.run_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.run_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"bench complete: {len(run.cells)} cells → {cfg.run_path}")


@app.command()
def report(config: str = "params.yaml") -> None:
    """Report stage (offline): figures + metrics.json + report.html from bench data."""
    cfg = load_config(Path(config))
    if not cfg.run_path.exists():
        raise typer.BadParameter(
            f"no bench run at {cfg.run_path}; run `bench` first (needs a live Ollama)"
        )
    run = BenchRun.model_validate_json(cfg.run_path.read_text(encoding="utf-8"))
    out = report_mod.build_report(run, cfg)
    typer.echo(f"report written: {out}")


# --- pass-4 E10: exact-match quality eval + quantization-matched pair ---------


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 (git is on PATH in every gate env)
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _arm_specs(cfg: BenchConfig) -> list[ModelSpec]:
    """Every committed serving arm, in committed grid order."""
    return [*cfg.models, *cfg.full_models, *cfg.quality_models, *cfg.engine_models]


def _ollama_version(cfg: BenchConfig) -> str:
    try:
        r = httpx.get(f"{cfg.base_url.rstrip('/')}/api/version", timeout=10.0)
        return str(r.json().get("version", ""))
    except (httpx.HTTPError, ValueError):
        return ""


@app.command(name="quality-subset")
def quality_subset(
    raw: Annotated[
        Path, typer.Option(help="Pinned GSM8K test JSONL; downloaded when absent.")
    ] = Path("data/gsm8k_test.jsonl"),
    out: Path = quality_mod.SUBSET_PATH,
) -> None:
    """Materialize the pinned 300-item GSM8K subset (seed 42) at data/quality_subset.jsonl."""
    if not raw.exists():
        typer.echo(f"downloading pinned GSM8K test split → {raw}")
        quality_mod.download_gsm8k(raw)
    subset = quality_mod.build_subset(raw, out)
    typer.echo(
        f"subset ready: {len(subset)} items (seed {quality_mod.SUBSET_SEED}) at {out} "
        f"sha256={quality_mod.sha256_file(out)[:12]}…"
    )


@app.command(name="quality-eval")
def quality_eval(
    config: str = "params.yaml",
    models: Annotated[
        str, typer.Option(help="Comma-separated arm filter; default = every committed arm.")
    ] = "",
    limit: Annotated[int, typer.Option(help="Cap items per arm (0 = full subset).")] = 0,
    out: Annotated[Path, typer.Option(help="Artifact path (merged across invocations).")] = Path(
        "reports/quality_eval.json"
    ),
) -> None:
    """Run the pinned exact-match subset through serving arms → reports/quality_eval.json."""
    cfg = load_config(Path(config))
    if not quality_mod.SUBSET_PATH.exists():
        raise typer.BadParameter(f"no subset at {quality_mod.SUBSET_PATH}; run `quality-subset`")
    items = quality_mod.load_subset()
    if limit:
        items = items[:limit]
    wanted = {m.strip() for m in models.split(",") if m.strip()}
    specs = [s for s in _arm_specs(cfg) if not wanted or s.name in wanted]
    if not specs:
        raise typer.BadParameter("no arms selected")

    async def _run() -> list[quality_mod.QualityArmResult]:
        results: list[quality_mod.QualityArmResult] = []
        async with (
            httpx.AsyncClient(
                base_url=f"{cfg.base_url.rstrip('/')}/v1", timeout=cfg.request_timeout_s
            ) as client,
            httpx.AsyncClient(base_url=cfg.base_url.rstrip("/"), timeout=10.0) as root,
        ):
            for spec in specs:
                quant, evidence, _ = quality_mod.inspect_local_quantization(spec.name)
                typer.echo(f"arm {spec.name}: quant={quant} ({evidence}) — {len(items)} items")
                results.append(
                    await quality_mod.run_quality_arm(
                        client, root, cfg, spec, items, quantization=quant
                    )
                )
        return results

    new_arms = asyncio.run(_run())
    arms: dict[str, quality_mod.QualityArmResult] = {}
    if out.exists():
        prior = quality_mod.QualityEvalArtifact.model_validate_json(out.read_text(encoding="utf-8"))
        arms = {a.model: a for a in prior.arms}
    for arm in new_arms:
        arms[arm.model] = arm
    ordered = [arms[s.name] for s in _arm_specs(cfg) if s.name in arms]
    ordered += [a for m, a in arms.items() if m not in {s.name for s in _arm_specs(cfg)}]
    artifact = quality_mod.build_artifact(
        ordered, git_sha=_git_sha(), ollama_version=_ollama_version(cfg)
    )
    out.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    for arm in ordered:
        typer.echo(
            f"  {arm.model} ({arm.engine}): {arm.n_correct}/{arm.n_items} = {arm.accuracy:.3f}"
        )
    typer.echo(f"quality eval written: {out}")


@app.command()
def remeasure(
    config: str = "params.yaml",
    model: str = "qwen3.6:35b-a3b-q4_K_M",
    tolerance_pct: float = 10.0,
    out: Annotated[Path, typer.Option(help="Gate artifact path.")] = Path(
        "reports/remeasure_gate.json"
    ),
) -> None:
    """Re-measurement gate: re-run one committed cell; exit 1 when drift exceeds tolerance."""
    cfg = load_config(Path(config))
    metrics_path = cfg.reports_dir / "metrics.json"
    committed_cells = json.loads(metrics_path.read_text(encoding="utf-8"))["cells"]
    committed = next(c for c in committed_cells if c["model"] == model and c["concurrency"] == 1)
    gate_cfg = cfg.model_copy(
        update={
            "models": [ModelSpec(name=model, runner="llamacpp")],
            "full_models": [],
            "quality_models": [],
            "engine_models": [],
            "concurrency_default": [1],
        }
    )
    run = asyncio.run(bench_mod.run_bench(gate_cfg, full=False))
    cell = run.cells[0]
    measured = cell.agg_tok_per_s or 0.0
    committed_tps = float(committed["agg_tok_per_s"])
    drift_pct = (measured - committed_tps) / committed_tps * 100.0
    payload = {
        "artifact": "remeasure_gate",
        "model": model,
        "concurrency": 1,
        "committed_agg_tok_per_s": committed_tps,
        "committed_ollama_version": json.loads(metrics_path.read_text(encoding="utf-8")).get(
            "ollama_version", ""
        ),
        "measured_agg_tok_per_s": measured,
        "measured_cell": cell.model_dump(),
        "drift_pct": drift_pct,
        "tolerance_pct": tolerance_pct,
        "passed": abs(drift_pct) <= tolerance_pct,
        "ollama_version": run.ollama_version,
        "platform": run.platform,
        "git_sha": _git_sha(),
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    status = "PASS" if payload["passed"] else "FAIL"
    typer.echo(
        f"remeasure gate: committed {committed_tps:.2f} tok/s vs measured {measured:.2f} "
        f"({drift_pct:+.1f}%, tolerance ±{tolerance_pct:.0f}%) → {status}"
    )
    if not payload["passed"]:
        raise typer.Exit(code=1)


@app.command(name="quant-pair")
def quant_pair(
    config: str = "params.yaml",
    gguf: str = "gemma4:31b-it-q4_K_M",
    mlx: str = "gemma4:31b-mlx",
    out: Annotated[Path, typer.Option(help="Pair artifact path.")] = Path(
        "reports/quant_pair.json"
    ),
) -> None:
    """Quantization-matched cross-runner pair: committed-harness speed cells + the subset."""
    cfg = load_config(Path(config))
    if not quality_mod.SUBSET_PATH.exists():
        raise typer.BadParameter(f"no subset at {quality_mod.SUBSET_PATH}; run `quality-subset`")
    items = quality_mod.load_subset()
    specs = [ModelSpec(name=gguf, runner="llamacpp"), ModelSpec(name=mlx, runner="mlx")]
    pair_cfg = cfg.model_copy(
        update={
            "models": specs,
            "full_models": [],
            "quality_models": [],
            "engine_models": [],
            "concurrency_default": [1],
        }
    )
    speed_run = asyncio.run(bench_mod.run_bench(pair_cfg, full=False))

    async def _quality() -> list[quality_mod.QualityArmResult]:
        results: list[quality_mod.QualityArmResult] = []
        async with (
            httpx.AsyncClient(
                base_url=f"{cfg.base_url.rstrip('/')}/v1", timeout=cfg.request_timeout_s
            ) as client,
            httpx.AsyncClient(base_url=cfg.base_url.rstrip("/"), timeout=10.0) as root,
        ):
            for spec in specs:
                quant, evidence, _ = quality_mod.inspect_local_quantization(spec.name)
                typer.echo(f"pair arm {spec.name}: quant={quant} ({evidence})")
                results.append(
                    await quality_mod.run_quality_arm(
                        client, root, cfg, spec, items, quantization=quant
                    )
                )
        return results

    quality_arms = asyncio.run(_quality())
    sides = []
    for spec, arm in zip(specs, quality_arms, strict=True):
        quant, evidence, config_sha = quality_mod.inspect_local_quantization(spec.name)
        sides.append(
            quality_mod.PairSide(
                label=f"{arm.engine}-{quant}",
                model=spec.name,
                engine=arm.engine,
                quantization=quant,
                quantization_evidence=evidence,
                artifact_config_sha256=config_sha,
            )
        )
    artifact = quality_mod.QuantPairArtifact(
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        git_sha=_git_sha(),
        ollama_version=speed_run.ollama_version,
        platform=speed_run.platform,
        family="gemma4:31b",
        pairing="quantization-matched cross-runner (same model family, matched 4-bit quant)",
        sides=sides,
        speed_protocol=(
            "committed harness cell per side: 8 fixed prompts x 5 repeats at concurrency 1 "
            "(same protocol as the committed engine-panel cells)"
        ),
        speed_cells=speed_run.cells,
        quality_subset_sha256=quality_mod.sha256_file(quality_mod.SUBSET_PATH),
        quality_n_items=len(items),
        quality_seed=quality_mod.SUBSET_SEED,
        quality_arms=quality_arms,
        notes=sorted(set(speed_run.notes)),
    )
    out.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    for cell in speed_run.cells:
        typer.echo(
            f"  {cell.model} ({cell.engine}): {cell.agg_tok_per_s or -1:.2f} tok/s, "
            f"p95={cell.p95_latency_s or -1:.2f}s"
        )
    for arm in quality_arms:
        typer.echo(f"  {arm.model}: exact-match {arm.n_correct}/{arm.n_items} = {arm.accuracy:.3f}")
    typer.echo(f"quant pair written: {out}")


if __name__ == "__main__":
    app()
