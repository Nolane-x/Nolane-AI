from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import Tensor, nn
import torch.nn.functional as F

R20I_EFFECTIVE_PARAMETERS = 78_779_253
R21_PARAMETER_CEILING = 81_000_000
MAX_R21_DELTA_PARAMETERS = R21_PARAMETER_CEILING - R20I_EFFECTIVE_PARAMETERS


class SwiGLU(nn.Module):
    def __init__(self, dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.gate = nn.Linear(dim, hidden_dim, bias=False)
        self.value = nn.Linear(dim, hidden_dim, bias=False)
        self.out = nn.Linear(hidden_dim, dim, bias=False)

    def forward(self, x: Tensor) -> Tensor:
        return self.out(F.silu(self.gate(x)) * self.value(x))


class SharedReasoningCell(nn.Module):
    """One weight-shared latent step used for every reasoning iteration.

    The cell is intentionally set-equivariant over actions. A single global
    latent attends to the action set, updates recurrent memory, then broadcasts
    the result back to every action through the same token path. No learned
    per-step embeddings are used, so the same parameters can run beyond the
    depths seen during training.
    """

    def __init__(self, latent_dim: int = 256, n_heads: int = 4, ff_mult: int = 2) -> None:
        super().__init__()
        if latent_dim % n_heads:
            raise ValueError("latent_dim must be divisible by n_heads")
        if min(latent_dim, n_heads, ff_mult) < 1:
            raise ValueError("reasoning dimensions must be positive")
        self.latent_dim = int(latent_dim)
        self.n_heads = int(n_heads)
        self.head_dim = self.latent_dim // self.n_heads

        self.query = nn.Linear(latent_dim, latent_dim, bias=False)
        self.key = nn.Linear(latent_dim, latent_dim, bias=False)
        self.value = nn.Linear(latent_dim, latent_dim, bias=False)
        self.attention_out = nn.Linear(latent_dim, latent_dim, bias=False)
        self.depth_projection = nn.Linear(4, latent_dim, bias=False)

        self.pre_recurrent_norm = nn.LayerNorm(latent_dim)
        self.recurrent = nn.GRUCell(latent_dim, latent_dim)
        self.global_norm = nn.LayerNorm(latent_dim)
        self.global_ff = SwiGLU(latent_dim, latent_dim * ff_mult)
        self.global_gate = nn.Parameter(torch.tensor(-1.0))

        self.state_to_action = nn.Linear(latent_dim, latent_dim, bias=False)
        self.action_norm = nn.LayerNorm(latent_dim)
        self.action_ff = SwiGLU(latent_dim, latent_dim * ff_mult)
        self.action_gate = nn.Parameter(torch.tensor(-1.0))

    @staticmethod
    def _depth_features(step: int, *, device: torch.device, dtype: torch.dtype) -> Tensor:
        # Continuous/non-parametric iteration encoding supports depths never seen
        # during training and avoids a finite learned step-embedding table.
        t = torch.tensor(float(step + 1), device=device, dtype=dtype)
        return torch.stack((
            1.0 / t,
            t / (t + 1.0),
            torch.log1p(t) / 4.0,
            torch.sin(torch.log1p(t)),
        ))

    def forward(self, latent: Tensor, action_tokens: Tensor, *, step: int) -> tuple[Tensor, Tensor]:
        batch, actions, dim = action_tokens.shape
        q = self.query(latent).view(batch, self.n_heads, self.head_dim)
        k = self.key(action_tokens).view(batch, actions, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.value(action_tokens).view(batch, actions, self.n_heads, self.head_dim).transpose(1, 2)
        score = torch.einsum("bhd,bhad->bha", q, k) / math.sqrt(float(self.head_dim))
        weights = torch.softmax(score, dim=-1)
        attended = torch.einsum("bha,bhad->bhd", weights, v).reshape(batch, dim)

        depth = self.depth_projection(
            self._depth_features(step, device=latent.device, dtype=latent.dtype)
        ).unsqueeze(0)
        recurrent_input = self.pre_recurrent_norm(latent + self.attention_out(attended) + depth)
        latent = self.recurrent(recurrent_input, latent)
        global_delta = self.global_ff(self.global_norm(latent))
        latent = self.global_norm(latent + torch.sigmoid(self.global_gate) * global_delta)

        broadcast = self.state_to_action(latent).unsqueeze(1) + depth.unsqueeze(1)
        action_hidden = self.action_norm(action_tokens + broadcast)
        action_delta = self.action_ff(action_hidden)
        action_tokens = self.action_norm(
            action_tokens + torch.sigmoid(self.action_gate) * action_delta + 0.1 * broadcast
        )
        return latent, action_tokens


@dataclass(frozen=True)
class R21Architecture:
    state_dim: int = 128
    context_dim: int = 64
    action_dim: int = 640
    effect_dim: int = 128
    action_memory_dim: int = 7
    latent_dim: int = 256
    n_heads: int = 4
    ff_mult: int = 2


class RecursiveLatentIntelligenceCore(nn.Module):
    """Small recursive neural core that converts inference compute into depth.

    This module is a residual neural successor to the R2.0i policy. It consumes
    public neural representations already emitted by R2.0i and refines them
    through one shared reasoning cell. The action/effect residual heads are
    exactly zero-initialized, making an untrained R2.1 core behavior preserving
    with respect to upstream action logits and effect estimates.
    """

    def __init__(
        self,
        *,
        state_dim: int = 128,
        context_dim: int = 64,
        action_dim: int = 640,
        effect_dim: int = 128,
        action_memory_dim: int = 7,
        latent_dim: int = 256,
        n_heads: int = 4,
        ff_mult: int = 2,
    ) -> None:
        super().__init__()
        if min(state_dim, context_dim, action_dim, effect_dim, action_memory_dim, latent_dim, n_heads, ff_mult) < 1:
            raise ValueError("all architecture dimensions must be positive")
        self.state_dim = int(state_dim)
        self.context_dim = int(context_dim)
        self.action_dim = int(action_dim)
        self.effect_dim = int(effect_dim)
        self.action_memory_dim = int(action_memory_dim)
        self.latent_dim = int(latent_dim)
        self.n_heads = int(n_heads)
        self.ff_mult = int(ff_mult)

        # Action-set anchor. Every projection is shared across actions.
        self.action_projection = nn.Linear(action_dim, latent_dim, bias=False)
        self.parent_effect_projection = nn.Linear(effect_dim, latent_dim, bias=False)
        self.imagined_effect_projection = nn.Linear(effect_dim, latent_dim, bias=False)
        self.evidence_effect_projection = nn.Linear(effect_dim, latent_dim, bias=False)
        self.action_memory_projection = nn.Linear(action_memory_dim, latent_dim, bias=False)
        self.action_scalar_projection = nn.Linear(2, latent_dim, bias=False)
        self.action_anchor_norm = nn.LayerNorm(latent_dim)

        # Global neural state anchor.
        self.state_projection = nn.Linear(state_dim, latent_dim, bias=False)
        self.context_projection = nn.Linear(context_dim, latent_dim, bias=False)
        self.global_scalar_projection = nn.Linear(7, latent_dim, bias=False)
        self.initial_norm = nn.LayerNorm(latent_dim)

        # Critically: one cell, reused N times. Parameter count is independent of
        # requested runtime reasoning depth.
        self.reasoning_cell = SharedReasoningCell(latent_dim, n_heads, ff_mult)

        self.action_residual_head = nn.Linear(latent_dim, 1)
        self.effect_residual_head = nn.Linear(latent_dim, effect_dim)
        self.progress_head = nn.Linear(latent_dim, 1)
        self.uncertainty_head = nn.Linear(latent_dim, 1)
        self.stop_head = nn.Linear(latent_dim, 1)
        self.success_head = nn.Linear(latent_dim, 1)
        self.ponder_head = nn.Linear(latent_dim, 1)

        # Start as an exact residual no-op over the currently accepted R2.0i
        # action/effect behavior. Training must earn every policy change.
        nn.init.zeros_(self.action_residual_head.weight)
        nn.init.zeros_(self.action_residual_head.bias)
        nn.init.zeros_(self.effect_residual_head.weight)
        nn.init.zeros_(self.effect_residual_head.bias)
        nn.init.zeros_(self.stop_head.weight)
        nn.init.zeros_(self.stop_head.bias)
        nn.init.zeros_(self.success_head.weight)
        nn.init.zeros_(self.success_head.bias)

        params = r21_parameter_count(self)
        if params > MAX_R21_DELTA_PARAMETERS:
            raise RuntimeError(
                f"R2.1 neural delta violates parameter ceiling: {params:,} > {MAX_R21_DELTA_PARAMETERS:,}"
            )

    def architecture(self) -> dict[str, int]:
        return {
            "state_dim": self.state_dim,
            "context_dim": self.context_dim,
            "action_dim": self.action_dim,
            "effect_dim": self.effect_dim,
            "action_memory_dim": self.action_memory_dim,
            "latent_dim": self.latent_dim,
            "n_heads": self.n_heads,
            "ff_mult": self.ff_mult,
        }

    def _validate(
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
        base_stop_logit: Tensor,
        base_success_probability: Tensor,
        reasoning_steps: int,
    ) -> tuple[int, int]:
        if not isinstance(reasoning_steps, int) or isinstance(reasoning_steps, bool) or reasoning_steps < 1:
            raise ValueError("reasoning_steps must be a positive integer")
        if state.ndim != 2 or state.shape[-1] != self.state_dim:
            raise ValueError("state must be [batch, state_dim]")
        batch = state.shape[0]
        if context.shape != (batch, self.context_dim):
            raise ValueError("context must be [batch, context_dim]")
        if action_embeddings.ndim != 3 or action_embeddings.shape[0] != batch or action_embeddings.shape[-1] != self.action_dim:
            raise ValueError("action_embeddings must be [batch, actions, action_dim]")
        actions = action_embeddings.shape[1]
        if actions < 1:
            raise ValueError("at least one legal action is required")
        effect_shape = (batch, actions, self.effect_dim)
        for name, tensor in (
            ("parent_effects", parent_effects),
            ("imagined_effects", imagined_effects),
            ("evidence_effects", evidence_effects),
        ):
            if tensor.shape != effect_shape:
                raise ValueError(f"{name} must be [batch, actions, effect_dim]")
        if action_memory.shape != (batch, actions, self.action_memory_dim):
            raise ValueError("action_memory must be [batch, actions, action_memory_dim]")
        if imagined_uncertainty.shape != (batch, actions) or imagined_value.shape != (batch, actions):
            raise ValueError("imagined scalars must be [batch, actions]")
        if base_action_logits.shape != (batch, actions):
            raise ValueError("base_action_logits must be [batch, actions]")
        if progress.shape != (batch, 1) or budget_fraction.shape != (batch, 1) or previous_feedback.shape != (batch, 3):
            raise ValueError("global scalar input shape mismatch")
        if base_stop_logit.shape != (batch,) or base_success_probability.shape != (batch,):
            raise ValueError("base global policy outputs must be [batch]")
        if torch.any((base_success_probability < 0) | (base_success_probability > 1)):
            raise ValueError("base_success_probability must lie in [0, 1]")
        return batch, actions

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
        base_stop_logit: Tensor,
        base_success_probability: Tensor,
        reasoning_steps: int = 4,
    ) -> dict[str, Tensor]:
        batch, actions = self._validate(
            state=state,
            context=context,
            action_embeddings=action_embeddings,
            parent_effects=parent_effects,
            imagined_effects=imagined_effects,
            evidence_effects=evidence_effects,
            action_memory=action_memory,
            imagined_uncertainty=imagined_uncertainty,
            imagined_value=imagined_value,
            base_action_logits=base_action_logits,
            progress=progress,
            budget_fraction=budget_fraction,
            previous_feedback=previous_feedback,
            base_stop_logit=base_stop_logit,
            base_success_probability=base_success_probability,
            reasoning_steps=reasoning_steps,
        )

        action_scalars = torch.stack((imagined_uncertainty, imagined_value), dim=-1)
        action_tokens = self.action_anchor_norm(
            self.action_projection(action_embeddings)
            + self.parent_effect_projection(parent_effects)
            + self.imagined_effect_projection(imagined_effects)
            + self.evidence_effect_projection(evidence_effects)
            + self.action_memory_projection(action_memory)
            + self.action_scalar_projection(action_scalars)
        )
        clipped_success = base_success_probability.clamp(1e-6, 1 - 1e-6)
        base_success_logit = torch.logit(clipped_success)
        global_scalars = torch.cat((
            progress, budget_fraction, previous_feedback, base_stop_logit.unsqueeze(-1), clipped_success.unsqueeze(-1)
        ), dim=-1)
        latent = self.initial_norm(
            self.state_projection(state)
            + self.context_projection(context)
            + self.global_scalar_projection(global_scalars)
            + action_tokens.mean(dim=1)
        )

        latent_trajectory: list[Tensor] = []
        logit_trajectory: list[Tensor] = []
        progress_trajectory: list[Tensor] = []
        uncertainty_trajectory: list[Tensor] = []
        stop_trajectory: list[Tensor] = []
        success_trajectory: list[Tensor] = []
        ponder_trajectory: list[Tensor] = []
        for step in range(reasoning_steps):
            latent, action_tokens = self.reasoning_cell(latent, action_tokens, step=step)
            residual = self.action_residual_head(action_tokens).squeeze(-1)
            latent_trajectory.append(latent)
            logit_trajectory.append(base_action_logits + residual)
            progress_trajectory.append(torch.sigmoid(self.progress_head(latent)).squeeze(-1))
            uncertainty_trajectory.append(torch.sigmoid(self.uncertainty_head(latent)).squeeze(-1))
            stop_trajectory.append(base_stop_logit + self.stop_head(latent).squeeze(-1))
            success_trajectory.append(torch.sigmoid(base_success_logit + self.success_head(latent).squeeze(-1)))
            ponder_trajectory.append(self.ponder_head(latent).squeeze(-1))

        action_residual = self.action_residual_head(action_tokens).squeeze(-1)
        effect_residuals = self.effect_residual_head(action_tokens)
        return {
            "action_logits": base_action_logits + action_residual,
            "action_logit_residual": action_residual,
            "effect_residuals": effect_residuals,
            "latent_state": latent,
            "latent_trajectory": torch.stack(latent_trajectory, dim=1),
            "action_logits_trajectory": torch.stack(logit_trajectory, dim=1),
            "progress_trajectory": torch.stack(progress_trajectory, dim=1),
            "uncertainty_trajectory": torch.stack(uncertainty_trajectory, dim=1),
            "stop_logits_trajectory": torch.stack(stop_trajectory, dim=1),
            "success_trajectory": torch.stack(success_trajectory, dim=1),
            "ponder_logits_trajectory": torch.stack(ponder_trajectory, dim=1),
            "progress_prediction": torch.sigmoid(self.progress_head(latent)).squeeze(-1),
            "uncertainty": torch.sigmoid(self.uncertainty_head(latent)).squeeze(-1),
            "stop_logit": base_stop_logit + self.stop_head(latent).squeeze(-1),
            "success_probability": torch.sigmoid(base_success_logit + self.success_head(latent).squeeze(-1)),
            "ponder_logit": self.ponder_head(latent).squeeze(-1),
        }


def r21_parameter_count(module: nn.Module) -> int:
    return sum(parameter.numel() for parameter in module.parameters())
