from __future__ import annotations

from itertools import product
import math
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor, nn

from native_core import (
    ACTION_FEATURE_DIM,
    TARGET_VISIBLE_FEATURE_INDEX,
    parameter_count,
    state_dict_sha256,
)
from attributed_core import NativeR3AttributedBeliefPolicy


GOAL_MODULUS = 5
GOAL_DIMENSIONS = 3
GOAL_CANDIDATES = GOAL_MODULUS ** GOAL_DIMENSIONS
GOAL_MARGINAL_DIM = GOAL_DIMENSIONS * GOAL_MODULUS
GOAL_BELIEF_FEATURE_DIM = GOAL_CANDIDATES + GOAL_MARGINAL_DIM + 2


class PublicGoalConsistencyBelief:
    """Exact public-only consistency filter over the 5^3 hidden-goal space.

    FIGG-18 exposes state and a scalar progress signal publicly. For hidden-goal
    worlds the signal equals 1 - sum(forward_distance(state_i, goal_i)) / 12.
    This tracker never reads private task fields: it intersects candidate goals
    that are mathematically consistent with each public observation.
    """

    def __init__(self) -> None:
        self._goals = tuple(product(range(GOAL_MODULUS), repeat=GOAL_DIMENSIONS))
        self._active = [True] * len(self._goals)
        self.observations = 0

    @staticmethod
    def _state(observation: Mapping[str, Any]) -> tuple[int, int, int]:
        raw = observation.get("state")
        if not isinstance(raw, list) or len(raw) != GOAL_DIMENSIONS:
            raise ValueError("public state must contain exactly three coordinates")
        state = tuple(int(value) for value in raw)
        if any(value < 0 or value >= GOAL_MODULUS for value in state):
            raise ValueError("public state coordinate outside R4 goal modulus")
        return state  # type: ignore[return-value]

    @staticmethod
    def _distance_sum(
        state: Sequence[int],
        goal: Sequence[int],
    ) -> int:
        return sum(
            (int(target) - int(value)) % GOAL_MODULUS
            for value, target in zip(state, goal)
        )

    @staticmethod
    def _public_distance(observation: Mapping[str, Any]) -> int:
        if "progress_signal" not in observation:
            raise ValueError("public observation is missing progress_signal")
        progress = float(observation["progress_signal"])
        raw_distance = (1.0 - progress) * float(
            GOAL_DIMENSIONS * (GOAL_MODULUS - 1)
        )
        nearest = int(round(raw_distance))
        # The benchmark rounds progress_signal to six decimals. Multiplying that
        # rounding error by 12 remains far below this fail-closed tolerance.
        if abs(raw_distance - nearest) > 2.0e-5:
            raise ValueError(
                "public progress signal is inconsistent with an exact FIGG-18 "
                f"goal distance: {progress}"
            )
        if not 0 <= nearest <= GOAL_DIMENSIONS * (GOAL_MODULUS - 1):
            raise ValueError("public goal distance outside valid range")
        return nearest

    def update(self, observation: Mapping[str, Any]) -> None:
        state = self._state(observation)
        target = observation.get("target")
        if isinstance(target, list) and len(target) == GOAL_DIMENSIONS:
            visible = tuple(int(value) for value in target)
            if any(value < 0 or value >= GOAL_MODULUS for value in visible):
                raise ValueError("visible target outside R4 goal modulus")
            self._active = [goal == visible for goal in self._goals]
            self.observations += 1
            return

        observed_distance = self._public_distance(observation)
        self._active = [
            active and self._distance_sum(state, goal) == observed_distance
            for active, goal in zip(self._active, self._goals)
        ]
        self.observations += 1
        if not any(self._active):
            raise ValueError(
                "public observations eliminated every hidden-goal candidate"
            )

    @property
    def candidate_count(self) -> int:
        return sum(int(active) for active in self._active)

    def contains(self, goal: Sequence[int]) -> bool:
        target = tuple(int(value) for value in goal)
        return any(
            active and candidate == target
            for active, candidate in zip(self._active, self._goals)
        )

    def encode(self) -> Tensor:
        count = self.candidate_count
        if count < 1:
            raise ValueError("cannot encode an empty public goal belief")
        probability = 1.0 / float(count)
        posterior = [
            probability if active else 0.0
            for active in self._active
        ]
        marginals: list[float] = []
        for dimension in range(GOAL_DIMENSIONS):
            for value in range(GOAL_MODULUS):
                marginals.append(
                    sum(
                        probability
                        for active, goal in zip(self._active, self._goals)
                        if active and goal[dimension] == value
                    )
                )
        normalized_count = float(count) / float(GOAL_CANDIDATES)
        normalized_entropy = (
            math.log(float(count)) / math.log(float(GOAL_CANDIDATES))
            if count > 1
            else 0.0
        )
        confidence = 1.0 - normalized_entropy
        values = posterior + marginals + [normalized_count, confidence]
        if len(values) != GOAL_BELIEF_FEATURE_DIM:
            raise AssertionError("unexpected public goal belief feature width")
        return torch.tensor(values, dtype=torch.float32)


