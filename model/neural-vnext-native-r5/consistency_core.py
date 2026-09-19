from __future__ import annotations

from dataclasses import dataclass, field
import itertools
from typing import Any, Mapping

import torch
from torch import Tensor, nn

from native_core import TARGET_VISIBLE_FEATURE_INDEX, parameter_count, state_dict_sha256
from latent_goal_core import NativeR4LatentGoalBeliefPolicy

GOAL_CARDINALITY = 5
GOAL_DIMENSIONS = 3
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
    """Episode-local hidden-goal posterior derived only from public state/progress."""

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
            raise ValueError("public observation state must contain three coordinates")
        values = [int(value) for value in raw]
        if any(value < 0 or value >= GOAL_CARDINALITY for value in values):
            raise ValueError("public state coordinate out of range")
        return torch.tensor(values, dtype=torch.long)

    @staticmethod
    def _progress(observation: Mapping[str, Any]) -> float:
        value = observation.get("progress_signal")
        if not isinstance(value, (int, float)):
            raise ValueError("public observation is missing progress_signal")
        progress = float(value)
        if not -1.0e-6 <= progress <= 1.0 + 1.0e-6:
            raise ValueError("public progress_signal out of range")
        return progress

    def update(self, observation: Mapping[str, Any]) -> None:
        state = self._state(observation)
        progress = self._progress(observation)
        visible = observation.get("target")
        if isinstance(visible, list) and len(visible) == GOAL_DIMENSIONS:
            target = torch.tensor([int(value) for value in visible], dtype=torch.long)
            match = (GOAL_TABLE == target.unsqueeze(0)).all(dim=1)
            posterior = match.to(torch.float32)
            posterior /= posterior.sum()
            self._posterior = posterior
            return

        forward_distance = torch.remainder(
            GOAL_TABLE - state.unsqueeze(0),
            GOAL_CARDINALITY,
        ).sum(dim=1).to(torch.float32)
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
            raise ValueError("public consistency update eliminated every goal hypothesis")
        self._posterior = filtered / mass

    def encode(self) -> Tensor:
        return self._posterior.detach().clone()

    def support_size(self) -> int:
        return int((self._posterior > 0.0).sum().item())


