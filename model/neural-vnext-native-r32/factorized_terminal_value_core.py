from __future__ import annotations

from typing import Any, Mapping

import torch
from torch import Tensor, nn

from native_core import ACTION_FEATURE_DIM, state_dict_sha256
from public_planner import GOAL_CARDINALITY, GOAL_DIMENSIONS, GOAL_HYPOTHESIS_COUNT

STATE_ONEHOT_DIM = GOAL_DIMENSIONS * GOAL_CARDINALITY
PUBLIC_GOAL_FEATURE_DIM = GOAL_HYPOTHESIS_COUNT + STATE_ONEHOT_DIM + 6

BELIEF_HIDDEN_DIM = 96
GOAL_EMBEDDING_DIM = 48
NATIVE_HIDDEN_DIM = 128
TRACE_HIDDEN_DIM = 128
ATTRIBUTION_HIDDEN_DIM = 128
LATENT_CONTEXT_DIM = (
    BELIEF_HIDDEN_DIM
    + GOAL_EMBEDDING_DIM
    + NATIVE_HIDDEN_DIM
    + TRACE_HIDDEN_DIM
    + ATTRIBUTION_HIDDEN_DIM
)

ACTION_VALUE_SCALAR_DIM = 13
ACTION_VALUE_FEATURE_DIM = (
    PUBLIC_GOAL_FEATURE_DIM
    + ACTION_FEATURE_DIM
    + STATE_ONEHOT_DIM
    + LATENT_CONTEXT_DIM
    + ACTION_VALUE_SCALAR_DIM
)


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


def state_onehot_optional(state: Tensor | list[int] | tuple[int, ...] | None) -> Tensor:
    if state is None:
        return torch.zeros(STATE_ONEHOT_DIM, dtype=torch.float32)
    return state_onehot(state)


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
        raise AssertionError("unexpected R32 public goal feature shape")
    return features


def _single_batch_vector(
    parent_output: Mapping[str, Tensor],
    key: str,
    expected_dim: int,
) -> Tensor:
    value = parent_output.get(key)
    if not isinstance(value, Tensor):
        raise ValueError(f"missing accepted-R4 latent tensor: {key}")
    if value.shape != (1, int(expected_dim)):
        raise ValueError(
            f"accepted-R4 latent tensor {key} must have shape [1,{expected_dim}], got {tuple(value.shape)}"
        )
    return value[0].detach().float()


def encode_parent_latent_context(parent_output: Mapping[str, Tensor]) -> Tensor:
    latent = torch.cat(
        (
            _single_batch_vector(parent_output, "belief_hidden", BELIEF_HIDDEN_DIM),
            _single_batch_vector(parent_output, "goal_embedding", GOAL_EMBEDDING_DIM),
            _single_batch_vector(parent_output, "next_parent_hidden", NATIVE_HIDDEN_DIM),
            _single_batch_vector(parent_output, "r2_trace_hidden", TRACE_HIDDEN_DIM),
            _single_batch_vector(
                parent_output,
                "r3_attribution_hidden",
                ATTRIBUTION_HIDDEN_DIM,
            ),
        ),
        dim=0,
    )
    if latent.shape != (LATENT_CONTEXT_DIM,):
        raise AssertionError("unexpected R32 parent latent context shape")
    if not bool(torch.isfinite(latent).all().item()):
        raise ValueError("accepted-R4 latent context contains non-finite values")
    return latent


