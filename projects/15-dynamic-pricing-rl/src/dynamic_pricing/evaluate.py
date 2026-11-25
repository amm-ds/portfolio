"""E2-8 single sealed evaluation against the committed pre-registration."""

import json
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray
from portfolio_eval.intervals import paired_bootstrap

from dynamic_pricing.baselines import EpisodeResult, make_baseline, run_baseline
from dynamic_pricing.benchmark import load_calibration
from dynamic_pricing.bound import solve_fluid_lp
from dynamic_pricing.calibrate import SeriesCalibration, load_params
from dynamic_pricing.env import HORIZON, EpisodeSpec, PricingEnv
from dynamic_pricing.ledger import (
    append_ledger,
    canonical_sha256,
    file_sha256,
    write_json,
)
from dynamic_pricing.ppo import load_ppo, run_ppo_episode
from dynamic_pricing.specs import load_episode_specs

FloatArray = NDArray[np.float64]
EXECUTABLE_POLICIES = ("B0", "B1", "B2", "B3", "RL")
BASELINE_POLICIES = ("B0", "B1", "B2", "B3")
EVALUATION_ORDER = ("test", "stress_mean_m1_5", "stress_mean_m3_5")
SPLITS_REPO_PATH = "projects/15-dynamic-pricing-rl/data/splits.json"


class TracePricingEnv(PricingEnv):
    """Record daily outcomes while the ordinary masked runners execute once."""

    def __init__(self, calibrations: dict[str, SeriesCalibration]) -> None:
        super().__init__(calibrations)
        self.trace: list[dict[str, float | int]] = []

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[NDArray[np.float32], dict[str, Any]]:
        self.trace.clear()
        return super().reset(seed=seed, options=options)

    def step(self, action: int) -> tuple[NDArray[np.float32], float, bool, bool, dict[str, Any]]:
        observation, reward, terminated, truncated, info = super().step(action)
        self.trace.append(
            {
                "day": len(self.trace),
                "multiplier": float(info["multiplier"]),
                "price": float(info["price"]),
                "sales": int(info["sales"]),
                "inventory": int(info["inventory"]),
            }
        )
        return observation, reward, terminated, truncated, info


def _mean_difference(a: FloatArray, b: FloatArray) -> float:
    return float(np.mean(a) - np.mean(b))


def _mean_ci95(values: list[float], n_resamples: int, seed: int) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    _, lo, hi = paired_bootstrap(
        array,
        np.zeros_like(array),
        _mean_difference,
        n_resamples=n_resamples,
        seed=seed,
    )
    return [lo, hi]


def _fluid_episode(calibration: SeriesCalibration, spec: EpisodeSpec) -> tuple[float, float]:
    """Return normalised profit and expected gross profit excluding salvage."""
    dow = np.asarray(calibration.dow, dtype=np.float64)
    reference = calibration.base * dow[np.arange(HORIZON) % 7]
    inventory = max(1, round(float(reference.sum()) / spec.rho))
    revenue_reference = float(reference.sum()) * calibration.p_ref
    solution = solve_fluid_lp(calibration, spec.epsilon, reference, inventory, revenue_reference)
    leftover = inventory - solution.expected_sales
    salvage = 0.30 * calibration.p_ref * leftover
    raw_gross_profit = solution.profit * revenue_reference - salvage
    return solution.profit, raw_gross_profit


def _new_set_payload(specs: list[EpisodeSpec]) -> dict[str, Any]:
    policies: dict[str, Any] = {
        policy_id: {"normalised_profit": [], "raw_gross_profit": [], "violations": []}
        for policy_id in EXECUTABLE_POLICIES
    }
    policies["UB"] = {"normalised_profit": [], "raw_gross_profit": []}
    return {"specs": [asdict(spec) for spec in specs], "policies": policies}


def _append_result(payload: dict[str, Any], result: EpisodeResult) -> None:
    block = payload["policies"][result.policy_id]
    block["normalised_profit"].append(result.mean_normalised_profit)
    block["raw_gross_profit"].append(result.raw_gross_profit)
    block["violations"].append(result.violations)


