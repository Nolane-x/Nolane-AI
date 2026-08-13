from __future__ import annotations

import torch
from torch import Tensor, nn


class FrontierRolloutHead(nn.Module):
    """Small recurrent residual world-model for ordered multi-step programs.

    The head is intentionally independent from the R1.8 parent state dict. It
    consumes only public representations emitted by the parent and predicts a
    residual correction to the additive composition of parent one-step effects.
    """

    def __init__(
        self,
        *,
        state_dim: int = 128,
        context_dim: int = 64,
        action_dim: int = 640,
        effect_dim: int = 128,
        hidden_dim: int = 256,
        relation_dim: int = 512,
        max_horizon: int = 4,
        refine_steps: int = 3,
    ) -> None:
        super().__init__()
        if min(state_dim, context_dim, action_dim, effect_dim, hidden_dim, relation_dim, max_horizon, refine_steps) < 1:
            raise ValueError("all dimensions and refine_steps must be positive")
        self.state_dim = int(state_dim)
        self.context_dim = int(context_dim)
        self.action_dim = int(action_dim)
        self.effect_dim = int(effect_dim)
        self.hidden_dim = int(hidden_dim)
        self.max_horizon = int(max_horizon)
        self.refine_steps = int(refine_steps)

        self.state_projection = nn.Linear(state_dim, hidden_dim, bias=False)
        self.context_projection = nn.Linear(context_dim, hidden_dim, bias=False)
        self.action_projection = nn.Linear(action_dim, hidden_dim, bias=False)
        self.effect_projection = nn.Linear(effect_dim, hidden_dim, bias=False)
        self.step_embedding = nn.Parameter(torch.empty(max_horizon, hidden_dim))
        nn.init.normal_(self.step_embedding, mean=0.0, std=0.02)

        self.relation_encoder = nn.Sequential(
            nn.Linear(hidden_dim * 6, relation_dim),
            nn.GELU(),
            nn.LayerNorm(relation_dim),
            nn.Linear(relation_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
        )
        self.refiner = nn.GRUCell(hidden_dim, hidden_dim)
        self.residual_head = nn.Linear(hidden_dim, effect_dim)
        self.value_head = nn.Linear(hidden_dim, 1)
        self.uncertainty_head = nn.Linear(hidden_dim, 1)

        # Behavior preserving at initialization: candidate == additive R1.8 baseline.
        nn.init.zeros_(self.residual_head.weight)
        nn.init.zeros_(self.residual_head.bias)

    def forward(
        self,
        state: Tensor,
        context: Tensor,
        program_actions: Tensor,
        parent_effects: Tensor,
    ) -> dict[str, Tensor]:
        if state.ndim != 2 or state.shape[-1] != self.state_dim:
            raise ValueError("state must have shape [batch, state_dim]")
        if context.ndim != 2 or context.shape[0] != state.shape[0] or context.shape[-1] != self.context_dim:
            raise ValueError("context must have shape [batch, context_dim]")
        if program_actions.ndim != 3 or program_actions.shape[0] != state.shape[0] or program_actions.shape[-1] != self.action_dim:
            raise ValueError("program_actions must have shape [batch, horizon, action_dim]")
        if parent_effects.ndim != 3 or parent_effects.shape[:2] != program_actions.shape[:2] or parent_effects.shape[-1] != self.effect_dim:
            raise ValueError("parent_effects must have shape [batch, horizon, effect_dim]")
        horizon = int(program_actions.shape[1])
        if horizon < 1 or horizon > self.max_horizon:
            raise ValueError("program horizon outside configured range")

        state_h = torch.tanh(self.state_projection(state))
        context_h = torch.tanh(self.context_projection(context))
        action_h = torch.tanh(self.action_projection(program_actions))
        effect_h = torch.tanh(self.effect_projection(parent_effects))
        hidden = torch.tanh(state_h + context_h)
        proposals: list[Tensor] = []

        for step in range(horizon):
            action_step = action_h[:, step] + self.step_embedding[step]
            effect_step = effect_h[:, step]
            relation = torch.cat(
                (
                    state_h,
                    context_h,
                    action_step,
                    effect_step,
                    state_h * action_step,
                    action_step * effect_step,
                ),
                dim=-1,
            )
            proposal = self.relation_encoder(relation)
            proposals.append(proposal)
            hidden = self.refiner(proposal, hidden)

        summary = torch.stack(proposals, dim=1).mean(dim=1)
        for _ in range(self.refine_steps):
            hidden = self.refiner(summary, hidden)

        residual = self.residual_head(hidden)
        baseline = parent_effects.sum(dim=1)
        return {
            "residual_effect": residual,
            "predicted_effect": baseline + residual,
            "value": self.value_head(hidden).squeeze(-1),
            "uncertainty": torch.sigmoid(self.uncertainty_head(hidden)).squeeze(-1),
        }


def frontier_parameter_count(head: FrontierRolloutHead) -> int:
    return sum(parameter.numel() for parameter in head.parameters())
