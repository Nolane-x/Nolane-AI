from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor, nn

from native_core import (
    ACTION_FEATURE_DIM,
    TARGET_VISIBLE_FEATURE_INDEX,
    parameter_count,
    state_dict_sha256,
)
from successor_core import (
    TRACE_TOKEN_DIM,
    NativeR2TransitionPolicy,
    PublicTransitionTrace,
)


ATTRIBUTION_TOKEN_DIM = ACTION_FEATURE_DIM + TRACE_TOKEN_DIM


@dataclass
class PublicActionAttributedTrace:
    """Ordered public transition memory that retains the responsible action evidence."""

    max_length: int = 12
    _tokens: list[list[float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if type(self.max_length) is not int or self.max_length < 1:
            raise ValueError("max_length must be a positive exact integer")

    @staticmethod
    def _action_row(values: Sequence[float] | Tensor) -> list[float]:
        if isinstance(values, Tensor):
            if values.ndim != 1:
                raise ValueError("selected action features must be one-dimensional")
            row = [float(value) for value in values.detach().cpu().tolist()]
        else:
            row = [float(value) for value in values]
        if len(row) != ACTION_FEATURE_DIM:
            raise ValueError(
                f"selected action feature width must be {ACTION_FEATURE_DIM}"
            )
        return row

    def update(
        self,
        *,
        selected_action_features: Sequence[float] | Tensor,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        progress_delta: float,
        information_gain: float,
        failed: bool,
    ) -> None:
        transition = PublicTransitionTrace(max_length=1)
        transition.update(
            before=before,
            after=after,
            progress_delta=progress_delta,
            information_gain=information_gain,
            failed=failed,
        )
        transition_features, transition_valid = transition.encode()
        if not bool(transition_valid[0]):
            raise AssertionError("public transition token was not materialized")
        token = self._action_row(selected_action_features) + [
            float(value) for value in transition_features[0].tolist()
        ]
        if len(token) != ATTRIBUTION_TOKEN_DIM:
            raise AssertionError(f"unexpected attribution token width {len(token)}")
        self._tokens.append(token)
        if len(self._tokens) > self.max_length:
            del self._tokens[: len(self._tokens) - self.max_length]

    def encode(self) -> tuple[Tensor, Tensor]:
        features = torch.zeros(
            self.max_length,
            ATTRIBUTION_TOKEN_DIM,
            dtype=torch.float32,
        )
        valid = torch.zeros(self.max_length, dtype=torch.bool)
        for index, token in enumerate(self._tokens[-self.max_length :]):
            features[index] = torch.tensor(token, dtype=torch.float32)
            valid[index] = True
        return features, valid

    def __len__(self) -> int:
        return len(self._tokens)


class NativeR3AttributedBeliefPolicy(nn.Module):
    """Frozen accepted R2 parent plus hidden-target action-attributed feedback memory."""

    def __init__(
        self,
        parent: NativeR2TransitionPolicy,
        *,
        attribution_token_dim: int = ATTRIBUTION_TOKEN_DIM,
        attribution_hidden_dim: int = 128,
        attribution_length: int = 12,
    ) -> None:
        super().__init__()
        if attribution_token_dim != ATTRIBUTION_TOKEN_DIM:
            raise ValueError(
                f"attribution_token_dim must be {ATTRIBUTION_TOKEN_DIM}"
            )
        if attribution_hidden_dim < 1:
            raise ValueError("attribution_hidden_dim must be positive")
        if attribution_length < 1:
            raise ValueError("attribution_length must be positive")

        self.parent = parent
        self.attribution_token_dim = int(attribution_token_dim)
        self.attribution_hidden_dim = int(attribution_hidden_dim)
        self.attribution_length = int(attribution_length)

        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)
        self.parent.eval()

        parent_hidden = int(parent.parent.hidden_dim)
        r2_trace_hidden = int(parent.trace_hidden_dim)
        self.attribution_encoder = nn.Sequential(
            nn.Linear(self.attribution_token_dim, self.attribution_hidden_dim),
            nn.GELU(),
            nn.LayerNorm(self.attribution_hidden_dim),
        )
        self.attribution_recurrent = nn.GRUCell(
            self.attribution_hidden_dim,
            self.attribution_hidden_dim,
        )
        residual_input = (
            parent_hidden
            + parent_hidden
            + r2_trace_hidden
            + self.attribution_hidden_dim
        )
        self.hidden_target_attribution_score = nn.Sequential(
            nn.Linear(residual_input, parent_hidden),
            nn.GELU(),
            nn.LayerNorm(parent_hidden),
            nn.Linear(parent_hidden, 1),
        )
        nn.init.zeros_(self.hidden_target_attribution_score[-1].weight)
        nn.init.zeros_(self.hidden_target_attribution_score[-1].bias)

    def train(self, mode: bool = True) -> "NativeR3AttributedBeliefPolicy":
        super().train(mode)
        self.parent.eval()
        return self

    def architecture(self) -> dict[str, int]:
        return {
            "attribution_token_dim": self.attribution_token_dim,
            "attribution_hidden_dim": self.attribution_hidden_dim,
            "attribution_length": self.attribution_length,
            "r2_trace_token_dim": int(self.parent.trace_token_dim),
            "r2_trace_hidden_dim": int(self.parent.trace_hidden_dim),
            "r2_trace_length": int(self.parent.trace_length),
            "native_global_dim": int(self.parent.parent.global_dim),
            "native_action_dim": int(self.parent.parent.action_dim),
            "native_hidden_dim": int(self.parent.parent.hidden_dim),
            "native_attention_heads": int(self.parent.parent.attention_heads),
        }

    def successor_parameters(self) -> list[nn.Parameter]:
        modules = (
            self.attribution_encoder,
            self.attribution_recurrent,
            self.hidden_target_attribution_score,
        )
        return [
            parameter
            for module in modules
            for parameter in module.parameters()
        ]

    def set_training_scope(self) -> None:
        successor_ids = {id(parameter) for parameter in self.successor_parameters()}
        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)
        for parameter in self.successor_parameters():
            parameter.requires_grad_(id(parameter) in successor_ids)

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
        if attribution_features.shape[-1] != self.attribution_token_dim:
            raise ValueError("attribution token width mismatch")
        if attribution_features.shape[1] != self.attribution_length:
            raise ValueError("attribution length mismatch")
        if (
            attribution_valid.shape != attribution_features.shape[:2]
            or attribution_valid.dtype != torch.bool
        ):
            raise ValueError(
                "attribution_valid must be bool [batch, attribution_trace]"
            )

        with torch.no_grad():
            parent_output = self.parent.forward_step(
                global_features,
                action_features,
                valid_actions,
                parent_hidden,
                trace_features,
                trace_valid,
            )
            parent_logits = parent_output["action_logits"].detach()
            next_parent_hidden = parent_output["next_parent_hidden"].detach()
            r2_trace_hidden = parent_output["trace_hidden"].detach()
            action_tokens = self.parent.parent.action_encoder(
                action_features
            ).detach()

        batch, actions, _ = action_tokens.shape
        attribution_hidden = torch.zeros(
            batch,
            self.attribution_hidden_dim,
            dtype=attribution_features.dtype,
            device=attribution_features.device,
        )
        encoded = self.attribution_encoder(attribution_features)
        for index in range(self.attribution_length):
            candidate = self.attribution_recurrent(
                encoded[:, index, :],
                attribution_hidden,
            )
            mask = attribution_valid[:, index].unsqueeze(-1)
            attribution_hidden = torch.where(
                mask,
                candidate,
                attribution_hidden,
            )

        native_expanded = next_parent_hidden[:, None, :].expand(
            batch,
            actions,
            next_parent_hidden.shape[-1],
        )
        r2_trace_expanded = r2_trace_hidden[:, None, :].expand(
            batch,
            actions,
            r2_trace_hidden.shape[-1],
        )
        attribution_expanded = attribution_hidden[:, None, :].expand(
            batch,
            actions,
            attribution_hidden.shape[-1],
        )
        residual_input = torch.cat(
            (
                action_tokens,
                native_expanded,
                r2_trace_expanded,
                attribution_expanded,
            ),
            dim=-1,
        )
        residual = self.hidden_target_attribution_score(
            residual_input
        ).squeeze(-1)
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
            "attribution_residual_logits": residual,
            "next_parent_hidden": next_parent_hidden,
            "r2_trace_hidden": r2_trace_hidden,
            "attribution_hidden": attribution_hidden,
        }


def r3_state_dict_sha256(model: NativeR3AttributedBeliefPolicy) -> str:
    return state_dict_sha256(model.state_dict())