def _policy_summary(
    set_payload: dict[str, Any],
    policy_id: str,
    *,
    include_ci: bool,
    n_resamples: int,
    seed: int,
) -> dict[str, Any]:
    block = set_payload["policies"][policy_id]
    profits = np.asarray(block["normalised_profit"], dtype=np.float64)
    bound = np.asarray(set_payload["policies"]["UB"]["normalised_profit"], dtype=np.float64)
    rhos = np.asarray([spec["rho"] for spec in set_payload["specs"]], dtype=np.float64)
    bound_mean = float(np.mean(bound))
    summary: dict[str, Any] = {
        "n_episodes": int(profits.size),
        "mean_normalised_profit": float(np.mean(profits)),
        "mean_raw_gross_profit": float(np.mean(block["raw_gross_profit"])),
        "fluid_bound_share": float(np.mean(profits) / bound_mean),
        "fluid_bound_share_pct": float(100.0 * np.mean(profits) / bound_mean),
        "fluid_bound_share_by_rho": {
            str(rho): float(np.mean(profits[rhos == rho]) / np.mean(bound[rhos == rho]))
            for rho in (0.7, 1.0, 1.3)
        },
        "mean_by_rho": {str(rho): float(np.mean(profits[rhos == rho])) for rho in (0.7, 1.0, 1.3)},
    }
    if policy_id == "UB":
        summary["violations"] = None
        summary["constraint_policy"] = False
    else:
        summary["violations"] = int(sum(block["violations"]))
        summary["constraint_policy"] = True
    if include_ci:
        summary["mean_normalised_profit_ci95"] = _mean_ci95(
            block["normalised_profit"], n_resamples, seed
        )
    return summary


