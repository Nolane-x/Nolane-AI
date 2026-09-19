from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch
from torch import Tensor, nn
import torch.nn.functional as F

PAD_TOKEN = 0
BYTE_OFFSET = 1
VOCAB_SIZE = 257


def encode_public_text(text: str, *, max_bytes: int) -> Tensor:
    if type(max_bytes) is not int or max_bytes < 8:
        raise ValueError("max_bytes must be an exact integer >= 8")
    raw = text.encode("utf-8", errors="strict")[:max_bytes]
    result = torch.zeros(max_bytes, dtype=torch.long)
    if raw:
        result[: len(raw)] = torch.tensor([int(value) + BYTE_OFFSET for value in raw], dtype=torch.long)
    return result


def encode_public_actions(
    descriptions: Sequence[str],
    *,
    max_actions: int = 6,
    max_bytes: int = 64,
) -> tuple[Tensor, Tensor]:
    if not descriptions:
        raise ValueError("at least one public action description is required")
    if len(descriptions) > max_actions:
        raise ValueError("public action count exceeds max_actions")
    tokens = torch.zeros(max_actions, max_bytes, dtype=torch.long)
    mask = torch.zeros(max_actions, dtype=torch.bool)
    for index, description in enumerate(descriptions):
        tokens[index] = encode_public_text(str(description), max_bytes=max_bytes)
        mask[index] = True
    return tokens, mask


