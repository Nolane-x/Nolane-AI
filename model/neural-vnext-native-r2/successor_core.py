from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor, nn

from native_core import (
    NativeRecurrentPolicy,
    TARGET_VISIBLE_FEATURE_INDEX,
    parameter_count,
    state_dict_sha256,
)


TRACE_TOKEN_DIM = 25


@dataclass
class PublicTransitionTrace:
    """Bounded ordered memory derived only from public transition evidence."""

    max_length: int = 8
    _tokens: list[list[float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if type(self.max_length) is not int or self.max_length < 1:
            raise ValueError("max_length must be a positive exact integer")

    @staticmethod
    def _state(observation: Mapping[str, Any]) -> list[int]:
        raw = observation.get("state")
        if not isinstance(raw, list) or len(raw) != 3:
            raise ValueError("public observation state must contain three coordinates")
        return [int(value) for value in raw]

    @staticmethod
    def _resources(observation: Mapping[str, Any]) -> Mapping[str, Any]:
        value = observation.get("resources")
        return value if isinstance(value, Mapping) else {}

    def update(
        self,
        *,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        progress_delta: float,
        information_gain: float,
        failed: bool,
    ) -> None:
        before_state = self._state(before)
        after_state = self._state(after)
        before_norm = [float(value) / 4.0 for value in before_state]
        after_norm = [float(value) / 4.0 for value in after_state]
        delta_norm = [
            float(after_value - before_value) / 4.0
            for before_value, after_value in zip(before_state, after_state)
        ]
        before_resources = self._resources(before)
        after_resources = self._resources(after)
        resource_delta = [
            (
                float(after_resources.get("charge_level", 0))
                - float(before_resources.get("charge_level", 0))
            )
            / 3.0,
            float(after_resources.get("gate_open", 0))
            - float(before_resources.get("gate_open", 0)),
        ]
        changed = any(abs(value) > 1e-12 for value in delta_norm + resource_delta)
        before_regime = before.get("regime")
        after_regime = after.get("regime")
        regime_changed = (
            isinstance(before_regime, str)
            and isinstance(after_regime, str)
            and before_regime != after_regime
        )
        target = before.get("target")
        target_visible = isinstance(target, list) and len(target) == 3

        token = (
            before_norm
            + after_norm
            + delta_norm
            + [
                float(before.get("progress_signal", 0.0)),
                float(after.get("progress_signal", 0.0)),
                float(progress_delta),
                float(information_gain),
                float(bool(failed)),
                float(bool(changed)),
                float(bool(regime_changed)),
                float(bool(target_visible)),
            ]
            + [float(value % 2) for value in before_state]
            + [float(value % 2) for value in after_state]
            + resource_delta
        )
        if len(token) != TRACE_TOKEN_DIM:
            raise AssertionError(f"unexpected transition token width {len(token)}")
        self._tokens.append([float(value) for value in token])
        if len(self._tokens) > self.max_length:
            del self._tokens[: len(self._tokens) - self.max_length]

    def encode(self) -> tuple[Tensor, Tensor]:
        features = torch.zeros(self.max_length, TRACE_TOKEN_DIM, dtype=torch.float32)
        valid = torch.zeros(self.max_length, dtype=torch.bool)
        for index, token in enumerate(self._tokens[-self.max_length :]):
            features[index] = torch.tensor(token, dtype=torch.float32)
            valid[index] = True
        return features, valid

    def __len__(self) -> int:
        return len(self._tokens)


class NativeR2TransitionPolicy(nn.Module):
    """Frozen accepted parent plus a trainable public-transition residual."""

    def __init__(
        self,
        parent: NativeRecurrentPolicy,
        *,
        trace_token_dim: int = TRACE_TOKEN_DIM,
        trace_hidden_dim: int = 128,
        trace_length: int = 8,
    ) -> None:
        super().__init__()
        if trace_token_dim != TRACE_TOKEN_DIM:
            raise ValueError(f"trace_token_dim must be {TRACE_TOKEN_DIM}")
        if trace_hidden_dim < 1:
            raise ValueError("trace_hidden_dim must be positive")
        if trace_length < 1:
            raise ValueError("trace_length must be positive")

        self.parent = parent
        self.trace_token_dim = int(trace_token_dim)
        self.trace_hidden_dim = int(trace_hidden_dim)
        self.trace_length = int(trace_length)

        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)
        self.parent.eval()

        parent_hidden = int(parent.hidden_dim)
        self.trace_encoder = nn.Sequential(
            nn.Linear(self.trace_token_dim, self.trace_hidden_dim),
            nn.GELU(),
            nn.LayerNorm(self.trace_hidden_dim),
        )
        self.trace_recurrent = nn.GRUCell(
            self.trace_hidden_dim,
            self.trace_hidden_dim,
        )
        residual_input = parent_hidden * 2 + self.trace_hidden_dim
        self.residual_score = nn.Sequential(
            nn.Linear(residual_input, parent_hidden),
            nn.GELU(),
            nn.LayerNorm(parent_hidden),
            nn.Linear(parent_hidden, 1),
        )
        self.hidden_target_residual_score = nn.Sequential(
            nn.Linear(residual_input, parent_hidden),
            nn.GELU(),
            nn.LayerNorm(parent_hidden),
            nn.Linear(parent_hidden, 1),
        )
        nn.init.zeros_(self.residual_score[-1].weight)
        nn.init.zeros_(self.residual_score[-1].bias)
        nn.init.zeros_(self.hidden_target_residual_score[-1].weight)
        nn.init.zeros_(self.hidden_target_residual_score[-1].bias)

    def train(self, mode: bool = True) -> "NativeR2TransitionPolicy":
        super().train(mode)
        self.parent.eval()
        return self

    def architecture(self) -> dict[str, int]:
        return {
            "trace_token_dim": self.trace_token_dim,
            "trace_hidden_dim": self.trace_hidden_dim,
            "trace_length": self.trace_length,
            "parent_global_dim": int(self.parent.global_dim),
            "parent_action_dim": int(self.parent.action_dim),
            "parent_hidden_dim": int(self.parent.hidden_dim),
            "parent_attention_heads": int(self.parent.attention_heads),
        }

    def general_parameters(self) -> list[nn.Parameter]:
        modules = (
            self.trace_encoder,
            self.trace_recurrent,
            self.residual_score,
        )
        return [
            parameter
            for module in modules
            for parameter in module.parameters()
        ]

    def hidden_target_parameters(self) -> list[nn.Parameter]:
        return list(self.hidden_target_residual_score.parameters())

    def successor_parameters(self) -> list[nn.Parameter]:
        return self.general_parameters() + self.hidden_target_parameters()

    def parameters_for_scope(self, scope: str) -> list[nn.Parameter]:
        if scope == "general":
            return self.general_parameters()
        if scope == "hidden_target":
            return self.hidden_target_parameters()
        if scope == "all":
            return self.successor_parameters()
        raise ValueError(f"unknown successor training scope {scope!r}")

    def set_training_scope(self, scope: str) -> None:
        selected = {id(parameter) for parameter in self.parameters_for_scope(scope)}
        for parameter in self.parent.parameters():
            parameter.requires_grad_(False)
        for parameter in self.successor_parameters():
            parameter.requires_grad_(id(parameter) in selected)

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
        return self.parent.init_hidden(batch_size, device=device)

    def forward_step(
        self,
        global_features: Tensor,
        action_features: Tensor,
        valid_actions: Tensor,
        parent_hidden: Tensor,
        trace_features: Tensor,
        trace_valid: Tensor,
    ) -> dict[str, Tensor]:
        if trace_features.ndim != 3:
            raise ValueError("trace_features must be [batch, trace, token_dim]")
        if trace_features.shape[-1] != self.trace_token_dim:
            raise ValueError("trace token width mismatch")
        if trace_features.shape[1] != self.trace_length:
            raise ValueError("trace length mismatch")
        if trace_valid.shape != trace_features.shape[:2] or trace_valid.dtype != torch.bool:
            raise ValueError("trace_valid must be bool [batch, trace]")

        with torch.no_grad():
            parent_output = self.parent.forward_step(
                global_features,
                action_features,
                valid_actions,
                parent_hidden,
            )
            parent_logits = parent_output["action_logits"].detach()
            next_parent_hidden = parent_output["next_hidden"].detach()
            action_tokens = self.parent.action_encoder(action_features).detach()

        batch, actions, _ = action_tokens.shape
        trace_hidden = torch.zeros(
            batch,
            self.trace_hidden_dim,
            dtype=trace_features.dtype,
            device=trace_features.device,
        )
        encoded_trace = self.trace_encoder(trace_features)
        for index in range(self.trace_length):
            candidate = self.trace_recurrent(encoded_trace[:, index, :], trace_hidden)
            mask = trace_valid[:, index].unsqueeze(-1)
            trace_hidden = torch.where(mask, candidate, trace_hidden)

        parent_expanded = next_parent_hidden[:, None, :].expand(
            batch,
            actions,
            next_parent_hidden.shape[-1],
        )
        trace_expanded = trace_hidden[:, None, :].expand(
            batch,
            actions,
            self.trace_hidden_dim,
        )
        residual_input = torch.cat(
            (
                action_tokens,
                parent_expanded,
                trace_expanded,
            ),
            dim=-1,
        )
        residual = self.residual_score(residual_input).squeeze(-1)
        hidden_target_residual = self.hidden_target_residual_score(
            residual_input
        ).squeeze(-1)
        target_visible = global_features[
            :, TARGET_VISIBLE_FEATURE_INDEX : TARGET_VISIBLE_FEATURE_INDEX + 1
        ].clamp(0.0, 1.0)
        hidden_target_gate = 1.0 - target_visible
        hidden_target_residual = hidden_target_residual * hidden_target_gate
        residual = residual.masked_fill(~valid_actions, 0.0)
        hidden_target_residual = hidden_target_residual.masked_fill(
            ~valid_actions,
            0.0,
        )
        combined_residual = residual + hidden_target_residual
        logits = (parent_logits + combined_residual).masked_fill(
            ~valid_actions,
            torch.finfo(parent_logits.dtype).min,
        )
        return {
            "action_logits": logits,
            "parent_action_logits": parent_logits,
            "residual_logits": residual,
            "hidden_target_residual_logits": hidden_target_residual,
            "combined_residual_logits": combined_residual,
            "next_parent_hidden": next_parent_hidden,
            "trace_hidden": trace_hidden,
        }


def successor_state_dict_sha256(model: NativeR2TransitionPolicy) -> str:
    return state_dict_sha256(model.state_dict())