def encode_action_value_features(
    *,
    public_goal_features: Tensor,
    latent_context: Tensor,
    action_features: Tensor,
    action_next_state: Tensor | None,
    support_count: int,
    action_min_mass: float,
    action_mean_mass: float,
    action_max_mass: float,
    action_mass_spread: float,
    parent_logit_margin_vs_r11: float,
    action_certified: bool,
    action_rule_count: int,
    current_expected_distance: float,
    action_expected_distance: float,
    expected_distance_improvement: float,
    action_seen_in_context: int,
    is_r11_action: bool,
) -> Tensor:
    if public_goal_features.shape != (PUBLIC_GOAL_FEATURE_DIM,):
        raise ValueError("public goal feature shape mismatch")
    if latent_context.shape != (LATENT_CONTEXT_DIM,):
        raise ValueError("latent context shape mismatch")
    if action_features.shape != (ACTION_FEATURE_DIM,):
        raise ValueError("action feature shape mismatch")

    scalars = torch.tensor(
        [
            min(1.0, float(support_count) / float(GOAL_HYPOTHESIS_COUNT)),
            float(action_min_mass),
            float(action_mean_mass),
            float(action_max_mass),
            float(action_mass_spread),
            float(parent_logit_margin_vs_r11),
            float(bool(action_certified)),
            min(1.0, float(action_rule_count) / 18.0),
            float(current_expected_distance) / 12.0,
            float(action_expected_distance) / 12.0,
            float(expected_distance_improvement) / 12.0,
            min(1.0, float(action_seen_in_context) / 8.0),
            float(bool(is_r11_action)),
        ],
        dtype=torch.float32,
    )
    features = torch.cat(
        (
            public_goal_features.float(),
            action_features.float(),
            state_onehot_optional(action_next_state),
            latent_context.float(),
            scalars,
        ),
        dim=0,
    )
    if features.shape != (ACTION_VALUE_FEATURE_DIM,):
        raise AssertionError("unexpected R32 action-value feature shape")
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


class _TerminalValueHead(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(ACTION_VALUE_FEATURE_DIM, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, features: Tensor) -> Tensor:
        return self.net(features).squeeze(-1)


class NativeR32FactorizedTerminalValueEnsemble(nn.Module):
    """Predicts terminal solve value for each first action; rescue/harm are derived pairwise."""

    def __init__(
        self,
        *,
        ensemble_size: int = 3,
        goal_hidden_dim: int = 96,
        value_hidden_dim: int = 64,
    ) -> None:
        super().__init__()
        if ensemble_size < 2:
            raise ValueError("ensemble_size must be >=2")
        self.ensemble_size = int(ensemble_size)
        self.goal_hidden_dim = int(goal_hidden_dim)
        self.value_hidden_dim = int(value_hidden_dim)
        self.goal_heads = nn.ModuleList(
            [_GoalBeliefHead(self.goal_hidden_dim) for _ in range(self.ensemble_size)]
        )
        self.value_heads = nn.ModuleList(
            [_TerminalValueHead(self.value_hidden_dim) for _ in range(self.ensemble_size)]
        )

    def architecture(self) -> dict[str, Any]:
        return {
            "r32_ensemble_size": self.ensemble_size,
            "r32_goal_hidden_dim": self.goal_hidden_dim,
            "r32_value_hidden_dim": self.value_hidden_dim,
            "r32_public_goal_feature_dim": PUBLIC_GOAL_FEATURE_DIM,
            "r32_latent_context_dim": LATENT_CONTEXT_DIM,
            "r32_action_value_feature_dim": ACTION_VALUE_FEATURE_DIM,
            "mechanism": "per_action_terminal_solve_value_then_pairwise_rescue_harm_derivation",
        }

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def goal_parameter_count(self) -> int:
        return sum(
            parameter.numel()
            for head in self.goal_heads
            for parameter in head.parameters()
        )

    def value_parameter_count(self) -> int:
        return sum(
            parameter.numel()
            for head in self.value_heads
            for parameter in head.parameters()
        )

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

    def solve_probabilities(self, features: Tensor) -> Tensor:
        if features.shape != (ACTION_VALUE_FEATURE_DIM,):
            raise ValueError("R32 action-value feature shape mismatch")
        logits = torch.stack(
            [head(features.unsqueeze(0))[0] for head in self.value_heads], dim=0
        )
        return torch.sigmoid(logits)
