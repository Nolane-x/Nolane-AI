from __future__ import annotations

from typing import Any

import torch
from torch import Tensor, nn

from native_core import state_dict_sha256
from public_planner import GOAL_CARDINALITY, GOAL_DIMENSIONS, GOAL_HYPOTHESIS_COUNT

PUBLIC_GOAL_FEATURE_DIM = GOAL_HYPOTHESIS_COUNT + GOAL_DIMENSIONS * GOAL_CARDINALITY + 6


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
        raise AssertionError("unexpected R23 public goal feature shape")
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


class NativeR23GoalBeliefEnsemble(nn.Module):
    def __init__(self, *, ensemble_size: int = 3, hidden_dim: int = 96) -> None:
        super().__init__()
        if ensemble_size < 2:
            raise ValueError("ensemble_size must be >=2")
        if hidden_dim < 1:
            raise ValueError("hidden_dim must be positive")
        self.ensemble_size = int(ensemble_size)
        self.hidden_dim = int(hidden_dim)
        self.heads = nn.ModuleList([_GoalBeliefHead(self.hidden_dim) for _ in range(self.ensemble_size)])

    def architecture(self) -> dict[str, Any]:
        return {
            "r23_ensemble_size": self.ensemble_size,
            "r23_hidden_dim": self.hidden_dim,
            "r23_public_goal_feature_dim": PUBLIC_GOAL_FEATURE_DIM,
            "r23_goal_hypothesis_count": GOAL_HYPOTHESIS_COUNT,
        }

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def state_sha256(self) -> str:
        return state_dict_sha256(
            {name: tensor.detach().cpu().clone() for name, tensor in self.state_dict().items()}
        )

    def ensemble_logits(self, features: Tensor) -> Tensor:
        if features.ndim != 2 or features.shape[-1] != PUBLIC_GOAL_FEATURE_DIM:
            raise ValueError("R23 features must be [batch,dim]")
        return torch.stack([head(features) for head in self.heads], dim=0)

    def probabilities(
        self,
        *,
        features: Tensor,
        support_mask: Tensor,
        temperature: float,
    ) -> tuple[Tensor, Tensor]:
        if features.ndim != 1 or features.shape[0] != PUBLIC_GOAL_FEATURE_DIM:
            raise ValueError("R23 probabilities expect one feature row")
        if support_mask.shape != (GOAL_HYPOTHESIS_COUNT,):
            raise ValueError("support_mask must be [125]")
        if float(temperature) <= 0.0:
            raise ValueError("temperature must be positive")
        logits = self.ensemble_logits(features.unsqueeze(0))[:, 0, :]
        masked = logits.masked_fill(
            ~support_mask.bool().unsqueeze(0),
            torch.finfo(logits.dtype).min,
        )
        per_head = torch.softmax(masked / float(temperature), dim=-1)
        mean = per_head.mean(dim=0) * support_mask.float()
        mass = mean.sum()
        if float(mass.item()) <= 0.0:
            support = support_mask.float()
            mean = support / support.sum()
        else:
            mean = mean / mass
        return mean, per_head
