from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Mapping

import torch
from torch import Tensor, nn

HERE = Path(__file__).resolve()
PARENT_ROOT = HERE.parent.parent / "neural-vnext-native"
if str(PARENT_ROOT) not in sys.path:
    sys.path.insert(0, str(PARENT_ROOT))

from native_core import (  # noqa: E402
    ACTION_FEATURE_DIM,
    GLOBAL_FEATURE_DIM,
    NativeRecurrentPolicy,
    parameter_count as parent_parameter_count,
)


@dataclass
class SuccessorState:
    parent_hidden: Tensor
    fast_hidden: Tensor
    slow_hidden: Tensor

    def detach(self) -> "SuccessorState":
        return SuccessorState(
            parent_hidden=self.parent_hidden.detach(),
            fast_hidden=self.fast_hidden.detach(),
            slow_hidden=self.slow_hidden.detach(),
        )


class DualTimescaleResidualPolicy(nn.Module):
    """Frozen accepted parent plus a learned public dual-timescale residual.

    The parent is never updated. S1 receives only the same public tensors already
    accepted by the parent and maintains two additional recurrent timescales.
    Action scoring remains shared across action slots, preserving permutation
    equivariance.
    """

    def __init__(
        self,
        parent: NativeRecurrentPolicy,
        *,
        specialist_dim: int = 96,
    ) -> None:
        super().__init__()
        if specialist_dim < 16:
            raise ValueError("specialist_dim must be at least 16")
        self.parent = parent
        self.specialist_dim = int(specialist_dim)
        self.global_dim = int(parent.global_dim)
        self.action_dim = int(parent.action_dim)
        self.parent_hidden_dim = int(parent.hidden_dim)

        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)

        self.fast_input = nn.Sequential(
            nn.Linear(self.parent_hidden_dim + self.global_dim, self.specialist_dim),
            nn.GELU(),
            nn.LayerNorm(self.specialist_dim),
        )
        self.fast_gru = nn.GRUCell(self.specialist_dim, self.specialist_dim)

        self.slow_gru = nn.GRUCell(self.specialist_dim, self.specialist_dim)
        self.slow_update_gate = nn.Sequential(
            nn.Linear(self.specialist_dim + self.global_dim, self.specialist_dim // 2),
            nn.GELU(),
            nn.Linear(self.specialist_dim // 2, 1),
        )

        self.context_projection = nn.Sequential(
            nn.Linear(
                self.parent_hidden_dim + 2 * self.specialist_dim,
                self.parent_hidden_dim,
            ),
            nn.GELU(),
            nn.LayerNorm(self.parent_hidden_dim),
        )
        self.residual_score = nn.Sequential(
            nn.Linear(self.parent_hidden_dim * 2, self.parent_hidden_dim),
            nn.GELU(),
            nn.LayerNorm(self.parent_hidden_dim),
            nn.Linear(self.parent_hidden_dim, 1),
        )
        # Exact parent behavior at initialization.
        nn.init.zeros_(self.residual_score[-1].weight)
        nn.init.zeros_(self.residual_score[-1].bias)

    def init_state(
        self,
        batch_size: int,
        *,
        device: torch.device | None = None,
    ) -> SuccessorState:
        return SuccessorState(
            parent_hidden=self.parent.init_hidden(batch_size, device=device),
            fast_hidden=torch.zeros(batch_size, self.specialist_dim, device=device),
            slow_hidden=torch.zeros(batch_size, self.specialist_dim, device=device),
        )

    def forward_step(
        self,
        global_features: Tensor,
        action_features: Tensor,
        valid_actions: Tensor,
        state: SuccessorState,
    ) -> dict[str, Tensor | SuccessorState]:
        batch = global_features.shape[0]
        if global_features.shape != (batch, self.global_dim):
            raise ValueError("global_features shape mismatch")
        if action_features.ndim != 3 or action_features.shape[0] != batch:
            raise ValueError("action_features must be [batch, actions, action_dim]")
        if action_features.shape[-1] != self.action_dim:
            raise ValueError("action feature width mismatch")
        actions = action_features.shape[1]
        if valid_actions.shape != (batch, actions) or valid_actions.dtype != torch.bool:
            raise ValueError("valid_actions must be bool [batch, actions]")
        if state.parent_hidden.shape != (batch, self.parent_hidden_dim):
            raise ValueError("parent hidden shape mismatch")
        if state.fast_hidden.shape != (batch, self.specialist_dim):
            raise ValueError("fast hidden shape mismatch")
        if state.slow_hidden.shape != (batch, self.specialist_dim):
            raise ValueError("slow hidden shape mismatch")

        with torch.no_grad():
            parent_out = self.parent.forward_step(
                global_features,
                action_features,
                valid_actions,
                state.parent_hidden,
            )
            parent_next = parent_out["next_hidden"].detach()
            parent_logits = parent_out["action_logits"].detach()
            action_tokens = self.parent.action_encoder(action_features).detach()

        fast_input = self.fast_input(
            torch.cat((parent_next, global_features), dim=-1)
        )
        fast_next = self.fast_gru(fast_input, state.fast_hidden)

        slow_candidate = self.slow_gru(fast_next, state.slow_hidden)
        slow_gate = torch.sigmoid(
            self.slow_update_gate(
                torch.cat((fast_next, global_features), dim=-1)
            )
        )
        slow_next = (
            slow_gate * slow_candidate
            + (1.0 - slow_gate) * state.slow_hidden
        )

        context = self.context_projection(
            torch.cat((parent_next, fast_next, slow_next), dim=-1)
        )
        expanded = context[:, None, :].expand(batch, actions, self.parent_hidden_dim)
        residual = self.residual_score(
            torch.cat((action_tokens, expanded), dim=-1)
        ).squeeze(-1)
        residual = residual.masked_fill(
            ~valid_actions,
            torch.zeros((), dtype=residual.dtype, device=residual.device),
        )
        logits = parent_logits + residual
        logits = logits.masked_fill(
            ~valid_actions,
            torch.finfo(logits.dtype).min,
        )

        next_state = SuccessorState(
            parent_hidden=parent_next,
            fast_hidden=fast_next,
            slow_hidden=slow_next,
        )
        return {
            "action_logits": logits,
            "parent_action_logits": parent_logits,
            "residual_logits": residual,
            "slow_gate": slow_gate.squeeze(-1),
            "state": next_state,
        }

    def architecture(self) -> dict[str, int]:
        return {
            "global_dim": self.global_dim,
            "action_dim": self.action_dim,
            "parent_hidden_dim": self.parent_hidden_dim,
            "specialist_dim": self.specialist_dim,
        }


def specialist_parameter_count(model: DualTimescaleResidualPolicy) -> int:
    return sum(
        parameter.numel()
        for name, parameter in model.named_parameters()
        if not name.startswith("parent.")
    )


def total_parameter_count(model: DualTimescaleResidualPolicy) -> int:
    return parent_parameter_count(model.parent) + specialist_parameter_count(model)


def parent_state_dict(model: DualTimescaleResidualPolicy) -> Mapping[str, Tensor]:
    return model.parent.state_dict()
