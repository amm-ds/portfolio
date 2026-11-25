"""E2-7 MaskablePPO training, validation, and checkpoint selection."""

import json
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any, cast

import gymnasium as gym
import numpy as np
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import SubprocVecEnv

from dynamic_pricing.benchmark import load_calibration
from dynamic_pricing.calibrate import SeriesCalibration, load_params
from dynamic_pricing.env import EpisodeSpec, PricingEnv
from dynamic_pricing.ledger import (
    append_ledger,
    canonical_sha256,
    file_sha256,
    write_json,
)
from dynamic_pricing.ppo import HistoryEncoder, run_ppo_episode
from dynamic_pricing.specs import load_episode_specs
from dynamic_pricing.tune import _summarise

PPO_HYPERPARAMETERS: dict[str, Any] = {
    "learning_rate": 3e-4,
    "n_steps": 2048,
    "batch_size": 64,
    "n_epochs": 10,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip_range": 0.2,
    "clip_range_vf": None,
    "normalize_advantage": True,
    "ent_coef": 0.0,
    "vf_coef": 0.5,
    "max_grad_norm": 0.5,
    "target_kl": None,
    "stats_window_size": 100,
    "policy": "MlpPolicy",
    "device": "cpu",
    "net_arch": {"pi": [64, 64], "vf": [64, 64]},
    "history_encoder": {"history_len": 14, "conv_layers": 2, "channels": 16, "kernel": 3},
}


class ScheduledPricingEnv(PricingEnv):
    """Cycle through train specs when SB3 resets an environment automatically."""

    def __init__(
        self,
        calibrations: dict[str, SeriesCalibration],
        specs: list[EpisodeSpec],
        offset: int,
    ) -> None:
        if not specs:
            raise ValueError("training requires at least one spec")
        self._schedule = specs
        self._next = offset % len(specs)
        super().__init__(calibrations)
        super().reset(options={"spec": self._schedule[self._next]})
        self._next = (self._next + 1) % len(specs)

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        if options is not None and "spec" in options:
            return super().reset(seed=seed, options=options)
        spec = self._schedule[self._next]
        self._next = (self._next + 1) % len(self._schedule)
        return super().reset(seed=seed, options={"spec": spec})


def make_scheduled_env(
    calibrations: dict[str, SeriesCalibration], specs: list[EpisodeSpec], offset: int
) -> ScheduledPricingEnv:
    return ScheduledPricingEnv(calibrations, specs, offset)