def _compute_gates(
    test_payload: dict[str, Any], preregistration: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    """Compute P1/P2 solely from episode rows and the frozen protocol."""
    comparator = str(preregistration["comparator"])
    rl = np.asarray(test_payload["policies"]["RL"]["normalised_profit"], dtype=np.float64)
    other = np.asarray(test_payload["policies"][comparator]["normalised_profit"], dtype=np.float64)
    bootstrap = preregistration["paired_bootstrap"]
    point, lo, hi = paired_bootstrap(
        rl,
        other,
        _mean_difference,
        n_resamples=int(bootstrap["n_resamples"]),
        seed=int(bootstrap["seed"]),
    )
    comparator_mean = float(np.mean(other))
    relative_lift = point / comparator_mean
    p1_rule = preregistration["hypotheses"]["P1"]
    p1_pass = bool(
        relative_lift >= float(p1_rule["relative_lift_min"])
        and lo > float(p1_rule["paired_difference_ci_lower_exclusive"])
    )
    primary = {
        "hypothesis": "P1",
        "comparison": p1_rule["comparison"],
        "comparator": comparator,
        "relative_lift": relative_lift,
        "relative_lift_pct": 100.0 * relative_lift,
        "relative_lift_min": float(p1_rule["relative_lift_min"]),
        "paired_difference": {
            "point": point,
            "lo": lo,
            "hi": hi,
            "confidence": float(bootstrap["confidence"]),
            "n_resamples": int(bootstrap["n_resamples"]),
            "seed": int(bootstrap["seed"]),
            "unit": bootstrap["unit"],
        },
        "passes": p1_pass,
    }
    violations = {
        policy_id: int(sum(test_payload["policies"][policy_id]["violations"]))
        for policy_id in EXECUTABLE_POLICIES
    }
    p2_rule = preregistration["hypotheses"]["P2"]
    p2_pass = all(value == int(p2_rule["violations_exactly"]) for value in violations.values())
    constraints = {
        "hypothesis": "P2",
        "violations_by_policy": violations,
        "violations_exactly": int(p2_rule["violations_exactly"]),
        "action_masks_required": bool(p2_rule["action_masks_required"]),
        "passes": p2_pass,
    }
    verdicts = {
        "P1": "pass" if p1_pass else "fail",
        "P2": "pass" if p2_pass else "fail",
        "P3": "context_only",
    }
    return primary, constraints, verdicts


def _existing_access(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        raise ValueError("sealed_access.json must contain a list")
    rows = cast(list[dict[str, Any]], payload)
    if any(row.get("purpose") == "seal_read" for row in rows):
        raise RuntimeError("a sealed read already exists; this evaluation is permanently consumed")
    return rows


def _append_sealed_access(
    path: Path, split: str, specs_sha256: str, rows: list[dict[str, Any]]
) -> None:
    if any(row.get("purpose") == "seal_read" and row.get("split") == split for row in rows):
        raise RuntimeError(f"sealed set {split} was already read")
    rows.append(
        {
            "ts": datetime.now(UTC).isoformat(),
            "step": "E2-8",
            "split": split,
            "path": SPLITS_REPO_PATH,
            "sha256": specs_sha256,
            "purpose": "seal_read",
        }
    )
    write_json(path, rows)


def _baseline_factory(policy_id: str, params: dict[str, Any], tuning: dict[str, Any]) -> Any:
    prior = params["elasticity_prior"]
    if policy_id == "B1":
        return make_baseline(policy_id, b1_action=int(tuning["train"]["best_b1"]["action"]))
    if policy_id == "B2":
        best = tuning["train"]["best_b2"]
        return make_baseline(
            policy_id,
            b2_behind_pct=float(best["behind_pct"]),
            b2_ahead_pct=float(best["ahead_pct"]),
        )
    if policy_id == "B3":
        return make_baseline(
            policy_id,
            prior_mean=float(prior["mean"]),
            prior_sd=float(prior["sd"]),
            observation_sd=float(params["baselines"]["b3_observation_sd"]),
        )
    return make_baseline(policy_id)


def run_sealed_evaluation(project_root: Path, repo_root: Path, params_path: Path) -> dict[str, Any]:
    """Preflight everything, then consume each sealed set exactly once."""
    del repo_root
    started = time.perf_counter()
    reports = project_root / "reports"
    access_path = reports / "sealed_access.json"
    access_rows = _existing_access(access_path)
    for name in ("metrics.json", "test_episodes.json"):
        if (reports / name).exists():
            raise RuntimeError(f"refusing to overwrite existing sealed output: {name}")

    params = load_params(params_path)
    preregistration = params["preregistration"]
    comparator = str(preregistration["comparator"])
    if comparator != params["comparator"]:
        raise ValueError("comparator differs from the pre-registered comparator")
    tuning = json.loads((reports / "baselines_val.json").read_text())
    if tuning["comparator"] != comparator:
        raise ValueError("validation tuning artifact disagrees with the comparator")

    splits_path = project_root / "data" / "splits.json"
    splits = cast(dict[str, Any], json.loads(splits_path.read_text()))
    sealed_specs: dict[str, list[EpisodeSpec]] = {}
    for name in EVALUATION_ORDER:
        definition = preregistration["evaluation_sets"][name]
        raw_specs = splits["sealed_evaluation"][name]
        if canonical_sha256(raw_specs) != definition["specs_sha256"]:
            raise ValueError(f"sealed spec hash mismatch for {name}")
        specs = [EpisodeSpec(**row) for row in raw_specs]
        if len(specs) != int(definition["n"]):
            raise ValueError(f"sealed spec count mismatch for {name}")
        sealed_specs[name] = specs

    calibrations = load_calibration(project_root / "data" / "calibration.json")
    ppo_report = json.loads((reports / "ppo_val.json").read_text())
    model_path = project_root / str(ppo_report["selected_model_path"])
    model = load_ppo(model_path)
    val_specs = load_episode_specs(splits, "val")
    preflight = run_ppo_episode(PricingEnv(calibrations), val_specs[0], model)
    if preflight.violations != 0:
        raise RuntimeError("winning model failed the validation preflight mask check")

    trace_rng = np.random.default_rng(int(preregistration["seed"]))
    trace_indices = sorted(
        int(index) for index in trace_rng.choice(len(sealed_specs["test"]), size=3, replace=False)
    )
    trace_index_set = set(trace_indices)
    episode_payload: dict[str, Any] = {
        "selection": {
            "price_trace_seed": int(preregistration["seed"]),
            "price_trace_indices": trace_indices,
            "selection_rule": "fixed-seed uniform choice without replacement; outcomes unseen",
        },
        "sets": {},
        "price_traces": {},
    }

    for set_name in EVALUATION_ORDER:
        specs = sealed_specs[set_name]
        spec_hash = str(preregistration["evaluation_sets"][set_name]["specs_sha256"])
        _append_sealed_access(access_path, set_name, spec_hash, access_rows)
        set_payload = _new_set_payload(specs)
        env = PricingEnv(calibrations)
        trace_env = TracePricingEnv(calibrations)
        for index, spec in enumerate(specs):
            capture = set_name == "test" and index in trace_index_set
            for policy_id in BASELINE_POLICIES:
                policy = _baseline_factory(policy_id, params, tuning)
                selected_env = trace_env if capture and policy_id == comparator else env
                result = run_baseline(selected_env, spec, policy)
                _append_result(set_payload, result)
                if capture and policy_id == comparator:
                    episode_payload["price_traces"][str(index)] = {
                        "spec": asdict(spec),
                        "policies": {policy_id: list(trace_env.trace)},
                    }
            selected_env = trace_env if capture else env
            rl_result = run_ppo_episode(selected_env, spec, model)
            _append_result(set_payload, rl_result)
            if capture:
                episode_payload["price_traces"][str(index)]["policies"]["RL"] = list(
                    trace_env.trace
                )
            bound_profit, bound_raw = _fluid_episode(calibrations[spec.series_id], spec)
            set_payload["policies"]["UB"]["normalised_profit"].append(bound_profit)
            set_payload["policies"]["UB"]["raw_gross_profit"].append(bound_raw)
        episode_payload["sets"][set_name] = set_payload
        write_json(reports / "test_episodes.json", episode_payload)

    bootstrap = preregistration["paired_bootstrap"]
    summaries: dict[str, Any] = {}
    for set_name in EVALUATION_ORDER:
        set_payload = episode_payload["sets"][set_name]
        summaries[set_name] = {
            "n_episodes": len(sealed_specs[set_name]),
            "policies": {
                policy_id: _policy_summary(
                    set_payload,
                    policy_id,
                    include_ci=set_name == "test",
                    n_resamples=int(bootstrap["n_resamples"]),
                    seed=int(bootstrap["seed"]),
                )
                for policy_id in (*EXECUTABLE_POLICIES, "UB")
            },
        }
    primary, constraints, verdicts = _compute_gates(
        episode_payload["sets"]["test"], preregistration
    )
    metrics: dict[str, Any] = {
        "protocol_version": int(preregistration["protocol_version"]),
        "preregistration_sha256": canonical_sha256(preregistration),
        "selected_seed": int(ppo_report["selected_seed"]),
        "selected_model_path": str(ppo_report["selected_model_path"]),
        "test": summaries["test"],
        "stress": {name: summaries[name] for name in EVALUATION_ORDER if name != "test"},
        "primary": primary,
        "constraint_gate": constraints,
        "verdicts": verdicts,
        "price_trace_indices": trace_indices,
        "bound_share_method": "ratio of mean normalised profits within each rho group",
    }
    write_json(reports / "metrics.json", metrics)
    append_ledger(
        project_root,
        step="E2-8",
        change=(
            "Consumed test and both stress sets once with B0-B3, selected masked PPO, and fluid UB"
        ),
        split="test then stress_mean_m1_5 then stress_mean_m3_5",
        config_sha256=canonical_sha256(params),
        set_sha256=file_sha256(splits_path),
        n=sum(len(specs) for specs in sealed_specs.values()),
        headline={"primary": primary, "constraint_gate": constraints, "verdicts": verdicts},
        wall_clock_s=time.perf_counter() - started,
        request_hosts=[],
        report_path="projects/15-dynamic-pricing-rl/reports/metrics.json",
        decision="sealed sets consumed; no policy or threshold changes permitted",
    )
    return metrics
