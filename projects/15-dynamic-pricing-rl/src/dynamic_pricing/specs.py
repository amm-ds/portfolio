"""Deterministic, stream-separated episode specification generation."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import numpy as np
from scipy.stats import truncnorm  # type: ignore[import-untyped]

from dynamic_pricing.env import EpisodeSpec
from dynamic_pricing.ledger import canonical_sha256, write_json


def generate_specs(
    series_ids: list[str],
    n: int,
    *,
    seed: int,
    stream: int,
    prior_mean: float,
    prior_sd: float,
    lower: float = -5.0,
    upper: float = -0.8,
) -> list[EpisodeSpec]:
    """Draw series, elasticity, balanced inventory pressure, and stable seeds."""
    if not series_ids or n <= 0:
        raise ValueError("series_ids must be non-empty and n positive")
    rng = np.random.default_rng(np.random.SeedSequence([seed, stream]))
    selected_series = rng.choice(np.array(sorted(series_ids), dtype=object), size=n)
    uniforms = rng.random(n)
    a = (lower - prior_mean) / prior_sd
    b = (upper - prior_mean) / prior_sd
    elasticities = truncnorm.ppf(uniforms, a, b, loc=prior_mean, scale=prior_sd)
    rhos = np.resize(np.array([0.7, 1.0, 1.3]), n)
    rng.shuffle(rhos)
    return [
        EpisodeSpec(
            series_id=str(selected_series[index]),
            epsilon=float(elasticities[index]),
            rho=float(rhos[index]),
            seed=stream * 1_000_000 + index,
        )
        for index in range(n)
    ]


def load_episode_specs(payload: dict[str, Any], split: str) -> list[EpisodeSpec]:
    return [EpisodeSpec(**row) for row in payload["episodes"][split]]


def materialize_development_specs(project_root: Path, params: dict[str, Any]) -> None:
    """Create reproducible train and validation specs without touching sealed sets."""
    path = project_root / "data" / "splits.json"
    payload = cast(dict[str, Any], json.loads(path.read_text()))
    prior = params["elasticity_prior"]
    tuning = params["tuning"]
    episodes: dict[str, Any] = {}
    for split, stream_key in (("train", "train_stream"), ("val", "val_stream")):
        specs = generate_specs(
            payload["series_ids"][split],
            int(tuning[f"{split}_episodes"]),
            seed=int(params["seed"]),
            stream=int(tuning[stream_key]),
            prior_mean=float(prior["mean"]),
            prior_sd=float(prior["sd"]),
            lower=float(prior["lower"]),
            upper=float(prior["upper"]),
        )
        episodes[split] = [asdict(spec) for spec in specs]
    payload["episodes"] = episodes
    payload.pop("content_sha256", None)
    payload["content_sha256"] = canonical_sha256(payload)
    write_json(path, payload)
