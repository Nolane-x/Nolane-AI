from __future__ import annotations

from dataclasses import dataclass, field
import itertools
from typing import Any, Mapping

import torch
from torch import Tensor, nn

from native_core import TARGET_VISIBLE_FEATURE_INDEX, parameter_count
from latent_goal_core import (
    GOAL_CARDINALITY,
    GOAL_DIMENSIONS,
    NativeR4LatentGoalBeliefPolicy,
)

GOAL_HYPOTHESIS_COUNT = GOAL_CARDINALITY ** GOAL_DIMENSIONS
PROGRESS_DENOMINATOR = GOAL_DIMENSIONS * (GOAL_CARDINALITY - 1)


def _goal_table() -> Tensor:
    return torch.tensor(
        list(itertools.product(range(GOAL_CARDINALITY), repeat=GOAL_DIMENSIONS)),
        dtype=torch.long,
    )


GOAL_TABLE = _goal_table()


@dataclass
class PublicGoalConsistencyBelief:
    """Episode-local goal posterior using public state/progress only."""

    tolerance: float = 2.0e-6
    _posterior: Tensor = field(
        default_factory=lambda: torch.full(
            (GOAL_HYPOTHESIS_COUNT,),
            1.0 / GOAL_HYPOTHESIS_COUNT,
            dtype=torch.float32,
        )
    )

    def __post_init__(self) -> None:
        if float(self.tolerance) <= 0.0:
            raise ValueError("tolerance must be positive")
        if self._posterior.shape != (GOAL_HYPOTHESIS_COUNT,):
            raise ValueError("posterior shape mismatch")
        self._posterior = self._posterior.detach().clone().float()
        total = float(self._posterior.sum().item())
        if total <= 0.0:
            raise ValueError("posterior must have positive mass")
        self._posterior /= total

    @staticmethod
    def _state(observation: Mapping[str, Any]) -> Tensor:
        raw = observation.get("state")
        if not isinstance(raw, list) or len(raw) != GOAL_DIMENSIONS:
            raise ValueError("public state must contain three coordinates")
        values = [int(v) for v in raw]
        if any(v < 0 or v >= GOAL_CARDINALITY for v in values):
            raise ValueError("public state coordinate out of range")
        return torch.tensor(values, dtype=torch.long)

    @staticmethod
    def _progress(observation: Mapping[str, Any]) -> float:
        value = observation.get("progress_signal")
        if not isinstance(value, (int, float)):
            raise ValueError("public observation missing progress_signal")
        progress = float(value)
        if not -1.0e-6 <= progress <= 1.0 + 1.0e-6:
            raise ValueError("public progress_signal out of range")
        return progress

    def update(self, observation: Mapping[str, Any]) -> None:
        state = self._state(observation)
        progress = self._progress(observation)
        visible = observation.get("target")
        if isinstance(visible, list) and len(visible) == GOAL_DIMENSIONS:
            target = torch.tensor([int(v) for v in visible], dtype=torch.long)
            posterior = (GOAL_TABLE == target.unsqueeze(0)).all(dim=1).float()
            posterior /= posterior.sum()
            self._posterior = posterior
            return

        forward_distance = torch.remainder(
            GOAL_TABLE - state.unsqueeze(0),
            GOAL_CARDINALITY,
        ).sum(dim=1).float()
        expected_progress = 1.0 - forward_distance / float(PROGRESS_DENOMINATOR)
        error = (expected_progress - progress).abs()
        consistent = error <= float(self.tolerance)
        filtered = self._posterior * consistent.to(self._posterior.dtype)
        mass = float(filtered.sum().item())
        if mass <= 0.0:
            min_error = error.min()
            closest = error <= (min_error + float(self.tolerance))
            filtered = self._posterior * closest.to(self._posterior.dtype)
            mass = float(filtered.sum().item())
        if mass <= 0.0:
            raise ValueError("public consistency eliminated every hypothesis")
        self._posterior = filtered / mass

    def encode(self) -> Tensor:
        return self._posterior.detach().clone()

    def support_size(self) -> int:
        return int((self._posterior > 0.0).sum().item())


