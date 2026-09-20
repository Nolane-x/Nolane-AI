from __future__ import annotations

from typing import Any

import torch
from torch import Tensor, nn

from native_core import ACTION_FEATURE_DIM, state_dict_sha256
from public_planner import GOAL_CARDINALITY, GOAL_DIMENSIONS, GOAL_HYPOTHESIS_COUNT

STATE_ONEHOT_DIM = GOAL_DIMENSIONS * GOAL_CARDINALITY
TRANSITION_SCALAR_DIM = 7
TRANSITION_FEATURE_DIM = STATE_ONEHOT_DIM * 2 + ACTION_FEATURE_DIM + TRANSITION_SCALAR_DIM


def goal_index(goal: tuple[int, int, int] | list[int]) -> int:
    if len(goal) != GOAL_DIMENSIONS:
        raise ValueError("goal needs three dimensions")
    a, b, c = (int(v) for v in goal)
    if not all(0 <= v < GOAL_CARDINALITY for v in (a, b, c)):
        raise ValueError("goal value out of range")
    return a * GOAL_CARDINALITY * GOAL_CARDINALITY + b * GOAL_CARDINALITY + c


def _state_onehot(observation: dict[str, Any]) -> Tensor:
    state = observation.get("state")
    if not isinstance(state, list) or len(state) != GOAL_DIMENSIONS:
        raise ValueError("public state must contain three dimensions")
    encoded = torch.zeros(STATE_ONEHOT_DIM, dtype=torch.float32)
    for dim, value in enumerate(state):
        value = int(value)
        if not 0 <= value < GOAL_CARDINALITY:
            raise ValueError("public state value out of range")
        encoded[dim * GOAL_CARDINALITY + value] = 1.0
    return encoded


def encode_transition_evidence(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    selected_action_features: Tensor,
    progress_delta: float,
    information_gain: float,
    failed: bool,
) -> Tensor:
    if selected_action_features.shape != (ACTION_FEATURE_DIM,):
        raise ValueError("selected action features have wrong shape")
    scalars = torch.tensor(
        [
            float(before["progress_signal"]),
            float(after["progress_signal"]),
            float(progress_delta),
            float(information_gain),
            float(failed),
            min(1.0, float(after["step"]) / 32.0),
            min(1.0, float(after["budget_remaining"]) / 32.0),
        ],
        dtype=torch.float32,
    )
    features = torch.cat(
        (
            _state_onehot(before),
            _state_onehot(after),
            selected_action_features.float(),
            scalars,
        ),
        dim=0,
    )
    if features.shape != (TRANSITION_FEATURE_DIM,):
        raise AssertionError("unexpected R24 transition feature shape")
    return features


class _EvidenceHead(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(TRANSITION_FEATURE_DIM, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, GOAL_HYPOTHESIS_COUNT),
        )

    def forward(self, features: Tensor) -> Tensor:
        return self.net(features)


class NativeR24SequentialEvidenceEnsemble(nn.Module):
    """Learn additive public transition evidence for hidden-goal hypotheses.

    The model never receives the private goal at inference. Each public transition
    emits an evidence increment over the fixed 125-goal hypothesis space. Evidence
    is accumulated across the episode, then hard-masked by the exact public
    consistency support before any posterior can influence action choice.
    """

    def __init__(self, *, ensemble_size: int = 3, hidden_dim: int = 96) -> None:
        super().__init__()
        if ensemble_size < 2:
            raise ValueError("ensemble_size must be >=2")
        if hidden_dim < 1:
            raise ValueError("hidden_dim must be positive")
        self.ensemble_size = int(ensemble_size)
        self.hidden_dim = int(hidden_dim)
        self.heads = nn.ModuleList(
            [_EvidenceHead(self.hidden_dim) for _ in range(self.ensemble_size)]
        )

    def architecture(self) -> dict[str, Any]:
        return {
            "r24_ensemble_size": self.ensemble_size,
            "r24_hidden_dim": self.hidden_dim,
            "r24_transition_feature_dim": TRANSITION_FEATURE_DIM,
            "r24_goal_hypothesis_count": GOAL_HYPOTHESIS_COUNT,
            "mechanism": "additive_sequential_public_transition_evidence",
        }

    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def state_sha256(self) -> str:
        return state_dict_sha256(
            {
                name: tensor.detach().cpu().clone()
                for name, tensor in self.state_dict().items()
            }
        )

    def evidence_logits(self, features: Tensor) -> Tensor:
        if features.ndim != 2 or features.shape[-1] != TRANSITION_FEATURE_DIM:
            raise ValueError("R24 features must be [batch, transition_dim]")
        return torch.stack([head(features) for head in self.heads], dim=0)

    def posterior(
        self,
        *,
        cumulative_logits: Tensor,
        support_mask: Tensor,
        temperature: float,
    ) -> tuple[Tensor, Tensor]:
        if cumulative_logits.shape != (self.ensemble_size, GOAL_HYPOTHESIS_COUNT):
            raise ValueError("cumulative logits have wrong shape")
        if support_mask.shape != (GOAL_HYPOTHESIS_COUNT,):
            raise ValueError("support mask must be [125]")
        if float(temperature) <= 0.0:
            raise ValueError("temperature must be positive")
        masked = cumulative_logits.masked_fill(
            ~support_mask.bool().unsqueeze(0),
            torch.finfo(cumulative_logits.dtype).min,
        )
        per_head = torch.softmax(masked / float(temperature), dim=-1)
        mean = per_head.mean(dim=0) * support_mask.float()
        mass = mean.sum()
        if float(mass.item()) <= 0.0:
            support = support_mask.float()
            mean = support / support.sum().clamp_min(1.0)
        else:
            mean = mean / mass
        return mean, per_head

    def zero_cumulative_logits(self) -> Tensor:
        return torch.zeros(
            self.ensemble_size,
            GOAL_HYPOTHESIS_COUNT,
            dtype=torch.float32,
        )
