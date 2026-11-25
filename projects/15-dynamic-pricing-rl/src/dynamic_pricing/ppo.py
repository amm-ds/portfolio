"""Custom PPO history encoder and mask-enforcing episode evaluation."""

from pathlib import Path

import gymnasium as gym
import torch as th
from sb3_contrib import MaskablePPO
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from torch import nn

from dynamic_pricing.baselines import EpisodeResult
from dynamic_pricing.env import HISTORY_LEN, OBSERVATION_LEN, EpisodeSpec, PricingEnv


class HistoryEncoder(BaseFeaturesExtractor):
    """Two-layer temporal CNN plus an MLP over scalar and lookahead context."""

    def __init__(self, observation_space: gym.spaces.Box, history_len: int = HISTORY_LEN) -> None:
        if history_len != HISTORY_LEN or observation_space.shape != (OBSERVATION_LEN,):
            raise ValueError("HistoryEncoder expects the frozen 39-value observation layout")
        self.history_len = history_len
        conv_output_dim = 16 * (history_len - 4)
        scalar_dim = 32
        super().__init__(observation_space, features_dim=conv_output_dim + scalar_dim)
        self.history = nn.Sequential(
            nn.Conv1d(2, 16, kernel_size=3),
            nn.ReLU(),
            nn.Conv1d(16, 16, kernel_size=3),
            nn.ReLU(),
            nn.Flatten(),
        )
        self.context = nn.Sequential(
            nn.Linear(OBSERVATION_LEN - 2 * history_len, scalar_dim),
            nn.ReLU(),
        )

    def forward(self, observations: th.Tensor) -> th.Tensor:
        history = observations[:, 4:32].reshape(-1, self.history_len, 2).transpose(1, 2)
        scalars = th.cat((observations[:, :4], observations[:, 32:]), dim=1)
        return th.cat((self.history(history), self.context(scalars)), dim=1)


def run_ppo_episode(env: PricingEnv, spec: EpisodeSpec, model: MaskablePPO) -> EpisodeResult:
    """Evaluate deterministically with the current action mask on every predict."""
    observation, _ = env.reset(options={"spec": spec})
    total_profit = 0.0
    while True:
        action, _ = model.predict(observation, deterministic=True, action_masks=env.action_masks())
        action_index = int(action)
        if not env.action_masks()[action_index]:
            raise ValueError(f"PPO returned masked action {action_index}")
        observation, reward, terminated, _, info = env.step(action_index)
        total_profit += reward
        if terminated:
            return EpisodeResult(
                policy_id="RL",
                spec=spec,
                mean_normalised_profit=total_profit,
                raw_gross_profit=float(info["gross_profit"]),
                violations=int(info["violations"]),
                terminal_inventory=int(info["inventory"]),
            )


def load_ppo(path: Path) -> MaskablePPO:
    return MaskablePPO.load(path, device="cpu")
