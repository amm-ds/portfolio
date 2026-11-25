"""PPO encoder shape and mandatory action-mask forwarding."""

from typing import Any

import gymnasium as gym
import numpy as np
import torch as th
from dynamic_pricing.calibrate import SeriesCalibration
from dynamic_pricing.env import OBSERVATION_LEN, EpisodeSpec, PricingEnv
from dynamic_pricing.ppo import HistoryEncoder, run_ppo_episode


def test_history_encoder_uses_temporal_history_and_scalar_context() -> None:
    encoder = HistoryEncoder(gym.spaces.Box(-1.0, 1.0, shape=(OBSERVATION_LEN,), dtype=np.float32))
    output = encoder(th.zeros((2, OBSERVATION_LEN), dtype=th.float32))
    assert output.shape == (2, 192)


class MaskCheckingModel:
    def predict(self, observation: Any, deterministic: bool, action_masks: Any) -> tuple[int, None]:
        assert deterministic
        assert action_masks[3]
        return 3, None


def test_ppo_evaluation_passes_masks_and_has_zero_violations() -> None:
    calibration = SeriesCalibration("series", "item", 5.0, (1.0,) * 7, 2.0, 2.0)
    env = PricingEnv({"series": calibration})
    result = run_ppo_episode(
        env,
        EpisodeSpec("series", -2.5, 1.0, 42),
        MaskCheckingModel(),  # type: ignore[arg-type]
    )
    assert result.violations == 0
