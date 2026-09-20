from __future__ import annotations

from typing import Any

import torch
from torch import Tensor, nn

from native_core import TARGET_VISIBLE_FEATURE_INDEX, parameter_count, state_dict_sha256
from latent_goal_core import NativeR4LatentGoalBeliefPolicy
from public_planner import GOAL_CARDINALITY, GOAL_DIMENSIONS, GOAL_HYPOTHESIS_COUNT, GOAL_TABLE

CAUSAL_FEATURE_DIM = 10


class NativeR12NeuralCausalResidualPolicy(nn.Module):
    """Frozen accepted R4 substrate plus an R11-anchored learned causal residual."""

    def __init__(
        self,
        parent: NativeR4LatentGoalBeliefPolicy,
        *,
        posterior_embedding_dim: int = 32,
        residual_hidden_dim: int = 128,
        max_support: int = 3,
        parent_margin: float = 1.0,
    ) -> None:
        super().__init__()
        if posterior_embedding_dim < 1:
            raise ValueError("posterior_embedding_dim must be positive")
        if residual_hidden_dim < 1:
            raise ValueError("residual_hidden_dim must be positive")
        if int(max_support) < 1 or int(max_support) > GOAL_HYPOTHESIS_COUNT:
            raise ValueError("max_support must lie in [1,125]")
        if float(parent_margin) <= 0.0:
            raise ValueError("parent_margin must be positive")
        self.parent = parent
        self.posterior_embedding_dim = int(posterior_embedding_dim)
        self.residual_hidden_dim = int(residual_hidden_dim)
        self.max_support = int(max_support)
        self.parent_margin = float(parent_margin)
        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)
        self.parent.eval()

        native_hidden = int(parent.parent.parent.parent.hidden_dim)
        r4_goal_embedding = int(parent.goal_embedding_dim)

        self.posterior_projection = nn.Sequential(
            nn.Linear(GOAL_HYPOTHESIS_COUNT, self.posterior_embedding_dim),
            nn.GELU(),
            nn.LayerNorm(self.posterior_embedding_dim),
        )
        goal_onehot = torch.zeros(
            GOAL_HYPOTHESIS_COUNT,
            GOAL_DIMENSIONS * GOAL_CARDINALITY,
        )
        for row, goal in enumerate(GOAL_TABLE.tolist()):
            for dimension, value in enumerate(goal):
                goal_onehot[row, dimension * GOAL_CARDINALITY + value] = 1.0
        self.register_buffer("goal_onehot", goal_onehot, persistent=True)

        residual_input = (
            native_hidden
            + native_hidden
            + r4_goal_embedding
            + self.posterior_embedding_dim
            + GOAL_DIMENSIONS * GOAL_CARDINALITY
            + CAUSAL_FEATURE_DIM
            + 1
        )
        self.residual_score = nn.Sequential(
            nn.Linear(residual_input, self.residual_hidden_dim),
            nn.GELU(),
            nn.LayerNorm(self.residual_hidden_dim),
            nn.Linear(self.residual_hidden_dim, 1),
        )
        nn.init.zeros_(self.residual_score[-1].weight)
        nn.init.zeros_(self.residual_score[-1].bias)

    def train(self, mode: bool = True) -> "NativeR12NeuralCausalResidualPolicy":
        super().train(mode)
        self.parent.eval()
        return self

    def architecture(self) -> dict[str, Any]:
        return {
            **self.parent.architecture(),
            "r12_posterior_embedding_dim": self.posterior_embedding_dim,
            "r12_residual_hidden_dim": self.residual_hidden_dim,
            "r12_max_support": self.max_support,
            "r12_parent_margin": self.parent_margin,
            "r12_causal_feature_dim": CAUSAL_FEATURE_DIM,
            "r12_goal_hypothesis_count": GOAL_HYPOTHESIS_COUNT,
        }

    def successor_parameters(self) -> list[nn.Parameter]:
        modules = (self.posterior_projection, self.residual_score)
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

    def successor_state_dict(self) -> dict[str, Tensor]:
        return {
            name: tensor.detach().cpu().clone()
            for name, tensor in self.state_dict().items()
            if not name.startswith("parent.")
        }

    def successor_state_sha256(self) -> str:
        return state_dict_sha256(self.successor_state_dict())

    def load_successor_state_dict(self, state: dict[str, Tensor]) -> None:
        expected = {
            name for name in self.state_dict()
            if not name.startswith("parent.")
        }
        if set(state) != expected:
            raise ValueError("R12 successor state keys mismatch")
        merged = self.state_dict()
        for name, tensor in state.items():
            merged[name] = tensor
        self.load_state_dict(merged, strict=True)

    def forward_from_parent(
        self,
        *,
        global_features: Tensor,
        action_features: Tensor,
        valid_actions: Tensor,
        parent_output: dict[str, Tensor],
        consistency_posterior: Tensor,
        causal_action_features: Tensor,
        r11_actions: Tensor,
    ) -> dict[str, Tensor]:
        if consistency_posterior.ndim != 2 or consistency_posterior.shape[-1] != GOAL_HYPOTHESIS_COUNT:
            raise ValueError("consistency_posterior must be [batch,125]")
        if causal_action_features.ndim != 3 or causal_action_features.shape[-1] != CAUSAL_FEATURE_DIM:
            raise ValueError("causal_action_features must be [batch,actions,10]")
        batch, actions, _ = causal_action_features.shape
        if action_features.shape[:2] != (batch, actions):
            raise ValueError("R12 action/causal shape mismatch")
        if valid_actions.shape != (batch, actions) or valid_actions.dtype != torch.bool:
            raise ValueError("valid_actions must be bool [batch,actions]")
        if r11_actions.shape != (batch,):
            raise ValueError("r11_actions must be [batch]")
        if bool((r11_actions < 0).any()) or bool((r11_actions >= actions).any()):
            raise ValueError("r11 action index out of range")
        if bool((consistency_posterior < 0.0).any()):
            raise ValueError("posterior must be non-negative")
        mass = consistency_posterior.sum(dim=-1, keepdim=True)
        if not bool((mass > 0.0).all()):
            raise ValueError("posterior rows need positive mass")
        posterior = consistency_posterior / mass

        parent_logits = parent_output["action_logits"].detach()
        next_parent_hidden = parent_output["next_parent_hidden"].detach()
        r4_goal_embedding = parent_output["goal_embedding"].detach()
        with torch.no_grad():
            action_tokens = self.parent.parent.parent.parent.action_encoder(
                action_features
            ).detach()

        posterior_embedding = self.posterior_projection(posterior)
        marginals = posterior @ self.goal_onehot.to(posterior.dtype)
        support_count = (posterior > 0.0).sum(dim=-1, keepdim=True)

        native_expanded = next_parent_hidden[:, None, :].expand(
            batch, actions, next_parent_hidden.shape[-1]
        )
        goal_expanded = r4_goal_embedding[:, None, :].expand(
            batch, actions, r4_goal_embedding.shape[-1]
        )
        posterior_expanded = posterior_embedding[:, None, :].expand(
            batch, actions, posterior_embedding.shape[-1]
        )
        marginals_expanded = marginals[:, None, :].expand(
            batch, actions, marginals.shape[-1]
        )
        parent_action_flag = torch.zeros(
            batch, actions, 1,
            dtype=action_features.dtype,
            device=action_features.device,
        )
        parent_action_flag.scatter_(
            1,
            r11_actions[:, None, None],
            torch.ones(
                batch, 1, 1,
                dtype=action_features.dtype,
                device=action_features.device,
            ),
        )

        residual_input = torch.cat(
            (
                action_tokens,
                native_expanded,
                goal_expanded,
                posterior_expanded,
                marginals_expanded,
                causal_action_features,
                parent_action_flag,
            ),
            dim=-1,
        )
        residual = self.residual_score(residual_input).squeeze(-1)

        target_visible = global_features[
            :, TARGET_VISIBLE_FEATURE_INDEX : TARGET_VISIBLE_FEATURE_INDEX + 1
        ].clamp(0.0, 1.0)
        hidden_gate = 1.0 - target_visible
        support_gate = (support_count <= float(self.max_support)).to(residual.dtype)
        residual = residual * hidden_gate * support_gate
        residual = residual.masked_fill(~valid_actions, 0.0)

        valid_parent = parent_logits.masked_fill(
            ~valid_actions,
            torch.finfo(parent_logits.dtype).min,
        )
        row_max = valid_parent.max(dim=-1, keepdim=True).values
        anchored = valid_parent.clone()
        anchor_value = row_max + float(self.parent_margin)
        anchored.scatter_(1, r11_actions[:, None], anchor_value)
        hidden_logits = (anchored + residual).masked_fill(
            ~valid_actions,
            torch.finfo(parent_logits.dtype).min,
        )
        logits = torch.where(
            (target_visible >= 0.5),
            valid_parent,
            hidden_logits,
        )
        return {
            "action_logits": logits,
            "r11_anchored_logits": anchored,
            "parent_r4_logits": valid_parent,
            "causal_residual_logits": residual,
            "consistency_posterior": posterior,
            "consistency_marginals": marginals.view(
                batch, GOAL_DIMENSIONS, GOAL_CARDINALITY
            ),
            "support_count": support_count.squeeze(-1),
            "support_gate": support_gate.squeeze(-1),
            "next_parent_hidden": next_parent_hidden,
        }