class NativeR4PublicGoalBeliefPolicy(nn.Module):
    """Frozen accepted R3 plus a hidden-target public-consistency belief residual."""

    def __init__(
        self,
        parent: NativeR3AttributedBeliefPolicy,
        *,
        belief_feature_dim: int = GOAL_BELIEF_FEATURE_DIM,
        belief_hidden_dim: int = 128,
    ) -> None:
        super().__init__()
        if belief_feature_dim != GOAL_BELIEF_FEATURE_DIM:
            raise ValueError(
                f"belief_feature_dim must be {GOAL_BELIEF_FEATURE_DIM}"
            )
        if belief_hidden_dim < 1:
            raise ValueError("belief_hidden_dim must be positive")
        self.parent = parent
        self.belief_feature_dim = int(belief_feature_dim)
        self.belief_hidden_dim = int(belief_hidden_dim)

        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)
        self.parent.eval()

        native_hidden = int(parent.parent.parent.hidden_dim)
        r2_trace_hidden = int(parent.parent.trace_hidden_dim)
        attribution_hidden = int(parent.attribution_hidden_dim)

        self.belief_encoder = nn.Sequential(
            nn.Linear(self.belief_feature_dim, self.belief_hidden_dim),
            nn.GELU(),
            nn.LayerNorm(self.belief_hidden_dim),
        )
        residual_input = (
            native_hidden
            + native_hidden
            + r2_trace_hidden
            + attribution_hidden
            + self.belief_hidden_dim
        )
        self.hidden_target_belief_score = nn.Sequential(
            nn.Linear(residual_input, native_hidden),
            nn.GELU(),
            nn.LayerNorm(native_hidden),
            nn.Linear(native_hidden, 1),
        )
        nn.init.zeros_(self.hidden_target_belief_score[-1].weight)
        nn.init.zeros_(self.hidden_target_belief_score[-1].bias)

    def train(self, mode: bool = True) -> "NativeR4PublicGoalBeliefPolicy":
        super().train(mode)
        self.parent.eval()
        return self

    def architecture(self) -> dict[str, int]:
        return {
            "belief_feature_dim": self.belief_feature_dim,
            "belief_hidden_dim": self.belief_hidden_dim,
            "r3_attribution_token_dim": int(self.parent.attribution_token_dim),
            "r3_attribution_hidden_dim": int(self.parent.attribution_hidden_dim),
            "r3_attribution_length": int(self.parent.attribution_length),
            "r2_trace_token_dim": int(self.parent.parent.trace_token_dim),
            "r2_trace_hidden_dim": int(self.parent.parent.trace_hidden_dim),
            "r2_trace_length": int(self.parent.parent.trace_length),
            "native_global_dim": int(self.parent.parent.parent.global_dim),
            "native_action_dim": int(self.parent.parent.parent.action_dim),
            "native_hidden_dim": int(self.parent.parent.parent.hidden_dim),
            "native_attention_heads": int(
                self.parent.parent.parent.attention_heads
            ),
        }

    def successor_parameters(self) -> list[nn.Parameter]:
        modules = (
            self.belief_encoder,
            self.hidden_target_belief_score,
        )
        return [
            parameter
            for module in modules
            for parameter in module.parameters()
        ]

    def set_training_scope(self) -> None:
        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)
        for parameter in self.successor_parameters():
            parameter.requires_grad_(True)

    def successor_parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.successor_parameters())

    def full_parameter_count(self) -> int:
        return parameter_count(self)

    def init_parent_hidden(
        self,
        batch_size: int,
        *,
        device: torch.device | None = None,
    ) -> Tensor:
        return self.parent.init_parent_hidden(batch_size, device=device)

    def forward_step(
        self,
        global_features: Tensor,
        action_features: Tensor,
        valid_actions: Tensor,
        parent_hidden: Tensor,
        trace_features: Tensor,
        trace_valid: Tensor,
        attribution_features: Tensor,
        attribution_valid: Tensor,
        belief_features: Tensor,
    ) -> dict[str, Tensor]:
        if belief_features.ndim != 2:
            raise ValueError("belief_features must be [batch, belief_feature_dim]")
        if belief_features.shape[-1] != self.belief_feature_dim:
            raise ValueError("public goal belief feature width mismatch")

        with torch.no_grad():
            parent_output = self.parent.forward_step(
                global_features,
                action_features,
                valid_actions,
                parent_hidden,
                trace_features,
                trace_valid,
                attribution_features,
                attribution_valid,
            )
            parent_logits = parent_output["action_logits"].detach()
            next_parent_hidden = parent_output["next_parent_hidden"].detach()
            r2_trace_hidden = parent_output["r2_trace_hidden"].detach()
            attribution_hidden = parent_output["attribution_hidden"].detach()
            action_tokens = self.parent.parent.parent.action_encoder(
                action_features
            ).detach()

        batch, actions, _ = action_tokens.shape
        belief_hidden = self.belief_encoder(belief_features)
        native_expanded = next_parent_hidden[:, None, :].expand(
            batch, actions, next_parent_hidden.shape[-1]
        )
        trace_expanded = r2_trace_hidden[:, None, :].expand(
            batch, actions, r2_trace_hidden.shape[-1]
        )
        attribution_expanded = attribution_hidden[:, None, :].expand(
            batch, actions, attribution_hidden.shape[-1]
        )
        belief_expanded = belief_hidden[:, None, :].expand(
            batch, actions, belief_hidden.shape[-1]
        )
        residual_input = torch.cat(
            (
                action_tokens,
                native_expanded,
                trace_expanded,
                attribution_expanded,
                belief_expanded,
            ),
            dim=-1,
        )
        residual = self.hidden_target_belief_score(
            residual_input
        ).squeeze(-1)

        target_visible = global_features[
            :, TARGET_VISIBLE_FEATURE_INDEX : TARGET_VISIBLE_FEATURE_INDEX + 1
        ].clamp(0.0, 1.0)
        residual = residual * (1.0 - target_visible)
        residual = residual.masked_fill(~valid_actions, 0.0)
        logits = (parent_logits + residual).masked_fill(
            ~valid_actions,
            torch.finfo(parent_logits.dtype).min,
        )
        return {
            "action_logits": logits,
            "parent_action_logits": parent_logits,
            "belief_residual_logits": residual,
            "next_parent_hidden": next_parent_hidden,
            "r2_trace_hidden": r2_trace_hidden,
            "attribution_hidden": attribution_hidden,
            "belief_hidden": belief_hidden,
        }


def r4_state_dict_sha256(model: NativeR4PublicGoalBeliefPolicy) -> str:
    return state_dict_sha256(model.state_dict())
