"""E2-4 fluid-bound and baseline behavior gates."""

import numpy as np
from dynamic_pricing.baselines import ThompsonBaseline, make_baseline, run_baseline
from dynamic_pricing.bound import fluid_upper_bound
from dynamic_pricing.calibrate import SeriesCalibration
from dynamic_pricing.env import EpisodeSpec, PricingEnv


def _calibration() -> dict[str, SeriesCalibration]:
    return {
        "series": SeriesCalibration(
            series_id="series",
            item_id="item",
            base=5.0,
            dow=(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
            k=100.0,
            p_ref=2.0,
        )
    }


def test_zero_noise_fluid_bound_dominates_every_baseline() -> None:
    spec = EpisodeSpec("series", -2.5, 0.7, 42)
    bound = fluid_upper_bound(_calibration()["series"], spec.epsilon, spec.rho)
    policies = [
        make_baseline("B0"),
        make_baseline("B1", b1_action=5),
        make_baseline("B2", b2_behind_pct=10.0, b2_ahead_pct=10.0),
        make_baseline("B3"),
    ]
    for policy in policies:
        env = PricingEnv(_calibration(), zero_noise=True)
        result = run_baseline(env, spec, policy)
        assert result.mean_normalised_profit <= bound + 1e-8


def test_b3_posterior_moves_toward_true_elasticity() -> None:
    policy = ThompsonBaseline()
    policy.reset(seed=42)
    before = policy.posterior_mean
    true_epsilon = -4.0
    for _ in range(91):
        multiplier = 1.3
        lambda_ref = 5.0
        sales = lambda_ref * multiplier**true_epsilon
        policy.observe({"multiplier": multiplier, "lambda_ref": lambda_ref, "sales": sales})
    after = policy.posterior_mean
    assert after < before
    assert abs(after - true_epsilon) < abs(before - true_epsilon)


def test_all_baselines_have_zero_mask_violations_over_50_specs() -> None:
    rng = np.random.default_rng(42)
    specs = [
        EpisodeSpec(
            series_id="series",
            epsilon=float(rng.uniform(-5.0, -0.8)),
            rho=(0.7, 1.0, 1.3)[index % 3],
            seed=1000 + index,
        )
        for index in range(50)
    ]
    for policy_id in ("B0", "B1", "B2", "B3"):
        for spec in specs:
            env = PricingEnv(_calibration())
            result = run_baseline(env, spec, make_baseline(policy_id, b1_action=5))
            assert result.violations == 0
