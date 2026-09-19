from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor, nn

GLOBAL_FEATURE_DIM = 29
ACTION_FEATURE_DIM = 25
REGIME_LABELS = ("amber", "violet", "cobalt", "ivory", "sable", "mint", "coral", "silver")


def _regime_features(label: str | None) -> list[float]:
    values = [0.0] * len(REGIME_LABELS)
    if label in REGIME_LABELS:
        values[REGIME_LABELS.index(str(label))] = 1.0
    return values


@dataclass
class ActionStat:
    count: int = 0
    last_state_delta: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    mean_state_delta: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    last_progress_delta: float = 0.0
    mean_progress_delta: float = 0.0
    last_information_gain: float = 0.0
    best_progress_delta: float = -1.0
    failures: int = 0
    changed: int = 0
    last_resource_delta: list[float] = field(default_factory=lambda: [0.0, 0.0])
    mean_resource_delta: list[float] = field(default_factory=lambda: [0.0, 0.0])

    def update(
        self,
        *,
        state_delta: Sequence[float],
        progress_delta: float,
        information_gain: float,
        failed: bool,
        changed: bool,
        resource_delta: Sequence[float],
    ) -> None:
        self.count += 1
        n = float(self.count)
        self.last_state_delta = [float(value) for value in state_delta]
        self.last_progress_delta = float(progress_delta)
        self.last_information_gain = float(information_gain)
        self.best_progress_delta = max(self.best_progress_delta, float(progress_delta))
        self.last_resource_delta = [float(value) for value in resource_delta]
        for index, value in enumerate(state_delta):
            self.mean_state_delta[index] += (float(value) - self.mean_state_delta[index]) / n
        for index, value in enumerate(resource_delta):
            self.mean_resource_delta[index] += (float(value) - self.mean_resource_delta[index]) / n
        self.mean_progress_delta += (float(progress_delta) - self.mean_progress_delta) / n
        self.failures += int(bool(failed))
        self.changed += int(bool(changed))


class PublicActionMemory:
    """Episode-local memory built only from public observations and transitions."""

    def __init__(self, action_count: int) -> None:
        if type(action_count) is not int or action_count < 1:
            raise ValueError("action_count must be a positive exact integer")
        self.action_count = action_count
        self.total = [ActionStat() for _ in range(action_count)]
        self.by_context: dict[tuple[str, int], ActionStat] = {}
        self.by_regime_parity: dict[tuple[str, tuple[int, int, int], int], ActionStat] = {}

    @staticmethod
    def context_key(observation: Mapping[str, Any]) -> str:
        regime = observation.get("regime")
        return str(regime) if isinstance(regime, str) else "prereq"

    @staticmethod
    def parity_key(observation: Mapping[str, Any]) -> tuple[int, int, int]:
        state = observation.get("state")
        if not isinstance(state, list) or len(state) != 3:
            raise ValueError("public observation state must contain three coordinates")
        return tuple(int(value) % 2 for value in state)

    def context_stat(self, observation: Mapping[str, Any], action: int) -> ActionStat:
        key = (self.context_key(observation), int(action))
        return self.by_context.setdefault(key, ActionStat())

    def local_stat(self, observation: Mapping[str, Any], action: int) -> ActionStat:
        key = (self.context_key(observation), self.parity_key(observation), int(action))
        return self.by_regime_parity.setdefault(key, ActionStat())

    def seen_in_context(self, observation: Mapping[str, Any], action: int) -> int:
        key = (self.context_key(observation), int(action))
        stat = self.by_context.get(key)
        return 0 if stat is None else stat.count

    def update(
        self,
        *,
        action: int,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        progress_delta: float,
        information_gain: float,
        failed: bool,
    ) -> None:
        if not 0 <= int(action) < self.action_count:
            raise ValueError("action index outside memory")
        before_state = [float(x) for x in before["state"]]
        after_state = [float(x) for x in after["state"]]
        state_delta = [a - b for a, b in zip(after_state, before_state)]
        before_resources = before.get("resources") or {}
        after_resources = after.get("resources") or {}
        resource_delta = [
            float(after_resources.get("charge_level", 0)) - float(before_resources.get("charge_level", 0)),
            float(after_resources.get("gate_open", 0)) - float(before_resources.get("gate_open", 0)),
        ]
        changed = any(abs(value) > 1e-9 for value in state_delta + resource_delta)
        kwargs = dict(
            state_delta=state_delta,
            progress_delta=float(progress_delta),
            information_gain=float(information_gain),
            failed=bool(failed),
            changed=bool(changed),
            resource_delta=resource_delta,
        )
        self.total[int(action)].update(**kwargs)
        self.context_stat(before, int(action)).update(**kwargs)
        self.local_stat(before, int(action)).update(**kwargs)


