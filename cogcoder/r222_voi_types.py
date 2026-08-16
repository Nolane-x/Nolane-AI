from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Sequence

from .r220_operator_discovery import ProposalSupport

META_FEATURE_NAMES = (
    'bias',
    'top_posterior',
    'posterior_margin',
    'posterior_entropy',
    'max_disagreement',
    'query_fraction',
    'remaining_fraction',
    'accumulated_cost_norm',
    'cheap_reliability',
    'cheap_cost_norm',
    'strong_reliability',
    'strong_cost_norm',
)


def _norm_name(value: str, *, field: str) -> str:
    out = str(value).strip().lower()
    if not out:
        raise ValueError(f'{field} must be non-empty')
    return out


@dataclass(frozen=True)
class VerifierChannel:
    name: str
    reliability: float
    cost: float

    def __post_init__(self) -> None:
        name = _norm_name(self.name, field='name')
        reliability = float(self.reliability)
        cost = float(self.cost)
        if not 0.5 < reliability <= 1.0:
            raise ValueError('reliability must be in (0.5, 1.0]')
        if not math.isfinite(cost) or cost <= 0.0:
            raise ValueError('cost must be finite and positive')
        object.__setattr__(self, 'name', name)
        object.__setattr__(self, 'reliability', reliability)
        object.__setattr__(self, 'cost', cost)


@dataclass(frozen=True)
class VerifierRegime:
    regime_id: str
    cheap: VerifierChannel
    strong: VerifierChannel

    def __post_init__(self) -> None:
        regime_id = _norm_name(self.regime_id, field='regime_id')
        if self.cheap.name == self.strong.name:
            raise ValueError('verifier channel names must be distinct')
        object.__setattr__(self, 'regime_id', regime_id)


@dataclass(frozen=True)
class MetaState:
    supports: tuple[ProposalSupport, ...]
    max_remaining_disagreement: float
    queries_used: int
    max_queries: int
    remaining_queries: int
    accumulated_cost: float
    cheap: VerifierChannel
    strong: VerifierChannel

    def __post_init__(self) -> None:
        supports = tuple(self.supports)
        if not supports:
            raise ValueError('supports must be non-empty')
        if int(self.queries_used) < 0:
            raise ValueError('queries_used must be non-negative')
        if int(self.max_queries) <= 0:
            raise ValueError('max_queries must be positive')
        if int(self.remaining_queries) < 0:
            raise ValueError('remaining_queries must be non-negative')
        if int(self.queries_used) > int(self.max_queries):
            raise ValueError('queries_used cannot exceed max_queries')
        if float(self.accumulated_cost) < 0.0:
            raise ValueError('accumulated_cost must be non-negative')
        if not 0.0 <= float(self.max_remaining_disagreement) <= 0.5 + 1e-12:
            raise ValueError('max_remaining_disagreement must be in [0, 0.5]')
        object.__setattr__(self, 'supports', supports)
        object.__setattr__(self, 'queries_used', int(self.queries_used))
        object.__setattr__(self, 'max_queries', int(self.max_queries))
        object.__setattr__(self, 'remaining_queries', int(self.remaining_queries))
        object.__setattr__(self, 'accumulated_cost', float(self.accumulated_cost))
        object.__setattr__(self, 'max_remaining_disagreement', float(self.max_remaining_disagreement))


def _ranked(supports: Sequence[ProposalSupport]) -> tuple[ProposalSupport, ...]:
    return tuple(sorted(supports, key=lambda row: (-row.posterior, row.operator_id)))


def extract_meta_features(state: MetaState) -> tuple[float, ...]:
    ranked = _ranked(state.supports)
    top = ranked[0].posterior
    second = ranked[1].posterior if len(ranked) > 1 else 0.0
    margin = top - second
    entropy = -sum(row.posterior * math.log(max(row.posterior, 1e-15)) for row in ranked)
    entropy_norm = entropy / max(math.log(len(ranked)), 1.0)
    query_fraction = state.queries_used / state.max_queries
    evidence_pool = state.queries_used + state.remaining_queries
    remaining_fraction = state.remaining_queries / max(evidence_pool, 1)
    cost_scale = max(state.strong.cost, state.cheap.cost, 1e-12)
    accumulated_cost_norm = state.accumulated_cost / (state.max_queries * cost_scale)
    return (
        1.0,
        float(top),
        float(margin),
        float(entropy_norm),
        float(state.max_remaining_disagreement),
        float(query_fraction),
        float(remaining_fraction),
        float(accumulated_cost_norm),
        float(state.cheap.reliability),
        float(state.cheap.cost / cost_scale),
        float(state.strong.reliability),
        float(state.strong.cost / cost_scale),
    )

_NONBIAS_META_FEATURE_NAMES = META_FEATURE_NAMES[1:]
EXPANDED_META_FEATURE_NAMES = (
    ('bias',)
    + _NONBIAS_META_FEATURE_NAMES
    + tuple(f'{name}^2' for name in _NONBIAS_META_FEATURE_NAMES)
    + tuple(
        f'{left}*{right}'
        for i, left in enumerate(_NONBIAS_META_FEATURE_NAMES)
        for right in _NONBIAS_META_FEATURE_NAMES[i + 1:]
    )
)


def expand_meta_features(base_features: Sequence[float]) -> tuple[float, ...]:
    """Deterministic quadratic basis for the tiny linear VOI metacontroller.

    The base state remains task-agnostic. This expansion only exposes fixed
    interactions among confidence, uncertainty, reliability and relative cost;
    it introduces no learned feature extractor and no task identifiers.
    """
    base = tuple(float(v) for v in base_features)
    if len(base) != len(META_FEATURE_NAMES):
        raise ValueError('base feature width mismatch')
    if not all(math.isfinite(v) for v in base):
        raise ValueError('base features must be finite')
    nonbias = base[1:]
    out = [base[0], *nonbias]
    out.extend(v * v for v in nonbias)
    for i, left in enumerate(nonbias):
        for right in nonbias[i + 1:]:
            out.append(left * right)
    return tuple(out)