class ByteSequenceEncoder(nn.Module):
    """Small order-sensitive encoder over public UTF-8 bytes only."""

    def __init__(self, *, max_bytes: int, byte_dim: int, output_dim: int) -> None:
        super().__init__()
        if min(max_bytes, byte_dim, output_dim) < 1:
            raise ValueError("encoder dimensions must be positive")
        self.max_bytes = int(max_bytes)
        self.byte_dim = int(byte_dim)
        self.output_dim = int(output_dim)
        self.embedding = nn.Embedding(VOCAB_SIZE, byte_dim, padding_idx=PAD_TOKEN)
        self.position = nn.Parameter(torch.zeros(max_bytes, byte_dim))
        self.conv3 = nn.Conv1d(byte_dim, output_dim // 2, kernel_size=3, padding=1)
        self.conv5 = nn.Conv1d(byte_dim, output_dim // 2, kernel_size=5, padding=2)
        merged = 2 * (output_dim // 2)
        self.projection = nn.Sequential(
            nn.Linear(merged * 2, output_dim),
            nn.GELU(),
            nn.LayerNorm(output_dim),
        )
        nn.init.normal_(self.position, mean=0.0, std=0.01)

    def forward(self, tokens: Tensor) -> Tensor:
        if tokens.ndim != 2 or tokens.shape[1] != self.max_bytes:
            raise ValueError("byte tokens must be [batch, max_bytes]")
        if tokens.dtype != torch.long:
            raise ValueError("byte tokens must be int64")
        mask = tokens.ne(PAD_TOKEN)
        x = self.embedding(tokens) + self.position.unsqueeze(0)
        x = x * mask.unsqueeze(-1)
        x = x.transpose(1, 2)
        a = F.gelu(self.conv3(x))
        b = F.gelu(self.conv5(x))
        features = torch.cat((a, b), dim=1).transpose(1, 2)
        float_mask = mask.unsqueeze(-1).to(dtype=features.dtype)
        denom = float_mask.sum(dim=1).clamp_min(1.0)
        mean = (features * float_mask).sum(dim=1) / denom
        masked = features.masked_fill(~mask.unsqueeze(-1), -torch.inf)
        maximum = masked.max(dim=1).values
        maximum = torch.where(torch.isfinite(maximum), maximum, torch.zeros_like(maximum))
        return self.projection(torch.cat((mean, maximum), dim=-1))


class SharedPublicReasoningCell(nn.Module):
    def __init__(self, hidden_dim: int, *, ff_mult: int = 2) -> None:
        super().__init__()
        self.hidden_dim = int(hidden_dim)
        self.query = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.key = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.value = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.context_out = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.latent_gru = nn.GRUCell(hidden_dim, hidden_dim)
        self.latent_norm = nn.LayerNorm(hidden_dim)
        self.action_norm = nn.LayerNorm(hidden_dim)
        self.action_ff = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * ff_mult),
            nn.GELU(),
            nn.Linear(hidden_dim * ff_mult, hidden_dim),
        )
        self.depth = nn.Embedding(8, hidden_dim)
        self.action_gate = nn.Parameter(torch.tensor(-1.0))

    def forward(
        self,
        latent: Tensor,
        action_tokens: Tensor,
        action_mask: Tensor,
        *,
        step: int,
    ) -> tuple[Tensor, Tensor]:
        if step >= self.depth.num_embeddings:
            raise ValueError("reasoning step exceeds encoded depth")
        q = self.query(latent).unsqueeze(1)
        k = self.key(action_tokens)
        v = self.value(action_tokens)
        scores = (q * k).sum(dim=-1) / float(self.hidden_dim) ** 0.5
        scores = scores.masked_fill(~action_mask, -1e9)
        weights = torch.softmax(scores, dim=-1)
        context = (weights.unsqueeze(-1) * v).sum(dim=1)
        depth = self.depth.weight[step].unsqueeze(0)
        latent = self.latent_gru(self.context_out(context) + depth, latent)
        latent = self.latent_norm(latent)
        broadcast = latent.unsqueeze(1) + depth.unsqueeze(1)
        delta = self.action_ff(self.action_norm(action_tokens + broadcast))
        action_tokens = self.action_norm(
            action_tokens + torch.sigmoid(self.action_gate) * delta + 0.1 * broadcast
        )
        action_tokens = action_tokens * action_mask.unsqueeze(-1)
        return latent, action_tokens


@dataclass(frozen=True)
class PublicR18Architecture:
    observation_bytes: int = 512
    action_bytes: int = 64
    max_actions: int = 6
    byte_dim: int = 32
    hidden_dim: int = 192
    reasoning_steps: int = 3
    ff_mult: int = 2


class PublicR18RecursiveCore(nn.Module):
    """Self-contained recurrent Neural Core candidate over public FIGG-18 state.

    The module receives only rendered public observations, public action
    descriptions, previous public transition feedback and its own recurrent
    memory. It has no interface for R18 private simulator fields or oracle state.
    """

    def __init__(
        self,
        *,
        observation_bytes: int = 512,
        action_bytes: int = 64,
        max_actions: int = 6,
        byte_dim: int = 32,
        hidden_dim: int = 192,
        action_memory_dim: int = 10,
        public_scalar_dim: int = 15,
        reasoning_steps: int = 3,
        ff_mult: int = 2,
    ) -> None:
        super().__init__()
        if not 1 <= reasoning_steps <= 8:
            raise ValueError("reasoning_steps must lie in [1, 8]")
        if hidden_dim < 32:
            raise ValueError("hidden_dim must be >= 32")
        self.observation_bytes = int(observation_bytes)
        self.action_bytes = int(action_bytes)
        self.max_actions = int(max_actions)
        self.byte_dim = int(byte_dim)
        self.hidden_dim = int(hidden_dim)
        self.action_memory_dim = int(action_memory_dim)
        self.public_scalar_dim = int(public_scalar_dim)
        self.reasoning_steps = int(reasoning_steps)
        self.ff_mult = int(ff_mult)

        self.observation_encoder = ByteSequenceEncoder(
            max_bytes=observation_bytes,
            byte_dim=byte_dim,
            output_dim=hidden_dim,
        )
        self.action_encoder = ByteSequenceEncoder(
            max_bytes=action_bytes,
            byte_dim=byte_dim,
            output_dim=hidden_dim,
        )
        self.public_scalar_projection = nn.Sequential(
            nn.Linear(public_scalar_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
        )
        self.feedback_projection = nn.Sequential(
            nn.Linear(4, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
        )
        self.previous_action_projection = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.memory_input_norm = nn.LayerNorm(hidden_dim)
        self.memory_gru = nn.GRUCell(hidden_dim, hidden_dim)
        self.memory_norm = nn.LayerNorm(hidden_dim)
        self.action_anchor = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.action_memory_projection = nn.Sequential(
            nn.Linear(action_memory_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
        )
        self.observation_to_action = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.memory_to_action = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.reasoning_cell = SharedPublicReasoningCell(hidden_dim, ff_mult=ff_mult)
        self.policy_head = nn.Linear(hidden_dim, 1)
        self.value_head = nn.Linear(hidden_dim, 1)
        self.ponder_head = nn.Linear(hidden_dim, 1)

    def architecture(self) -> dict[str, int]:
        return {
            "observation_bytes": self.observation_bytes,
            "action_bytes": self.action_bytes,
            "max_actions": self.max_actions,
            "byte_dim": self.byte_dim,
            "hidden_dim": self.hidden_dim,
            "action_memory_dim": self.action_memory_dim,
            "public_scalar_dim": self.public_scalar_dim,
            "reasoning_steps": self.reasoning_steps,
            "ff_mult": self.ff_mult,
        }

    def initial_memory(self, batch_size: int, *, device: torch.device | None = None) -> Tensor:
        if type(batch_size) is not int or batch_size < 1:
            raise ValueError("batch_size must be a positive exact integer")
        return torch.zeros(batch_size, self.hidden_dim, device=device)

    def forward(
        self,
        *,
        observation_tokens: Tensor,
        action_tokens: Tensor,
        action_mask: Tensor,
        action_memory: Tensor,
        public_scalars: Tensor,
        memory: Tensor,
        previous_action: Tensor,
        previous_feedback: Tensor,
    ) -> dict[str, Tensor]:
        if observation_tokens.ndim != 2:
            raise ValueError("observation_tokens must be [batch, bytes]")
        batch = observation_tokens.shape[0]
        if action_tokens.shape != (batch, self.max_actions, self.action_bytes):
            raise ValueError("action_tokens must be [batch, max_actions, action_bytes]")
        if action_mask.shape != (batch, self.max_actions) or action_mask.dtype != torch.bool:
            raise ValueError("action_mask must be bool [batch, max_actions]")
        if action_memory.shape != (batch, self.max_actions, self.action_memory_dim):
            raise ValueError("action_memory has invalid shape")
        if public_scalars.shape != (batch, self.public_scalar_dim):
            raise ValueError("public_scalars has invalid shape")
        if memory.shape != (batch, self.hidden_dim):
            raise ValueError("memory has invalid shape")
        if previous_action.shape != (batch,) or previous_action.dtype != torch.long:
            raise ValueError("previous_action must be int64 [batch]")
        if previous_feedback.shape != (batch, 3):
            raise ValueError("previous_feedback must be [batch, 3]")
        if not bool(action_mask.any(dim=1).all()):
            raise ValueError("each sample needs at least one legal public action")

        observation = self.observation_encoder(observation_tokens)
        scalar_context = self.public_scalar_projection(public_scalars)
        observation = self.memory_norm(observation + scalar_context)
        flat_actions = action_tokens.reshape(batch * self.max_actions, self.action_bytes)
        action_encoded = self.action_encoder(flat_actions).reshape(
            batch, self.max_actions, self.hidden_dim
        )
        action_encoded = action_encoded * action_mask.unsqueeze(-1)

        has_previous = previous_action.ge(0)
        safe_previous = previous_action.clamp(min=0, max=self.max_actions - 1)
        previous = action_encoded.gather(
            1, safe_previous[:, None, None].expand(batch, 1, self.hidden_dim)
        ).squeeze(1)
        previous = previous * has_previous.unsqueeze(-1)
        feedback = torch.cat(
            (previous_feedback, has_previous.to(dtype=previous_feedback.dtype)[:, None]),
            dim=-1,
        )
        memory_input = self.memory_input_norm(
            observation
            + self.previous_action_projection(previous)
            + self.feedback_projection(feedback)
        )
        next_memory = self.memory_norm(self.memory_gru(memory_input, memory))

        actions = self.action_anchor(action_encoded)
        actions = actions + self.action_memory_projection(action_memory)
        actions = actions + self.observation_to_action(observation).unsqueeze(1)
        actions = actions + self.memory_to_action(next_memory).unsqueeze(1)
        actions = actions * action_mask.unsqueeze(-1)
        latent = self.memory_norm(next_memory + observation)

        logits_trajectory: list[Tensor] = []
        value_trajectory: list[Tensor] = []
        ponder_trajectory: list[Tensor] = []
        for step in range(self.reasoning_steps):
            latent, actions = self.reasoning_cell(
                latent, actions, action_mask, step=step
            )
            logits = self.policy_head(actions).squeeze(-1).masked_fill(~action_mask, -1e9)
            values = self.value_head(actions).squeeze(-1).masked_fill(~action_mask, -1e9)
            logits_trajectory.append(logits)
            value_trajectory.append(values)
            ponder_trajectory.append(self.ponder_head(latent).squeeze(-1))

        trajectory = torch.stack(logits_trajectory, dim=1)
        return {
            "action_logits": trajectory[:, -1],
            "action_logits_trajectory": trajectory,
            "action_value_trajectory": torch.stack(value_trajectory, dim=1),
            "ponder_logits_trajectory": torch.stack(ponder_trajectory, dim=1),
            "next_memory": next_memory,
            "latent_state": latent,
        }


def public_r18_parameter_count(module: nn.Module) -> int:
    return sum(parameter.numel() for parameter in module.parameters())
