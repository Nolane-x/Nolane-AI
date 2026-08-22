from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .registry import AgentRegistry
from .types import canonical_digest


class MemoryIntelligenceDomain(str, Enum):
    LIFECYCLE = 'lifecycle'
    KNOWLEDGE_GRAPH = 'knowledge_graph'
    CONTEXT_COMPILATION = 'context_compilation'
    CROSS_MEMORY = 'cross_memory'


@dataclass(frozen=True, slots=True)
class _ProfileSpec:
    agent_id: str
    domains: tuple[MemoryIntelligenceDomain, ...]
    primary_domains: tuple[MemoryIntelligenceDomain, ...]
    signals: tuple[str, ...]


_PROFILE_SPECS = (
    _ProfileSpec(
        'memory.chief',
        (
            MemoryIntelligenceDomain.CROSS_MEMORY,
            MemoryIntelligenceDomain.LIFECYCLE,
            MemoryIntelligenceDomain.KNOWLEDGE_GRAPH,
            MemoryIntelligenceDomain.CONTEXT_COMPILATION,
        ),
        (MemoryIntelligenceDomain.CROSS_MEMORY,),
        ('repair', 'cross-memory', 'conflict', 'continuity', 'arbitration'),
    ),
    _ProfileSpec(
        'memory.context-compiler.01',
        (MemoryIntelligenceDomain.CONTEXT_COMPILATION,),
        (MemoryIntelligenceDomain.CONTEXT_COMPILATION,),
        ('context', 'delta', 'checkpoint', 'resume', 'overload', 'budget'),
    ),
    _ProfileSpec(
        'memory.knowledge-graph.01',
        (MemoryIntelligenceDomain.KNOWLEDGE_GRAPH,),
        (MemoryIntelligenceDomain.KNOWLEDGE_GRAPH,),
        ('graph', 'relation', 'contradiction', 'provenance', 'dependency'),
    ),
    _ProfileSpec(
        'memory.lifecycle.01',
        (MemoryIntelligenceDomain.LIFECYCLE,),
        (MemoryIntelligenceDomain.LIFECYCLE,),
        ('lifecycle', 'quarantine', 'archive', 'supersede', 'consolidate'),
    ),
)
_SPEC_BY_ID = {row.agent_id: row for row in _PROFILE_SPECS}


@dataclass(frozen=True, slots=True)
class MemoryIntelligenceProfile:
    agent_id: str
    region: str
    domains: tuple[MemoryIntelligenceDomain, ...]
    primary_domains: tuple[MemoryIntelligenceDomain, ...]
    signals: tuple[str, ...]
    preferred_external_cores: tuple[str, ...]
    accepted_neural_version: str

    def to_state(self) -> dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'region': self.region,
            'domains': [row.value for row in self.domains],
            'primary_domains': [row.value for row in self.primary_domains],
            'signals': list(self.signals),
            'preferred_external_cores': list(self.preferred_external_cores),
            'accepted_neural_version': self.accepted_neural_version,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'MemoryIntelligenceProfile':
        return cls(
            agent_id=str(state['agent_id']),
            region=str(state['region']),
            domains=tuple(MemoryIntelligenceDomain(str(row)) for row in state.get('domains', ())),
            primary_domains=tuple(MemoryIntelligenceDomain(str(row)) for row in state.get('primary_domains', ())),
            signals=tuple(str(row) for row in state.get('signals', ())),
            preferred_external_cores=tuple(str(row) for row in state.get('preferred_external_cores', ())),
            accepted_neural_version=str(state['accepted_neural_version']),
        )


