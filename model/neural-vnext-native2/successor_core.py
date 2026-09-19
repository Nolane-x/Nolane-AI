from __future__ import annotations

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
    TARGET_VISIBLE_FEATURE_INDEX,
    NativeRecurrentPolicy,
)


class SuccessorResidualPolicy(nn.Module):
    """Frozen accepted parent plus a zero-init public universal residual.

    The parent remains an exact immutable submodule. The successor learns only a
    shared per-action residual from public global features, parent recurrent
    hidden state, and parent action tokens. No private benchmark state enters
    this module.
    """

    def __init__(self, parent: NativeRecurrentPolicy) -> None:
        super().__init__()
        self.parent = parent
        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)

        hidden_dim = int(parent.hidden_dim)
        self.global_projection = nn.Linear(int(parent.global_dim), hidden_dim)
        self.policy_norm = nn.LayerNorm(hidden_dim)
        self.residual_score = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )
        nn.init.zeros_(self.residual_score[-1].weight)
        nn.init.zeros_(self.residual_score[-1].bias)

        self.global_dim = int(parent.global_dim)
        self.action_dim = int(parent.action_dim)
        self.hidden_dim = hidden_dim
        self.attention_heads = int(parent.attention_heads)

    def architecture(self) -> dict[str, Any]:
        return {
            "kind": "neural-vnext-native2-universal-residual-v1",
            "global_dim": self.global_dim,
            "action_dim": self.action_dim,
            "hidden_dim": self.hidden_dim,
            "attention_heads": self.attention_heads,
            "parent_architecture": self.parent.architecture(),
            "parent_frozen": True,
            "residual_final_zero_initialized": True,
        }

    def init_hidden(
        self,
        batch_size: int,
        *,
        device: torch.device | None = None,
    ) -> Tensor:
        return self.parent.init_hidden(batch_size, device=device)

    def successor_parameters(self) -> list[nn.Parameter]:
        rows: list[nn.Parameter] = []
        for module in (self.global_projection, self.policy_norm, self.residual_score):
            rows.extend(module.parameters())
        return rows

    def configure_successor_training(self) -> dict[str, int]:
        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)
        successor = self.successor_parameters()
        for parameter in successor:
            parameter.requires_grad_(True)
        return {
            "parent_frozen_parameters": sum(p.numel() for p in self.parent.parameters()),
            "successor_trainable_parameters": sum(p.numel() for p in successor),
        }

    def forward_step(
        self,
        global_features: Tensor,
        action_features: Tensor,
        valid_actions: Tensor,
        hidden: Tensor,
    ) -> dict[str, Tensor]:
        with torch.no_grad():
            parent_output = self.parent.forward_step(
                global_features,
                action_features,
                valid_actions,
                hidden,
            )
            action_tokens = self.parent.action_encoder(action_features)

        next_hidden = parent_output["next_hidden"]
        public_context = torch.nn.functional.gelu(
            self.global_projection(global_features)
        )
        residual_hidden = self.policy_norm(next_hidden + public_context)
        batch, actions, _ = action_tokens.shape
        residual_expanded = residual_hidden[:, None, :].expand(
            batch,
            actions,
            self.hidden_dim,
        )
        residual_logits = self.residual_score(
            torch.cat((action_tokens, residual_expanded), dim=-1)
        ).squeeze(-1)
        target_visible = global_features[
            :, TARGET_VISIBLE_FEATURE_INDEX : TARGET_VISIBLE_FEATURE_INDEX + 1
        ].clamp(0.0, 1.0)
        gated_residual_logits = target_visible * residual_logits

        logits = parent_output["action_logits"] + gated_residual_logits
        logits = logits.masked_fill(
            ~valid_actions,
            torch.finfo(logits.dtype).min,
        )
        return {
            **parent_output,
            "action_logits": logits,
            "parent_action_logits": parent_output["action_logits"],
            "successor_residual_logits": residual_logits,
            "successor_gated_residual_logits": gated_residual_logits,
            "target_visible_gate": target_visible,
            "next_hidden": next_hidden,
        }


def successor_parameter_count(model: SuccessorResidualPolicy) -> dict[str, int]:
    parent = sum(parameter.numel() for parameter in model.parent.parameters())
    successor = sum(parameter.numel() for parameter in model.successor_parameters())
    return {
        "parent_parameters": parent,
        "successor_parameters": successor,
        "physical_parameters": parent + successor,
    }
