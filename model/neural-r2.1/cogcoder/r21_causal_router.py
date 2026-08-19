from __future__ import annotations

import torch
from torch import Tensor, nn


class CausalEvidenceRouter(nn.Module):
    """Tiny set-equivariant neural router over public R2.0i evidence tensors.

    The module is residual over the accepted neural policy. Its score head is
    zero-initialized, so a new untrained router is an exact policy no-op. The
    role head is auxiliary training supervision only; deployment receives no
    hidden role labels or private environment state.
    """

    def __init__(self, hidden_dim: int = 48) -> None:
        super().__init__()
        if hidden_dim < 1:
            raise ValueError("hidden_dim must be positive")
        self.hidden_dim = int(hidden_dim)
        h = self.hidden_dim
        self.action = nn.Linear(640, h, bias=False)
        self.evidence = nn.Linear(128, h, bias=False)
        self.parent = nn.Linear(128, h, bias=False)
        self.imagined = nn.Linear(128, h, bias=False)
        self.memory = nn.Linear(7, h, bias=False)
        self.state = nn.Linear(128, h, bias=False)
        self.context = nn.Linear(64, h, bias=False)
        self.scalars = nn.Linear(8, h, bias=False)
        self.relation = nn.Sequential(
            nn.Linear(h * 10, h * 2), nn.GELU(), nn.LayerNorm(h * 2),
            nn.Linear(h * 2, h), nn.GELU(), nn.LayerNorm(h),
        )
        self.score = nn.Linear(h, 1)
        self.role = nn.Linear(h, 5)
        self.gate = nn.Sequential(
            nn.Linear(h * 4 + 5, h), nn.GELU(), nn.LayerNorm(h), nn.Linear(h, 1),
        )
        nn.init.constant_(self.gate[-1].bias, -3.0)
        nn.init.zeros_(self.score.weight)
        nn.init.zeros_(self.score.bias)

    def architecture(self) -> dict[str, int]:
        return {"hidden_dim": self.hidden_dim}

    def forward(
        self,
        *,
        state: Tensor,
        context: Tensor,
        action_embeddings: Tensor,
        parent_effects: Tensor,
        imagined_effects: Tensor,
        evidence_effects: Tensor,
        action_memory: Tensor,
        imagined_uncertainty: Tensor,
        imagined_value: Tensor,
        base_action_logits: Tensor,
        progress: Tensor,
        budget_fraction: Tensor,
        previous_feedback: Tensor,
    ) -> dict[str, Tensor]:
        if state.ndim != 2 or state.shape[-1] != 128:
            raise ValueError("state must be [batch, 128]")
        batch = state.shape[0]
        if context.shape != (batch, 64):
            raise ValueError("context must be [batch, 64]")
        if action_embeddings.ndim != 3 or action_embeddings.shape[0] != batch or action_embeddings.shape[-1] != 640:
            raise ValueError("action_embeddings must be [batch, actions, 640]")
        actions = action_embeddings.shape[1]
        if actions < 1:
            raise ValueError("at least one action is required")
        effect_shape = (batch, actions, 128)
        for name, value in (("parent_effects", parent_effects), ("imagined_effects", imagined_effects), ("evidence_effects", evidence_effects)):
            if value.shape != effect_shape:
                raise ValueError(f"{name} must be [batch, actions, 128]")
        if action_memory.shape != (batch, actions, 7):
            raise ValueError("action_memory must be [batch, actions, 7]")
        if imagined_uncertainty.shape != (batch, actions) or imagined_value.shape != (batch, actions):
            raise ValueError("imagined scalars must be [batch, actions]")
        if base_action_logits.shape != (batch, actions):
            raise ValueError("base_action_logits must be [batch, actions]")
        if progress.shape != (batch, 1) or budget_fraction.shape != (batch, 1) or previous_feedback.shape != (batch, 3):
            raise ValueError("global public scalar shape mismatch")

        centered = base_action_logits - base_action_logits.mean(dim=-1, keepdim=True)
        # Preserve the exact admitted training/evaluation normalization for
        # multi-action states. Only the degenerate one-action case is special-
        # cased to avoid PyTorch's unbiased-variance NaN.
        if actions == 1:
            scale = torch.ones_like(centered)
        else:
            scale = base_action_logits.std(dim=-1, keepdim=True).clamp_min(1e-3)
        standardized = centered / scale
        scalar = torch.cat((
            imagined_uncertainty.unsqueeze(-1), imagined_value.unsqueeze(-1), standardized.unsqueeze(-1),
            progress.unsqueeze(1).expand(-1, actions, -1), budget_fraction.unsqueeze(1).expand(-1, actions, -1),
            previous_feedback.unsqueeze(1).expand(-1, actions, -1),
        ), dim=-1)
        action_h = torch.tanh(self.action(action_embeddings))
        evidence_h = torch.tanh(self.evidence(evidence_effects))
        parent_h = torch.tanh(self.parent(parent_effects))
        imagined_h = torch.tanh(self.imagined(imagined_effects))
        memory_h = torch.tanh(self.memory(action_memory))
        state_h = torch.tanh(self.state(state)).unsqueeze(1).expand(-1, actions, -1)
        context_h = torch.tanh(self.context(context)).unsqueeze(1).expand(-1, actions, -1)
        scalar_h = torch.tanh(self.scalars(scalar))
        hidden = self.relation(torch.cat((
            action_h, evidence_h, parent_h, imagined_h, memory_h, state_h, context_h, scalar_h,
            state_h * evidence_h, torch.abs(state_h - evidence_h),
        ), dim=-1))
        raw_residual = self.score(hidden).squeeze(-1)
        role_logits = self.role(hidden)
        gate_features = torch.cat((
            hidden.mean(dim=1), hidden.max(dim=1).values, evidence_h.mean(dim=1), memory_h.mean(dim=1),
            progress, budget_fraction, previous_feedback,
        ), dim=-1)
        activation = torch.sigmoid(self.gate(gate_features)).squeeze(-1)
        residual = activation.unsqueeze(-1) * raw_residual
        return {
            "action_logits": base_action_logits + residual,
            "action_logit_residual": residual,
            "router_activation": activation,
            "role_logits": role_logits,
        }


def r21a_parameter_count(module: nn.Module) -> int:
    return sum(parameter.numel() for parameter in module.parameters())
