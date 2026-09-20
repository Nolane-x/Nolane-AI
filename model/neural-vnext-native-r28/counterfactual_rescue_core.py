from __future__ import annotations

from typing import Any

import torch
from torch import Tensor, nn

from native_core import ACTION_FEATURE_DIM, state_dict_sha256
from public_planner import GOAL_CARDINALITY, GOAL_DIMENSIONS, GOAL_HYPOTHESIS_COUNT

PUBLIC_GOAL_FEATURE_DIM = GOAL_HYPOTHESIS_COUNT + GOAL_DIMENSIONS * GOAL_CARDINALITY + 6
RESCUE_SCALAR_DIM = 4
RESCUE_FEATURE_DIM = PUBLIC_GOAL_FEATURE_DIM + ACTION_FEATURE_DIM * 2 + RESCUE_SCALAR_DIM


def goal_index(goal: tuple[int, int, int] | list[int]) -> int:
    if len(goal) != GOAL_DIMENSIONS:
        raise ValueError("goal needs three dimensions")
    a, b, c = (int(v) for v in goal)
    if not all(0 <= v < GOAL_CARDINALITY for v in (a, b, c)):
        raise ValueError("goal value out of range")
    return a * GOAL_CARDINALITY * GOAL_CARDINALITY + b * GOAL_CARDINALITY + c


def encode_public_goal_features(
    *,
    support_mask: Tensor,
    observation: dict[str, Any],
    previous_feedback: list[float] | tuple[float, float, float],
) -> Tensor:
    if support_mask.shape != (GOAL_HYPOTHESIS_COUNT,):
        raise ValueError("support_mask must have shape [125]")
    state = observation.get("state")
    if not isinstance(state, list) or len(state) != GOAL_DIMENSIONS:
        raise ValueError("public state must contain three dimensions")
    onehot = torch.zeros(GOAL_DIMENSIONS * GOAL_CARDINALITY, dtype=torch.float32)
    for dim, value in enumerate(state):
        value = int(value)
        if not 0 <= value < GOAL_CARDINALITY:
            raise ValueError("public state value out of range")
        onehot[dim * GOAL_CARDINALITY + value] = 1.0
    feedback = [float(v) for v in previous_feedback]
    if len(feedback) != 3:
        raise ValueError("previous_feedback must contain three values")
    scalars = torch.tensor(
        [
            float(observation["progress_signal"]),
            min(1.0, float(observation["budget_remaining"]) / 32.0),
            min(1.0, float(observation["step"]) / 32.0),
            feedback[0],
            feedback[1],
            feedback[2],
        ],
        dtype=torch.float32,
    )
    features = torch.cat((support_mask.float(), onehot, scalars), dim=0)
    if features.shape != (PUBLIC_GOAL_FEATURE_DIM,):
        raise AssertionError("unexpected R28 public goal feature shape")
    return features


def encode_rescue_features(
    *,
    public_goal_features: Tensor,
    r11_action_features: Tensor,
    candidate_action_features: Tensor,
    minimum_action_mass: float,
    mean_action_mass: float,
    mean_r11_action_mass: float,
    support_count: int,
) -> Tensor:
    if public_goal_features.shape != (PUBLIC_GOAL_FEATURE_DIM,):
        raise ValueError("public goal feature shape mismatch")
    if r11_action_features.shape != (ACTION_FEATURE_DIM,):
        raise ValueError("R11 action feature shape mismatch")
    if candidate_action_features.shape != (ACTION_FEATURE_DIM,):
        raise ValueError("candidate action feature shape mismatch")
    scalars = torch.tensor(
        [
            float(minimum_action_mass),
            float(mean_action_mass),
            float(mean_r11_action_mass),
            min(1.0, float(support_count) / float(GOAL_HYPOTHESIS_COUNT)),
        ],
        dtype=torch.float32,
    )
    features = torch.cat(
        (
            public_goal_features.float(),
            r11_action_features.float(),
            candidate_action_features.float(),
            scalars,
        ),
        dim=0,
    )
    if features.shape != (RESCUE_FEATURE_DIM,):
        raise AssertionError("unexpected R28 rescue feature shape")
    return features