def encode_public_state(
    observation: Mapping[str, Any],
    memory: PublicActionMemory,
    *,
    previous_feedback: Sequence[float],
) -> tuple[Tensor, Tensor, Tensor]:
    """Encode one FIGG-18 public state without private task fields."""

    raw_state = [int(value) for value in observation["state"]]
    state = [float(value) / 4.0 for value in raw_state]
    parity = [float(value % 2) for value in raw_state]
    target_raw = observation.get("target")
    target_visible = isinstance(target_raw, list) and len(target_raw) == 3
    target = [float(value) / 4.0 for value in target_raw] if target_visible else [0.0, 0.0, 0.0]
    modulus = 4 if "resources" in observation else 5
    distance = (
        [float((int(goal) - value) % modulus) / float(modulus - 1) for value, goal in zip(raw_state, target_raw)]
        if target_visible
        else [0.0, 0.0, 0.0]
    )
    resources = observation.get("resources") or {}
    global_values = (
        state
        + parity
        + target
        + distance
        + [1.0 if target_visible else 0.0]
        + [float(observation["progress_signal"])]
        + [min(1.0, float(observation["budget_remaining"]) / 32.0)]
        + [min(1.0, float(observation["step"]) / 32.0)]
        + [float(resources.get("charge_level", 0)) / 3.0]
        + [float(resources.get("gate_open", 0))]
        + _regime_features(observation.get("regime") if isinstance(observation.get("regime"), str) else None)
        + [float(value) for value in previous_feedback]
    )
    if len(global_values) != GLOBAL_FEATURE_DIM:
        raise AssertionError(f"unexpected global feature width {len(global_values)}")

    descriptions = observation["actions"]
    rows: list[list[float]] = []
    for action, description in enumerate(descriptions):
        total = memory.total[action]
        context = memory.context_stat(observation, action)
        local = memory.local_stat(observation, action)
        count = max(1, context.count)
        rows.append(
            [
                1.0 if "submit" in str(description).lower() else 0.0,
                min(1.0, total.count / 8.0),
                min(1.0, context.count / 4.0),
                *context.last_state_delta,
                *context.mean_state_delta,
                context.last_progress_delta,
                context.mean_progress_delta,
                context.last_information_gain,
                float(context.failures) / count,
                float(context.changed) / count,
                *context.last_resource_delta,
                *context.mean_resource_delta,
                min(1.0, local.count / 3.0),
                *local.last_state_delta,
                local.last_progress_delta,
                local.best_progress_delta,
                context.best_progress_delta,
            ]
        )
    if any(len(row) != ACTION_FEATURE_DIM for row in rows):
        raise AssertionError("unexpected action feature width")
    valid = [1.0] * len(rows)
    return (
        torch.tensor(global_values, dtype=torch.float32),
        torch.tensor(rows, dtype=torch.float32),
        torch.tensor(valid, dtype=torch.bool),
    )


