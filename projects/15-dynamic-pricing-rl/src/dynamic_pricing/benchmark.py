"""Measured SB3 vector-environment throughput for the E2-3 gate."""

import json
import time
from collections.abc import Callable
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any, cast

import numpy as np
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecEnv

from dynamic_pricing.calibrate import SeriesCalibration, load_params
from dynamic_pricing.env import EpisodeSpec, PricingEnv
from dynamic_pricing.ledger import (
    append_ledger,
    canonical_sha256,
    file_sha256,
    write_json,
)


def load_calibration(path: Path) -> dict[str, SeriesCalibration]:
    raw = cast(list[dict[str, Any]], json.loads(path.read_text()))
    return {
        row["series_id"]: SeriesCalibration(
            series_id=row["series_id"],
            item_id=row["item_id"],
            base=float(row["base"]),
            dow=tuple(float(value) for value in row["dow"]),
            k=float(row["k"]),
            p_ref=float(row["p_ref"]),
        )
        for row in raw
    }


def make_pricing_env(calibrations: dict[str, SeriesCalibration], spec: EpisodeSpec) -> PricingEnv:
    env = PricingEnv(calibrations)
    env.reset(options={"spec": spec})
    return env


def _measure(
    wrapper: Callable[..., VecEnv],
    calibrations: dict[str, SeriesCalibration],
    spec: EpisodeSpec,
    steps: int,
) -> float:
    factories = [
        partial(make_pricing_env, calibrations, replace(spec, seed=spec.seed + index))
        for index in range(8)
    ]
    env = wrapper(factories)
    try:
        env.reset()
        actions = np.full(8, 3, dtype=np.int64)
        started = time.perf_counter()
        for _ in range(steps // 8):
            env.step(actions)
        elapsed = time.perf_counter() - started
        return steps / elapsed
    finally:
        env.close()


def run_benchmark(project_root: Path, repo_root: Path, params_path: Path) -> dict[str, Any]:
    del repo_root
    params = load_params(params_path)
    calibrations = load_calibration(project_root / "data" / "calibration.json")
    splits = json.loads((project_root / "data" / "splits.json").read_text())
    series_id = sorted(splits["series_ids"]["train"])[0]
    spec = EpisodeSpec(
        series_id=series_id,
        epsilon=float(params["elasticity_prior"]["mean"]),
        rho=1.0,
        seed=42,
    )
    steps = 10_000
    result: dict[str, Any] = {
        "steps_per_wrapper": steps,
        "n_envs": 8,
        "dummy_steps_per_second": _measure(DummyVecEnv, calibrations, spec, steps),
        "subproc_steps_per_second": _measure(SubprocVecEnv, calibrations, spec, steps),
    }
    result["selected_wrapper"] = (
        "DummyVecEnv"
        if result["dummy_steps_per_second"] >= result["subproc_steps_per_second"]
        else "SubprocVecEnv"
    )
    write_json(project_root / "reports" / "env_benchmark.json", result)
    append_ledger(
        project_root,
        step="E2-3",
        change="Benchmarked 8-copy SB3 vector environments over 10,000 transitions each",
        split="train series only",
        config_sha256=canonical_sha256(params),
        set_sha256=file_sha256(project_root / "data" / "splits.json"),
        n=steps,
        headline=result,
        wall_clock_s=steps / result["dummy_steps_per_second"]
        + steps / result["subproc_steps_per_second"],
        request_hosts=[],
        report_path="projects/15-dynamic-pricing-rl/reports/env_benchmark.json",
        decision=f"select {result['selected_wrapper']} for E2-7",
    )
    return result