class NativeR5PublicConsistencyPolicy(nn.Module):
    """Frozen accepted R4 plus a public-consistency posterior neural residual."""

    def __init__(
        self,
        parent: NativeR4LatentGoalBeliefPolicy,
        *,
        consistency_embedding_dim: int = 64,
        residual_hidden_dim: int = 160,
    ) -> None:
        super().__init__()
        if consistency_embedding_dim < 1:
            raise ValueError("consistency_embedding_dim must be positive")
        if residual_hidden_dim < 1:
            raise ValueError("residual_hidden_dim must be positive")
        self.parent = parent
        self.consistency_embedding_dim = int(consistency_embedding_dim)
        self.residual_hidden_dim = int(residual_hidden_dim)
        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)
        self.parent.eval()

        native_hidden = int(parent.parent.parent.parent.hidden_dim)
        r2_trace_hidden = int(parent.parent.parent.trace_hidden_dim)
        r3_attribution_hidden = int(parent.parent.attribution_hidden_dim)
        r4_belief_hidden = int(parent.belief_hidden_dim)
        r4_goal_embedding = int(parent.goal_embedding_dim)

        self.consistency_projection = nn.Sequential(
            nn.Linear(GOAL_HYPOTHESIS_COUNT, self.consistency_embedding_dim),
            nn.GELU(),
            nn.LayerNorm(self.consistency_embedding_dim),
        )
        goal_onehot = torch.zeros(
            GOAL_HYPOTHESIS_COUNT,
            GOAL_DIMENSIONS * GOAL_CARDINALITY,
        )
        for row, goal in enumerate(GOAL_TABLE.tolist()):
            for dimension, value in enumerate(goal):
                goal_onehot[
                    row,
                    dimension * GOAL_CARDINALITY + value,
                ] = 1.0
        self.register_buffer("goal_onehot", goal_onehot, persistent=True)

        residual_input = (
            native_hidden
            + native_hidden
            + r2_trace_hidden
            + r3_attribution_hidden
            + r4_belief_hidden
            + r4_goal_embedding
            + self.consistency_embedding_dim
            + GOAL_DIMENSIONS * GOAL_CARDINALITY
            + 2
        )
        self.hidden_target_consistency_score = nn.Sequential(
            nn.Linear(residual_input, self.residual_hidden_dim),
            nn.GELU(),
            nn.LayerNorm(self.residual_hidden_dim),
            nn.Linear(self.residual_hidden_dim, 1),
        )
        nn.init.zeros_(self.hidden_target_consistency_score[-1].weight)
        nn.init.zeros_(self.hidden_target_consistency_score[-1].bias)

    def train(self, mode: bool = True) -> "NativeR5PublicConsistencyPolicy":
        super().train(mode)
        self.parent.eval()
        return self

    def architecture(self) -> dict[str, int]:
        return {
            **self.parent.architecture(),
            "consistency_embedding_dim": self.consistency_embedding_dim,
            "residual_hidden_dim": self.residual_hidden_dim,
            "goal_hypothesis_count": GOAL_HYPOTHESIS_COUNT,
        }

    def successor_parameters(self) -> list[nn.Parameter]:
        modules = (
            self.consistency_projection,
            self.hidden_target_consistency_score,
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
        return sum(
            parameter.numel()
            for parameter in self.successor_parameters()
        )

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
        if (
            consistency_posterior.ndim != 2
            or consistency_posterior.shape[-1] != GOAL_HYPOTHESIS_COUNT
        ):
            raise ValueError(
                "consistency_posterior must be [batch, 125]"
            )
        if consistency_posterior.shape[0] != global_features.shape[0]:
            raise ValueError("consistency_posterior batch mismatch")
        if bool((consistency_posterior < 0.0).any()):
            raise ValueError(
                "consistency_posterior must be non-negative"
            )
        mass = consistency_posterior.sum(dim=-1, keepdim=True)
        if not bool((mass > 0.0).all()):
            raise ValueError(
                "each consistency posterior row needs positive mass"
            )
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
            parent_logits = parent_output["action_logits"].detach()
            next_parent_hidden = parent_output[
                "next_parent_hidden"
            ].detach()
            r2_trace_hidden = parent_output[
                "r2_trace_hidden"
            ].detach()
            r3_attribution_hidden = parent_output[
                "r3_attribution_hidden"
            ].detach()
            r4_belief_hidden = parent_output[
                "belief_hidden"
            ].detach()
            r4_goal_embedding = parent_output[
                "goal_embedding"
            ].detach()
            action_tokens = (
                self.parent.parent.parent.parent.action_encoder(
                    action_features
                ).detach()
            )

        consistency_embedding = self.consistency_projection(posterior)
        consistency_marginals = (
            posterior @ self.goal_onehot.to(posterior.dtype)
        )
        safe_posterior = posterior.clamp_min(1.0e-12)
        entropy = -(
            safe_posterior * safe_posterior.log()
        ).sum(dim=-1, keepdim=True)
        entropy = entropy / torch.log(
            torch.tensor(
                float(GOAL_HYPOTHESIS_COUNT),
                dtype=posterior.dtype,
                device=posterior.device,
            )
        )
        support_fraction = (
            (posterior > 0.0)
            .to(posterior.dtype)
            .mean(dim=-1, keepdim=True)
        )

        batch, actions, _ = action_tokens.shape
        contexts = (
            next_parent_hidden,
            r2_trace_hidden,
            r3_attribution_hidden,
            r4_belief_hidden,
            r4_goal_embedding,
            consistency_embedding,
            consistency_marginals,
            entropy,
            support_fraction,
        )
        expanded = [
            value[:, None, :].expand(
                batch,
                actions,
                value.shape[-1],
            )
            for value in contexts
        ]
        residual_input = torch.cat(
            (action_tokens, *expanded),
            dim=-1,
        )
        residual = self.hidden_target_consistency_score(
            residual_input
        ).squeeze(-1)
        target_visible = global_features[
            :,
            TARGET_VISIBLE_FEATURE_INDEX :
            TARGET_VISIBLE_FEATURE_INDEX + 1,
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
            "consistency_residual_logits": residual,
            "consistency_posterior": posterior,
            "consistency_marginals": consistency_marginals.view(
                batch,
                GOAL_DIMENSIONS,
                GOAL_CARDINALITY,
            ),
            "consistency_entropy": entropy.squeeze(-1),
            "consistency_support_fraction":
                support_fraction.squeeze(-1),
            "consistency_embedding": consistency_embedding,
            "next_parent_hidden": next_parent_hidden,
            "r2_trace_hidden": r2_trace_hidden,
            "r3_attribution_hidden": r3_attribution_hidden,
            "r4_belief_hidden": r4_belief_hidden,
            "r4_goal_embedding": r4_goal_embedding,
        }


def r5_state_dict_sha256(
    model: NativeR5PublicConsistencyPolicy,
) -> str:
    return state_dict_sha256(model.state_dict())
