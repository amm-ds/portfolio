"""E2-3 environment, CRN, and action-mask gates."""

import gymnasium as gym
import numpy as np
import pytest
from dynamic_pricing.calibrate import SeriesCalibration
from dynamic_pricing.env import HORIZON, MULTIPLIERS, EpisodeSpec, PricingEnv
from gymnasium.utils.env_checker import check_env


def _calibration() -> dict[str, SeriesCalibration]:
    return {
        "series": SeriesCalibration(
            series_id="series",
            item_id="item",
            base=5.0,
            dow=(0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 0.7),
            k=2.0,
            p_ref=2.0,
        )
    }


def _spec(seed: int = 42) -> EpisodeSpec:
    return EpisodeSpec(series_id="series", epsilon=-2.5, rho=1.0, seed=seed)


def _reset(env: PricingEnv, spec: EpisodeSpec | None = None) -> None:
    env.reset(options={"spec": spec or _spec()})


def test_same_spec_produces_identical_trajectory() -> None:
    first = PricingEnv(_calibration())
    second = PricingEnv(_calibration())
    first_obs, _ = first.reset(options={"spec": _spec()})
    second_obs, _ = second.reset(options={"spec": _spec()})
    np.testing.assert_array_equal(first_obs, second_obs)
    for _ in range(HORIZON):
        first_step = first.step(3)
        second_step = second.step(3)
        np.testing.assert_array_equal(first_step[0], second_step[0])
        assert first_step[1:] == second_step[1:]


def test_different_policies_share_the_same_uniform_stream() -> None:
    holding = PricingEnv(_calibration())
    changing = PricingEnv(_calibration())
    _reset(holding)
    _reset(changing)
    np.testing.assert_array_equal(holding.demand_uniforms, changing.demand_uniforms)
    holding.step(3)
    changing.step(2)
    np.testing.assert_array_equal(holding.demand_uniforms, changing.demand_uniforms)


def test_masks_forbid_two_step_jump_and_changes_inside_cooldown() -> None:
    env = PricingEnv(_calibration())
    _reset(env)
    mask = env.action_masks()
    assert not mask[1]
    assert mask[2]
    assert mask[3]
    assert mask[4]
    assert not mask[5]

    env.step(2)
    next_mask = env.action_masks()
    assert not next_mask[3]
    assert next_mask[2]
    for _ in range(6):
        env.step(2)
    assert env.action_masks()[3]


def test_invalid_action_raises_in_strict_mode() -> None:
    env = PricingEnv(_calibration(), strict=True)
    _reset(env)
    with pytest.raises(ValueError, match="invalid masked action"):
        env.step(1)
    assert env.violations == 1


def test_invalid_action_holds_price_and_counts_by_default() -> None:
    env = PricingEnv(_calibration())
    _reset(env)
    _, _, _, _, info = env.step(1)
    assert info["multiplier"] == 1.0
    assert info["violations"] == 1


def test_sales_never_exceed_inventory() -> None:
    env = PricingEnv(_calibration())
    _reset(env, EpisodeSpec("series", -5.0, 1.3, 7))
    for _ in range(HORIZON):
        before = env.inventory
        _, _, terminated, _, info = env.step(3)
        assert info["sales"] <= before
        assert info["inventory"] >= 0
        if terminated:
            break


def test_c4_margin_floor_holds_across_whole_band() -> None:
    p_ref = _calibration()["series"].p_ref
    assert np.all(MULTIPLIERS * p_ref >= 0.60 * p_ref * 1.05)


def test_gymnasium_check_env_passes_after_spec_reset() -> None:
    env = PricingEnv(_calibration())
    _reset(env)
    check_env(env, skip_render_check=True)
    assert isinstance(env, gym.Env)