class NativeR8BeliefCorrectionPolicy(nn.Module):
    """Public posterior correction of frozen accepted R4 goal belief."""

    def __init__(
        self,
        parent: NativeR4LatentGoalBeliefPolicy,
        *,
        max_support: int = 1,
        correction_strength: float = 1.0,
    ) -> None:
        super().__init__()
        if int(max_support) < 1 or int(max_support) > GOAL_HYPOTHESIS_COUNT:
            raise ValueError("max_support must lie in [1,125]")
        if not 0.0 < float(correction_strength) <= 1.0:
            raise ValueError("correction_strength must lie in (0,1]")
        self.parent = parent
        self.max_support = int(max_support)
        self.correction_strength = float(correction_strength)
        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)
        self.parent.eval()

        goal_onehot = torch.zeros(
            GOAL_HYPOTHESIS_COUNT,
            GOAL_DIMENSIONS * GOAL_CARDINALITY,
        )
        for row, goal in enumerate(GOAL_TABLE.tolist()):
            for dimension, value in enumerate(goal):
                goal_onehot[row, dimension * GOAL_CARDINALITY + value] = 1.0
        self.register_buffer("goal_onehot", goal_onehot, persistent=True)

    def train(self, mode: bool = True) -> "NativeR8BeliefCorrectionPolicy":
        super().train(mode)
        self.parent.eval()
        return self

    def architecture(self) -> dict[str, Any]:
        return {
            **self.parent.architecture(),
            "r8_max_support": self.max_support,
            "r8_correction_strength": self.correction_strength,
            "r8_goal_hypothesis_count": GOAL_HYPOTHESIS_COUNT,
        }

    def successor_parameters(self) -> list[nn.Parameter]:
        return []

    def successor_parameter_count(self) -> int:
        return 0

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
        consistency_posterior: Tensor,
    ) -> dict[str, Tensor]:
        if consistency_posterior.ndim != 2:
            raise ValueError("consistency_posterior must be [batch,125]")
        if consistency_posterior.shape[-1] != GOAL_HYPOTHESIS_COUNT:
            raise ValueError("consistency_posterior width mismatch")
        if consistency_posterior.shape[0] != global_features.shape[0]:
            raise ValueError("consistency_posterior batch mismatch")
        if bool((consistency_posterior < 0.0).any()):
            raise ValueError("consistency_posterior must be non-negative")
        mass = consistency_posterior.sum(dim=-1, keepdim=True)
        if not bool((mass > 0.0).all()):
            raise ValueError("each posterior row needs positive mass")
        posterior = consistency_posterior / mass

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
            parent_logits = parent_output["action_logits"]
            r3_logits = parent_output["parent_action_logits"]
            parent_goal = parent_output["goal_probabilities"]
            next_parent_hidden = parent_output["next_parent_hidden"]
            r2_trace_hidden = parent_output["r2_trace_hidden"]
            r3_attribution_hidden = parent_output["r3_attribution_hidden"]

            public_marginals = (
                posterior @ self.goal_onehot.to(posterior.dtype)
            ).view(
                posterior.shape[0],
                GOAL_DIMENSIONS,
                GOAL_CARDINALITY,
            )
            support_count = (posterior > 0.0).sum(dim=-1, keepdim=True)
            public_sharp = support_count <= self.max_support
            target_visible = global_features[
                :,
                TARGET_VISIBLE_FEATURE_INDEX : TARGET_VISIBLE_FEATURE_INDEX + 1,
            ] >= 0.5
            correction_active = public_sharp & (~target_visible)

            strength = float(self.correction_strength)
            corrected_goal = (
                parent_goal * (1.0 - strength)
                + public_marginals * strength
            )
            corrected_embedding = self.parent.goal_projection(
                corrected_goal.flatten(1)
            )
            action_tokens = (
                self.parent.parent.parent.parent.action_encoder(action_features)
            )
            batch, actions, _ = action_tokens.shape
            expanded = [
                value[:, None, :].expand(batch, actions, value.shape[-1])
                for value in (
                    next_parent_hidden,
                    r2_trace_hidden,
                    r3_attribution_hidden,
                    corrected_embedding,
                )
            ]
            residual_input = torch.cat((action_tokens, *expanded), dim=-1)
            corrected_residual = self.parent.hidden_target_goal_score(
                residual_input
            ).squeeze(-1)
            corrected_logits = (r3_logits + corrected_residual).masked_fill(
                ~valid_actions,
                torch.finfo(r3_logits.dtype).min,
            )
            logits = torch.where(
                correction_active,
                corrected_logits,
                parent_logits,
            )

        return {
            "action_logits": logits,
            "parent_action_logits": parent_logits,
            "corrected_action_logits": corrected_logits,
            "parent_goal_probabilities": parent_goal,
            "public_goal_marginals": public_marginals,
            "corrected_goal_probabilities": corrected_goal,
            "consistency_support": support_count.squeeze(-1),
            "correction_active": correction_active.squeeze(-1),
            "next_parent_hidden": next_parent_hidden,
            "r2_trace_hidden": r2_trace_hidden,
            "r3_attribution_hidden": r3_attribution_hidden,
        }
