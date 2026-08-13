from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

import torch
from torch import Tensor


def _categorical_tokens(value: Any) -> list[str]:
    tokens: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            tokens.extend(_categorical_tokens(child))
    elif isinstance(value, list):
        for child in value:
            tokens.extend(_categorical_tokens(child))
    elif isinstance(value, str):
        text = value.strip().lower()
        if 1 <= len(text) <= 16 and text.isalpha() and " " not in text:
            tokens.append(text)
    return tokens


def _token_fingerprint(token: str, *, dims: int) -> Tensor:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    bits: list[float] = []
    for byte in digest:
        for offset in range(8):
            bits.append(1.0 if ((byte >> offset) & 1) else -1.0)
            if len(bits) == dims:
                return torch.tensor(bits, dtype=torch.float32) / math.sqrt(dims)
    while len(bits) < dims:
        bits.extend(bits[: min(len(bits), dims - len(bits))])
    return torch.tensor(bits[:dims], dtype=torch.float32) / math.sqrt(dims)


def public_context_fingerprint(observation_text: str, *, dims: int = 64) -> Tensor:
    """Hash public categorical context values without consulting JSON key names."""
    if dims < 8:
        raise ValueError("context fingerprint requires at least 8 dimensions")
    payload = json.loads(observation_text)
    if not isinstance(payload, (dict, list)):
        raise ValueError("public observation must decode to an object or list")
    tokens = sorted(set(_categorical_tokens(payload)))
    if not tokens:
        return torch.zeros(dims, dtype=torch.float32)
    out = torch.stack([_token_fingerprint(token, dims=dims) for token in tokens]).sum(dim=0)
    norm = float(out.norm().item())
    return out / norm if norm > 1e-12 else torch.zeros_like(out)


@dataclass(frozen=True)
class EvidenceLookup:
    effect: Tensor
    count: int
    consistency: float
    context_similarity: float
    reliable: bool


@dataclass
class _EvidenceBucket:
    context: Tensor
    effect_mean: Tensor
    effect_m2: Tensor
    last_pre_state: Tensor
    count: int = 1

    @property
    def consistency(self) -> float:
        if self.count <= 1:
            return 1.0
        variance = self.effect_m2 / max(1, self.count - 1)
        return float(1.0 / (1.0 + variance.mean().item()))


class ConditionalEvidenceMemory:
    """Context-indexed non-parametric action-effect memory."""

    def __init__(self, *, action_count: int, effect_dim: int, context_similarity_threshold: float = 0.95) -> None:
        if action_count < 1 or effect_dim < 1:
            raise ValueError("action_count and effect_dim must be positive")
        if not 0.0 <= context_similarity_threshold <= 1.0:
            raise ValueError("context_similarity_threshold must be in [0,1]")
        self.action_count = int(action_count)
        self.effect_dim = int(effect_dim)
        self.context_similarity_threshold = float(context_similarity_threshold)
        self._buckets: list[list[_EvidenceBucket]] = [[] for _ in range(self.action_count)]

    @staticmethod
    def _similarity(a: Tensor, b: Tensor) -> float:
        a = a.detach().float().flatten()
        b = b.detach().float().flatten()
        if a.shape != b.shape:
            raise ValueError("context fingerprint shapes must match")
        an = float(a.norm().item())
        bn = float(b.norm().item())
        if an <= 1e-12 and bn <= 1e-12:
            return 1.0
        if an <= 1e-12 or bn <= 1e-12:
            return 0.0
        return float(torch.dot(a, b).item() / (an * bn))

    def _check_action(self, action_index: int) -> int:
        index = int(action_index)
        if not 0 <= index < self.action_count:
            raise ValueError("action index out of range")
        return index

    def _nearest(self, action_index: int, context: Tensor) -> tuple[_EvidenceBucket | None, float]:
        buckets = self._buckets[action_index]
        if not buckets:
            return None, 0.0
        scored = [(self._similarity(bucket.context, context), bucket) for bucket in buckets]
        similarity, bucket = max(scored, key=lambda item: item[0])
        if similarity < self.context_similarity_threshold:
            return None, similarity
        return bucket, similarity

    def update(self, action_index: int, context: Tensor, pre_state: Tensor, effect: Tensor) -> None:
        index = self._check_action(action_index)
        effect = effect.detach().float().flatten().clone()
        pre_state = pre_state.detach().float().flatten().clone()
        context = context.detach().float().flatten().clone()
        if effect.numel() != self.effect_dim:
            raise ValueError("effect dimension mismatch")
        bucket, _ = self._nearest(index, context)
        if bucket is None:
            self._buckets[index].append(_EvidenceBucket(context=context, effect_mean=effect, effect_m2=torch.zeros_like(effect), last_pre_state=pre_state))
            return
        bucket.count += 1
        delta = effect - bucket.effect_mean
        bucket.effect_mean = bucket.effect_mean + delta / bucket.count
        delta2 = effect - bucket.effect_mean
        bucket.effect_m2 = bucket.effect_m2 + delta * delta2
        bucket.last_pre_state = pre_state

    def retrieve(self, action_index: int, context: Tensor) -> EvidenceLookup:
        index = self._check_action(action_index)
        bucket, similarity = self._nearest(index, context.detach().float().flatten())
        if bucket is None:
            return EvidenceLookup(effect=torch.zeros(self.effect_dim, dtype=torch.float32), count=0, consistency=0.0, context_similarity=float(similarity), reliable=False)
        consistency = bucket.consistency
        return EvidenceLookup(effect=bucket.effect_mean.detach().clone(), count=int(bucket.count), consistency=float(consistency), context_similarity=float(similarity), reliable=bool(consistency >= 0.5))