class _GoalBeliefHead(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(PUBLIC_GOAL_FEATURE_DIM, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, GOAL_HYPOTHESIS_COUNT),
        )

    def forward(self, features: Tensor) -> Tensor:
        return self.net(features)


class _RescueHead(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(RESCUE_FEATURE_DIM, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, features: Tensor) -> Tensor:
        return self.net(features).squeeze(-1)


class NativeR28CounterfactualRescueEnsemble(nn.Module):
    """Public action-mass candidate generator plus learned episode-rescue gate."""

    def __init__(
        self,
        *,
        ensemble_size: int = 3,
        goal_hidden_dim: int = 96,
        rescue_hidden_dim: int = 64,
    ) -> None:
        super().__init__()
        if ensemble_size < 2:
            raise ValueError("ensemble_size must be >=2")
        self.ensemble_size = int(ensemble_size)
        self.goal_hidden_dim = int(goal_hidden_dim)
        self.rescue_hidden_dim = int(rescue_hidden_dim)
        self.goal_heads = nn.ModuleList(
            [_GoalBeliefHead(self.goal_hidden_dim) for _ in range(self.ensemble_size)]
        )
        self.rescue_heads = nn.ModuleList(
            [_RescueHead(self.rescue_hidden_dim) for _ in range(self.ensemble_size)]
        )

    def architecture(self) -> dict[str, Any]:
        return {
            "r28_ensemble_size": self.ensemble_size,
            "r28_goal_hidden_dim": self.goal_hidden_dim,
            "r28_rescue_hidden_dim": self.rescue_hidden_dim,
            "r28_public_goal_feature_dim": PUBLIC_GOAL_FEATURE_DIM,
            "r28_rescue_feature_dim": RESCUE_FEATURE_DIM,
            "r28_goal_hypothesis_count": GOAL_HYPOTHESIS_COUNT,
            "mechanism": "action_mass_candidate_plus_counterfactual_episode_rescue_value",
        }

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def goal_parameter_count(self) -> int:
        return sum(parameter.numel() for head in self.goal_heads for parameter in head.parameters())

    def rescue_parameter_count(self) -> int:
        return sum(parameter.numel() for head in self.rescue_heads for parameter in head.parameters())

    def state_sha256(self) -> str:
        return state_dict_sha256(
            {
                name: tensor.detach().cpu().clone()
                for name, tensor in self.state_dict().items()
            }
        )

    def per_head_goal_probabilities(
        self,
        *,
        features: Tensor,
        support_mask: Tensor,
        temperature: float,
    ) -> Tensor:
        if features.ndim != 1 or features.shape[0] != PUBLIC_GOAL_FEATURE_DIM:
            raise ValueError("R28 expects one public feature row")
        if support_mask.shape != (GOAL_HYPOTHESIS_COUNT,):
            raise ValueError("support mask must be [125]")
        if float(temperature) <= 0.0:
            raise ValueError("temperature must be positive")
        logits = torch.stack(
            [head(features.unsqueeze(0))[0] for head in self.goal_heads], dim=0
        )
        masked = logits.masked_fill(
            ~support_mask.bool().unsqueeze(0),
            torch.finfo(logits.dtype).min,
        )
        probabilities = torch.softmax(masked / float(temperature), dim=-1)
        probabilities = probabilities * support_mask.float().unsqueeze(0)
        probabilities = probabilities / probabilities.sum(
            dim=-1, keepdim=True
        ).clamp_min(1.0e-12)
        return probabilities

    def rescue_probabilities(self, features: Tensor) -> Tensor:
        if features.shape != (RESCUE_FEATURE_DIM,):
            raise ValueError("R28 rescue feature shape mismatch")
        return torch.stack(
            [torch.sigmoid(head(features.unsqueeze(0))[0]) for head in self.rescue_heads],
            dim=0,
        )