class CurveCallback(BaseCallback):
    """Retain downsampled rollout metrics without external logging services."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, float | int | None]] = []

    def _on_step(self) -> bool:
        return True

    def _on_rollout_end(self) -> None:
        values = self.model.logger.name_to_value
        reward = values.get("rollout/ep_rew_mean")
        loss = values.get("train/loss")
        self.rows.append(
            {
                "timesteps": self.num_timesteps,
                "ep_rew_mean": None if reward is None else float(reward),
                "loss": None if loss is None else float(loss),
            }
        )


def _vec_env(calibrations: dict[str, SeriesCalibration], specs: list[EpisodeSpec]) -> SubprocVecEnv:
    factories: list[Callable[[], gym.Env[Any, Any]]] = [
        partial(make_scheduled_env, calibrations, specs, index) for index in range(8)
    ]
    return SubprocVecEnv(factories, start_method="spawn")


def _model(env: SubprocVecEnv, seed: int) -> MaskablePPO:
    return MaskablePPO(
        policy="MlpPolicy",
        env=env,
        seed=seed,
        verbose=0,
        policy_kwargs={
            "features_extractor_class": HistoryEncoder,
            "features_extractor_kwargs": {"history_len": 14},
            "net_arch": {"pi": [64, 64], "vf": [64, 64]},
        },
        **{
            key: value
            for key, value in PPO_HYPERPARAMETERS.items()
            if key not in {"policy", "device", "net_arch", "history_encoder"}
        },
        device="cpu",
    )


def _val_specs(project_root: Path) -> list[EpisodeSpec]:
    splits = cast(dict[str, Any], json.loads((project_root / "data" / "splits.json").read_text()))
    return load_episode_specs(splits, "val")


def run_smoke(project_root: Path, repo_root: Path, params_path: Path) -> dict[str, Any]:
    del repo_root
    params = load_params(params_path)
    calibrations = load_calibration(project_root / "data" / "calibration.json")
    splits = cast(dict[str, Any], json.loads((project_root / "data" / "splits.json").read_text()))
    train_specs = load_episode_specs(splits, "train")
    env = _vec_env(calibrations, train_specs)
    started = time.perf_counter()
    try:
        model = _model(env, seed=0)
        smoke_steps = 16_384
        model.learn(total_timesteps=smoke_steps, progress_bar=False)
    finally:
        env.close()
    elapsed = time.perf_counter() - started
    projected_hours = (9_000_000 / smoke_steps) * elapsed / 3600.0
    result = {
        "seed": 0,
        "steps": smoke_steps,
        "wall_clock_s": elapsed,
        "projected_hours_for_3_by_3m": projected_hours,
        "within_24h": projected_hours <= 24.0,
        "recommended_steps_per_seed": 3_000_000 if projected_hours <= 24.0 else 2_000_000,
    }
    write_json(project_root / "reports" / "training_smoke.json", result)
    append_ledger(
        project_root,
        step="E2-7-smoke",
        change="Measured MaskablePPO throughput before full training",
        split="train",
        config_sha256=canonical_sha256(params),
        set_sha256=file_sha256(project_root / "data" / "splits.json"),
        n=smoke_steps,
        headline=result,
        wall_clock_s=elapsed,
        report_path="projects/15-dynamic-pricing-rl/reports/training_smoke.json",
        decision="use recommended steps per seed before full training",
    )
    return result


def run_training(
    project_root: Path, repo_root: Path, params_path: Path, steps: int = 3_000_000
) -> dict[str, Any]:
    del repo_root
    if steps not in {2_000_000, 3_000_000}:
        raise ValueError("steps must be the pre-approved 3,000,000 or fallback 2,000,000")
    params = load_params(params_path)
    calibrations = load_calibration(project_root / "data" / "calibration.json")
    splits_path = project_root / "data" / "splits.json"
    splits = cast(dict[str, Any], json.loads(splits_path.read_text()))
    train_specs = load_episode_specs(splits, "train")
    val_specs = _val_specs(project_root)
    models_dir = project_root / "reports" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    curves: dict[str, Any] = {}
    validations: dict[str, Any] = {}

    for seed in (0, 1, 2):
        env = _vec_env(calibrations, train_specs)
        callback = CurveCallback()
        started = time.perf_counter()
        try:
            model = _model(env, seed=seed)
            model.learn(total_timesteps=steps, callback=callback, progress_bar=False)
        finally:
            env.close()
        wall_clock = time.perf_counter() - started
        model_path = models_dir / f"ppo_seed_{seed}.zip"
        model.save(model_path)
        val_env = PricingEnv(calibrations)
        results = [run_ppo_episode(val_env, spec, model) for spec in val_specs]
        summary = _summarise(results)
        if summary["violations"] != 0:
            raise RuntimeError(f"PPO seed {seed} violated action masks on validation")
        validations[str(seed)] = {
            **summary,
            "wall_clock_s": wall_clock,
            "total_timesteps": steps,
            "model_path": f"reports/models/ppo_seed_{seed}.zip",
        }
        stride = max(1, len(callback.rows) // 200)
        curves[str(seed)] = callback.rows[::stride]
        write_json(project_root / "reports" / "train_curves.json", curves)
        append_ledger(
            project_root,
            step=f"E2-7-seed-{seed}",
            change=f"Trained MaskablePPO for {steps} steps and evaluated 300 val episodes",
            split="train then val",
            config_sha256=canonical_sha256(params),
            set_sha256=file_sha256(splits_path),
            n=steps,
            headline=validations[str(seed)],
            wall_clock_s=wall_clock,
            report_path="projects/15-dynamic-pricing-rl/reports/ppo_val.json",
            decision="validation recorded; no sealed evaluation",
        )

    selected_seed = max(validations, key=lambda seed: validations[seed]["mean_normalised_profit"])
    for seed in (0, 1, 2):
        if str(seed) != selected_seed:
            (models_dir / f"ppo_seed_{seed}.zip").unlink()
    report = {
        "seeds": [0, 1, 2],
        "n_envs": 8,
        "wrapper": "SubprocVecEnv",
        "total_timesteps_per_seed": steps,
        "hyperparameters": PPO_HYPERPARAMETERS,
        "validation": validations,
        "selected_seed": int(selected_seed),
        "selected_model_path": validations[selected_seed]["model_path"],
        "n_val_episodes": len(val_specs),
    }
    write_json(project_root / "reports" / "ppo_val.json", report)
    return report