class NativeRecurrentPolicy(nn.Module):
    """Small self-contained recurrent neural policy over public FIGG-18 evidence."""

    def __init__(
        self,
        *,
        global_dim: int = GLOBAL_FEATURE_DIM,
        action_dim: int = ACTION_FEATURE_DIM,
        hidden_dim: int = 128,
        attention_heads: int = 4,
    ) -> None:
        super().__init__()
        if hidden_dim % attention_heads:
            raise ValueError("hidden_dim must be divisible by attention_heads")
        self.global_dim = int(global_dim)
        self.action_dim = int(action_dim)
        self.hidden_dim = int(hidden_dim)
        self.attention_heads = int(attention_heads)

        self.global_encoder = nn.Sequential(
            nn.Linear(global_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.action_encoder = nn.Sequential(
            nn.Linear(action_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.action_attention = nn.MultiheadAttention(
            hidden_dim,
            attention_heads,
            batch_first=True,
        )
        self.recurrent = nn.GRUCell(hidden_dim * 2, hidden_dim)
        self.goal_head = nn.Linear(hidden_dim, 15)
        self.goal_belief_projection = nn.Linear(3, hidden_dim, bias=False)
        self.goal_policy_norm = nn.LayerNorm(hidden_dim)
        self.score = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, 1),
        )
        self.value_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, 1),
        )
        self.uncertainty_head = nn.Linear(hidden_dim, 1)

    def architecture(self) -> dict[str, int]:
        return {
            "global_dim": self.global_dim,
            "action_dim": self.action_dim,
            "hidden_dim": self.hidden_dim,
            "attention_heads": self.attention_heads,
        }

    def init_hidden(self, batch_size: int, *, device: torch.device | None = None) -> Tensor:
        return torch.zeros(batch_size, self.hidden_dim, device=device)

    def forward_step(
        self,
        global_features: Tensor,
        action_features: Tensor,
        valid_actions: Tensor,
        hidden: Tensor,
    ) -> dict[str, Tensor]:
        if global_features.ndim != 2 or global_features.shape[-1] != self.global_dim:
            raise ValueError("global_features must be [batch, global_dim]")
        if action_features.ndim != 3 or action_features.shape[-1] != self.action_dim:
            raise ValueError("action_features must be [batch, actions, action_dim]")
        batch, actions, _ = action_features.shape
        if valid_actions.shape != (batch, actions) or valid_actions.dtype != torch.bool:
            raise ValueError("valid_actions must be bool [batch, actions]")
        if hidden.shape != (batch, self.hidden_dim):
            raise ValueError("hidden shape mismatch")
        if not bool(valid_actions.any(dim=1).all()):
            raise ValueError("each batch row needs at least one valid action")

        global_token = self.global_encoder(global_features)
        action_tokens = self.action_encoder(action_features)
        attended, _weights = self.action_attention(
            global_token[:, None, :],
            action_tokens,
            action_tokens,
            key_padding_mask=~valid_actions,
            need_weights=False,
        )
        next_hidden = self.recurrent(
            torch.cat((global_token, attended[:, 0, :]), dim=-1),
            hidden,
        )
        goal_logits = self.goal_head(next_hidden).view(batch, 3, 5)
        goal_probability = torch.softmax(goal_logits, dim=-1)
        goal_values = torch.arange(
            5,
            device=goal_logits.device,
            dtype=goal_logits.dtype,
        ) / 4.0
        goal_expectation = (goal_probability * goal_values[None, None, :]).sum(dim=-1)
        policy_hidden = self.goal_policy_norm(
            next_hidden + self.goal_belief_projection(goal_expectation)
        )
        expanded = policy_hidden[:, None, :].expand(batch, actions, self.hidden_dim)
        logits = self.score(torch.cat((action_tokens, expanded), dim=-1)).squeeze(-1)
        logits = logits.masked_fill(~valid_actions, torch.finfo(logits.dtype).min)
        return {
            "action_logits": logits,
            "next_hidden": next_hidden,
            "goal_logits": goal_logits,
            "goal_expectation": goal_expectation,
            "value": self.value_head(next_hidden).squeeze(-1),
            "uncertainty": torch.sigmoid(self.uncertainty_head(next_hidden)).squeeze(-1),
        }


def parameter_count(module: nn.Module) -> int:
    return sum(parameter.numel() for parameter in module.parameters())


def state_dict_sha256(state_dict: Mapping[str, Tensor]) -> str:
    digest = hashlib.sha256()
    for name in sorted(state_dict):
        tensor = state_dict[name].detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(tensor.dtype).encode("ascii"))
        digest.update(b"\0")
        digest.update(json.dumps(list(tensor.shape), separators=(",", ":")).encode("ascii"))
        digest.update(b"\0")
        digest.update(tensor.reshape(-1).view(torch.uint8).numpy().tobytes())
        digest.update(b"\0")
    return digest.hexdigest()
