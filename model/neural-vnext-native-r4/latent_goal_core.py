from __future__ import annotations

import torch
from torch import Tensor, nn

from native_core import TARGET_VISIBLE_FEATURE_INDEX, parameter_count, state_dict_sha256
from attributed_core import ATTRIBUTION_TOKEN_DIM, NativeR3AttributedBeliefPolicy

GOAL_DIMENSIONS = 3
GOAL_CARDINALITY = 5
GOAL_LOGIT_DIM = GOAL_DIMENSIONS * GOAL_CARDINALITY


class NativeR4LatentGoalBeliefPolicy(nn.Module):
    """Frozen accepted R3 parent plus a learned hidden-goal posterior residual."""

    def __init__(
        self,
        parent: NativeR3AttributedBeliefPolicy,
        *,
        belief_hidden_dim: int = 96,
        goal_embedding_dim: int = 48,
    ) -> None:
        super().__init__()
        if belief_hidden_dim < 1:
            raise ValueError("belief_hidden_dim must be positive")
        if goal_embedding_dim < 1:
            raise ValueError("goal_embedding_dim must be positive")
        self.parent = parent
        self.belief_hidden_dim = int(belief_hidden_dim)
        self.goal_embedding_dim = int(goal_embedding_dim)
        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)
        self.parent.eval()

        native_hidden = int(parent.parent.parent.hidden_dim)
        r2_trace_hidden = int(parent.parent.trace_hidden_dim)
        r3_attribution_hidden = int(parent.attribution_hidden_dim)

        self.belief_encoder = nn.Sequential(
            nn.Linear(ATTRIBUTION_TOKEN_DIM, self.belief_hidden_dim),
            nn.GELU(),
            nn.LayerNorm(self.belief_hidden_dim),
        )
        self.belief_recurrent = nn.GRUCell(
            self.belief_hidden_dim,
            self.belief_hidden_dim,
        )
        self.goal_head = nn.Sequential(
            nn.Linear(
                self.belief_hidden_dim + native_hidden + r3_attribution_hidden,
                self.belief_hidden_dim,
            ),
            nn.GELU(),
            nn.LayerNorm(self.belief_hidden_dim),
            nn.Linear(self.belief_hidden_dim, GOAL_LOGIT_DIM),
        )
        self.goal_projection = nn.Sequential(
            nn.Linear(GOAL_LOGIT_DIM, self.goal_embedding_dim),
            nn.GELU(),
            nn.LayerNorm(self.goal_embedding_dim),
        )
        residual_input = (
            native_hidden
            + native_hidden
            + r2_trace_hidden
            + r3_attribution_hidden
            + self.goal_embedding_dim
        )
        self.hidden_target_goal_score = nn.Sequential(
            nn.Linear(residual_input, native_hidden),
            nn.GELU(),
            nn.LayerNorm(native_hidden),
            nn.Linear(native_hidden, 1),
        )
        nn.init.zeros_(self.hidden_target_goal_score[-1].weight)
        nn.init.zeros_(self.hidden_target_goal_score[-1].bias)

    def train(self, mode: bool = True) -> "NativeR4LatentGoalBeliefPolicy":
        super().train(mode)
        self.parent.eval()
        return self

    def architecture(self) -> dict[str, int]:
        parent_arch = self.parent.architecture()
        return {
            **parent_arch,
            "belief_hidden_dim": self.belief_hidden_dim,
            "goal_embedding_dim": self.goal_embedding_dim,
            "goal_dimensions": GOAL_DIMENSIONS,
            "goal_cardinality": GOAL_CARDINALITY,
        }

    def successor_parameters(self) -> list[nn.Parameter]:
        modules = (
            self.belief_encoder,
            self.belief_recurrent,
            self.goal_head,
            self.goal_projection,
            self.hidden_target_goal_score,
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
    ) -> dict[str, Tensor]:
        if attribution_features.ndim != 3:
            raise ValueError(
                "attribution_features must be [batch, trace, token_dim]"
            )
        if attribution_features.shape[-1] != ATTRIBUTION_TOKEN_DIM:
            raise ValueError("R4 attribution token width mismatch")
        if attribution_features.shape[1] != self.parent.attribution_length:
            raise ValueError("R4 attribution length mismatch")
        if attribution_valid.shape != attribution_features.shape[:2]:
            raise ValueError("R4 attribution_valid shape mismatch")
        if attribution_valid.dtype != torch.bool:
            raise ValueError("R4 attribution_valid must be bool")

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
            r3_attribution_hidden = parent_output["attribution_hidden"].detach()
            action_tokens = self.parent.parent.parent.action_encoder(
                action_features
            ).detach()

        batch, actions, _ = action_tokens.shape
        belief_hidden = torch.zeros(
            batch,
            self.belief_hidden_dim,
            dtype=attribution_features.dtype,
            device=attribution_features.device,
        )
        encoded = self.belief_encoder(attribution_features)
        for index in range(self.parent.attribution_length):
            candidate = self.belief_recurrent(
                encoded[:, index, :],
                belief_hidden,
            )
            mask = attribution_valid[:, index].unsqueeze(-1)
            belief_hidden = torch.where(mask, candidate, belief_hidden)

        goal_context = torch.cat(
            (belief_hidden, next_parent_hidden, r3_attribution_hidden),
            dim=-1,
        )
        goal_logits_flat = self.goal_head(goal_context)
        goal_logits = goal_logits_flat.view(
            batch,
            GOAL_DIMENSIONS,
            GOAL_CARDINALITY,
        )
        goal_probabilities = torch.softmax(goal_logits, dim=-1)
        goal_embedding = self.goal_projection(goal_probabilities.flatten(1))

        native_expanded = next_parent_hidden[:, None, :].expand(
            batch, actions, next_parent_hidden.shape[-1]
        )
        r2_expanded = r2_trace_hidden[:, None, :].expand(
            batch, actions, r2_trace_hidden.shape[-1]
        )
        r3_expanded = r3_attribution_hidden[:, None, :].expand(
            batch, actions, r3_attribution_hidden.shape[-1]
        )
        goal_expanded = goal_embedding[:, None, :].expand(
            batch, actions, goal_embedding.shape[-1]
        )
        residual_input = torch.cat(
            (
                action_tokens,
                native_expanded,
                r2_expanded,
                r3_expanded,
                goal_expanded,
            ),
            dim=-1,
        )
        residual = self.hidden_target_goal_score(residual_input).squeeze(-1)
        target_visible = global_features[
            :, TARGET_VISIBLE_FEATURE_INDEX : TARGET_VISIBLE_FEATURE_INDEX + 1
        ].clamp(0.0, 1.0)
        hidden_target_gate = 1.0 - target_visible
        residual = residual * hidden_target_gate
        residual = residual.masked_fill(~valid_actions, 0.0)
        logits = (parent_logits + residual).masked_fill(
            ~valid_actions,
            torch.finfo(parent_logits.dtype).min,
        )
        return {
            "action_logits": logits,
            "parent_action_logits": parent_logits,
            "goal_residual_logits": residual,
            "goal_logits": goal_logits,
            "goal_probabilities": goal_probabilities,
            "goal_embedding": goal_embedding,
            "belief_hidden": belief_hidden,
            "next_parent_hidden": next_parent_hidden,
            "r2_trace_hidden": r2_trace_hidden,
            "r3_attribution_hidden": r3_attribution_hidden,
        }


def r4_state_dict_sha256(model: NativeR4LatentGoalBeliefPolicy) -> str:
    return state_dict_sha256(model.state_dict())