@dataclass(frozen=True, slots=True)
class MemoryWorkRequest:
    work_id: str
    object_id: str
    requested_domains: tuple[MemoryIntelligenceDomain, ...]
    scope_hints: tuple[str, ...]
    priority: int
    requester_agent_id: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all(str(value).strip() for value in (self.work_id, self.object_id, self.requester_agent_id)):
            raise ValueError('memory intelligence work id, object and requester must be explicit')
        if not self.requested_domains:
            raise ValueError('memory intelligence work requires at least one requested domain')
        if not self.evidence_refs:
            raise ValueError('memory intelligence work requires evidence refs')
        if not 0 <= int(self.priority) <= 100:
            raise ValueError('memory intelligence work priority must be in [0,100]')

    def to_state(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id,
            'object_id': self.object_id,
            'requested_domains': [row.value for row in self.requested_domains],
            'scope_hints': list(self.scope_hints),
            'priority': int(self.priority),
            'requester_agent_id': self.requester_agent_id,
            'evidence_refs': list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class MemoryCandidateScore:
    agent_id: str
    score: int
    reasons: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {'agent_id': self.agent_id, 'score': self.score, 'reasons': list(self.reasons)}


@dataclass(frozen=True, slots=True)
class MemoryAssignmentReceipt:
    work_id: str
    selected_agent_id: str
    ranked_candidates: tuple[MemoryCandidateScore, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id,
            'selected_agent_id': self.selected_agent_id,
            'ranked_candidates': [row.to_state() for row in self.ranked_candidates],
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}


class MemoryIntelligenceProfileRegistry:
    REGION = 'memory-context-knowledge'

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        actual = {
            row.agent_id for row in registry.identities()
            if row.region == self.REGION
        }
        if actual != set(_SPEC_BY_ID):
            raise ValueError('memory intelligence profile registry requires exact four Memory/Context identities')

    def _profile(self, spec: _ProfileSpec) -> MemoryIntelligenceProfile:
        identity = self.registry.get(spec.agent_id)
        if identity.region != self.REGION:
            raise ValueError(f'memory intelligence identity region mismatch: {spec.agent_id}')
        return MemoryIntelligenceProfile(
            agent_id=identity.agent_id,
            region=identity.region,
            domains=spec.domains,
            primary_domains=spec.primary_domains,
            signals=spec.signals,
            preferred_external_cores=identity.external_core_bindings,
            accepted_neural_version=identity.neural_version,
        )

    def profiles(self) -> tuple[MemoryIntelligenceProfile, ...]:
        return tuple(self._profile(spec) for spec in _PROFILE_SPECS)

    def get(self, agent_id: str) -> MemoryIntelligenceProfile:
        try:
            return self._profile(_SPEC_BY_ID[str(agent_id)])
        except KeyError as exc:
            raise KeyError(f'unknown memory intelligence profile: {agent_id}') from exc

    def _score(self, profile: MemoryIntelligenceProfile, request: MemoryWorkRequest) -> MemoryCandidateScore:
        score = 0
        reasons: list[str] = []
        for domain in request.requested_domains:
            if domain in profile.primary_domains:
                score += 1000
                reasons.append(f'primary:{domain.value}')
            elif domain in profile.domains:
                score += 100
                reasons.append(f'domain:{domain.value}')
        signals = set(profile.signals)
        for hint in sorted({str(value).strip().lower() for value in request.scope_hints if str(value).strip()}):
            if hint in signals:
                score += 10
                reasons.append(f'signal:{hint}')
        if self.registry.get(profile.agent_id).current_task is None:
            score += 1
            reasons.append('available')
        return MemoryCandidateScore(profile.agent_id, score, tuple(reasons))

    def route(self, request: MemoryWorkRequest) -> MemoryAssignmentReceipt:
        self.registry.get(request.requester_agent_id)
        ranked = tuple(sorted(
            (self._score(profile, request) for profile in self.profiles()),
            key=lambda row: (-row.score, row.agent_id),
        ))
        if not ranked or ranked[0].score <= 1:
            raise ValueError('no Memory/Context profile covers requested domains')
        payload = {
            'work_id': request.work_id,
            'selected_agent_id': ranked[0].agent_id,
            'ranked_candidates': [row.to_state() for row in ranked],
        }
        return MemoryAssignmentReceipt(
            work_id=request.work_id,
            selected_agent_id=ranked[0].agent_id,
            ranked_candidates=ranked,
            digest=canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {'profiles': [row.to_state() for row in self.profiles()]}

    @classmethod
    def from_state(cls, registry: AgentRegistry, state: Mapping[str, Any]) -> 'MemoryIntelligenceProfileRegistry':
        result = cls(registry)
        supplied = tuple(MemoryIntelligenceProfile.from_state(row) for row in state.get('profiles', ()))
        if supplied and supplied != result.profiles():
            raise ValueError('serialized Memory/Context profiles do not match current registry identities')
        return result
