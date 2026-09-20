from __future__ import annotations

from typing import Any

import torch
from torch import Tensor, nn

from native_core import ACTION_FEATURE_DIM, state_dict_sha256
from public_planner import GOAL_CARDINALITY, GOAL_DIMENSIONS, GOAL_HYPOTHESIS_COUNT

STATE_ONEHOT_DIM = GOAL_DIMENSIONS * GOAL_CARDINALITY
PUBLIC_GOAL_FEATURE_DIM = GOAL_HYPOTHESIS_COUNT + STATE_ONEHOT_DIM + 6
GEOMETRY_SCALAR_DIM = 12
RESCUE_FEATURE_DIM = (
    PUBLIC_GOAL_FEATURE_DIM
    + ACTION_FEATURE_DIM * 2
    + STATE_ONEHOT_DIM * 2
    + GEOMETRY_SCALAR_DIM
)
RESCUE_CLASS_COUNT = 3
NEUTRAL_CLASS = 0
RESCUE_CLASS = 1
HARM_CLASS = 2


def goal_index(goal: tuple[int, int, int] | list[int]) -> int:
    if len(goal) != GOAL_DIMENSIONS:
        raise ValueError("goal needs three dimensions")
    a, b, c = (int(v) for v in goal)
    if not all(0 <= v < GOAL_CARDINALITY for v in (a, b, c)):
        raise ValueError("goal value out of range")
    return a * GOAL_CARDINALITY * GOAL_CARDINALITY + b * GOAL_CARDINALITY + c


def state_onehot(state: Tensor | list[int] | tuple[int, ...]) -> Tensor:
    values = [int(v) for v in (state.tolist() if isinstance(state, Tensor) else state)]
    if len(values) != GOAL_DIMENSIONS:
        raise ValueError("state needs three dimensions")
    out = torch.zeros(STATE_ONEHOT_DIM, dtype=torch.float32)
    for dim, value in enumerate(values):
        if not 0 <= value < GOAL_CARDINALITY:
            raise ValueError("state value out of range")
        out[dim * GOAL_CARDINALITY + value] = 1.0
    return out


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
    features = torch.cat((support_mask.float(), state_onehot(state), scalars), dim=0)
    if features.shape != (PUBLIC_GOAL_FEATURE_DIM,):
        raise AssertionError("unexpected R29 public goal feature shape")
    return features


def encode_rescue_geometry_features(
    *,
    public_goal_features: Tensor,
    r11_action_features: Tensor,
    candidate_action_features: Tensor,
    r11_next_state: Tensor,
    candidate_next_state: Tensor,
    minimum_action_mass: float,
    mean_action_mass: float,
    mean_r11_action_mass: float,
    support_count: int,
    r11_rule_count: int,
    candidate_rule_count: int,
    current_expected_distance: float,
    r11_expected_distance: float,
    candidate_expected_distance: float,
    action_mass_margin: float,
    distance_advantage: float,
    rule_count_advantage: float,
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
            min(1.0, float(r11_rule_count) / 18.0),
            min(1.0, float(candidate_rule_count) / 18.0),
            float(current_expected_distance) / 12.0,
            float(r11_expected_distance) / 12.0,
            float(candidate_expected_distance) / 12.0,
            float(action_mass_margin),
            float(distance_advantage) / 12.0,
            float(rule_count_advantage) / 18.0,
        ],
        dtype=torch.float32,
    )
    features = torch.cat(
        (
            public_goal_features.float(),
            r11_action_features.float(),
            candidate_action_features.float(),
            state_onehot(r11_next_state),
            state_onehot(candidate_next_state),
            scalars,
        ),
        dim=0,
    )
    if features.shape != (RESCUE_FEATURE_DIM,):
        raise AssertionError("unexpected R29 rescue feature shape")
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


class _RescueGeometryHead(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(RESCUE_FEATURE_DIM, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, RESCUE_CLASS_COUNT),
        )

    def forward(self, features: Tensor) -> Tensor:
        return self.net(features)


class NativeR29CertifiedRescueEnsemble(nn.Module):
    """Action-mass candidate generator plus certified rescue/harm geometry classifier."""

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
            [_RescueGeometryHead(self.rescue_hidden_dim) for _ in range(self.ensemble_size)]
        )

    def architecture(self) -> dict[str, Any]:
        return {
            "r29_ensemble_size": self.ensemble_size,
            "r29_goal_hidden_dim": self.goal_hidden_dim,
            "r29_rescue_hidden_dim": self.rescue_hidden_dim,
            "r29_public_goal_feature_dim": PUBLIC_GOAL_FEATURE_DIM,
            "r29_rescue_feature_dim": RESCUE_FEATURE_DIM,
            "r29_rescue_class_count": RESCUE_CLASS_COUNT,
            "mechanism": "certified_counterfactual_geometry_with_neutral_rescue_harm_classifier",
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
        logits = torch.stack(
            [head(features.unsqueeze(0))[0] for head in self.goal_heads], dim=0
        )
        masked = logits.masked_fill(
            ~support_mask.bool().unsqueeze(0),
            torch.finfo(logits.dtype).min,
        )
        probabilities = torch.softmax(masked / float(temperature), dim=-1)
        probabilities = probabilities * support_mask.float().unsqueeze(0)
        return probabilities / probabilities.sum(dim=-1, keepdim=True).clamp_min(1.0e-12)

    def rescue_class_probabilities(self, features: Tensor) -> Tensor:
        if features.shape != (RESCUE_FEATURE_DIM,):
            raise ValueError("R29 rescue feature shape mismatch")
        logits = torch.stack(
            [head(features.unsqueeze(0))[0] for head in self.rescue_heads], dim=0
        )
        return torch.softmax(logits, dim=-1)
