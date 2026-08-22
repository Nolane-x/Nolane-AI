from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .registry import AgentRegistry
from .types import canonical_digest


class DebugDomain(str, Enum):
    CROSS_FAILURE = 'cross_failure'
    REPRODUCTION = 'reproduction'
    RUNTIME_TRACE = 'runtime_trace'
    STATIC_ROOT_CAUSE = 'static_root_cause'
    CONCURRENCY_STATE = 'concurrency_state'
    REGRESSION_BISECT = 'regression_bisect'


_PROFILE_CONFIG: dict[str, tuple[tuple[DebugDomain, ...], tuple[str, ...]]] = {
    'debug.chief': ((DebugDomain.CROSS_FAILURE,), ('cross-failure', 'mixed', 'systemic', 'coordination')),
    'debug.reproducer.01': ((DebugDomain.REPRODUCTION,), ('reproduce', 'minimize', 'deterministic', 'fixture')),
    'debug.runtime-trace.01': ((DebugDomain.RUNTIME_TRACE,), ('trace', 'stack', 'coverage', 'timeline')),
    'debug.static-root-cause.01': ((DebugDomain.STATIC_ROOT_CAUSE,), ('static', 'data-flow', 'control-flow', 'source')),
    'debug.concurrency-state.01': ((DebugDomain.CONCURRENCY_STATE,), ('race', 'deadlock', 'concurrency', 'state')),
    'debug.regression-bisect.01': ((DebugDomain.REGRESSION_BISECT,), ('regression', 'bisect', 'history', 'commit')),
}


@dataclass(frozen=True, slots=True)
class DebugProfile:
    agent_id: str
    domains: tuple[DebugDomain, ...]
    preferred_external_cores: tuple[str, ...]
    signals: tuple[str, ...]
    accepted_neural_version: str

    def to_state(self) -> dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'domains': [x.value for x in self.domains],
            'preferred_external_cores': list(self.preferred_external_cores),
            'signals': list(self.signals),
            'accepted_neural_version': self.accepted_neural_version,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'DebugProfile':
        return cls(
            agent_id=str(state['agent_id']),
            domains=tuple(DebugDomain(str(x)) for x in state.get('domains', ())),
            preferred_external_cores=tuple(str(x) for x in state.get('preferred_external_cores', ())),
            signals=tuple(str(x) for x in state.get('signals', ())),
            accepted_neural_version=str(state['accepted_neural_version']),
        )


@dataclass(frozen=True, slots=True)
class DebugWorkRequest:
    work_id: str
    case_id: str
    task_id: str
    requested_domains: tuple[DebugDomain, ...]
    scope_hints: tuple[str, ...]
    priority: int
    requester_agent_id: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.work_id, self.case_id, self.task_id, self.requester_agent_id)):
            raise ValueError('debug work identity/case/task/requester must be explicit')
        if not self.requested_domains or not self.evidence_refs:
            raise ValueError('debug work requires domain and evidence')
        if not 0 <= int(self.priority) <= 100:
            raise ValueError('debug work priority must be in [0,100]')

    def to_state(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id, 'case_id': self.case_id, 'task_id': self.task_id,
            'requested_domains': [x.value for x in self.requested_domains],
            'scope_hints': list(self.scope_hints), 'priority': self.priority,
            'requester_agent_id': self.requester_agent_id, 'evidence_refs': list(self.evidence_refs),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'DebugWorkRequest':
        return cls(
            work_id=str(state['work_id']), case_id=str(state['case_id']), task_id=str(state['task_id']),
            requested_domains=tuple(DebugDomain(str(x)) for x in state.get('requested_domains', ())),
            scope_hints=tuple(str(x) for x in state.get('scope_hints', ())),
            priority=int(state.get('priority', 0)), requester_agent_id=str(state['requester_agent_id']),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
        )


@dataclass(frozen=True, slots=True)
class DebugCandidateScore:
    agent_id: str
    score: int
    reasons: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {'agent_id': self.agent_id, 'score': self.score, 'reasons': list(self.reasons)}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'DebugCandidateScore':
        return cls(str(state['agent_id']), int(state['score']), tuple(str(x) for x in state.get('reasons', ())))


@dataclass(frozen=True, slots=True)
class DebugAssignmentReceipt:
    work_id: str
    case_id: str
    selected_agent_id: str
    ranked_candidates: tuple[DebugCandidateScore, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id, 'case_id': self.case_id, 'selected_agent_id': self.selected_agent_id,
            'ranked_candidates': [x.to_state() for x in self.ranked_candidates],
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'DebugAssignmentReceipt':
        row = cls(
            work_id=str(state['work_id']), case_id=str(state['case_id']), selected_agent_id=str(state['selected_agent_id']),
            ranked_candidates=tuple(DebugCandidateScore.from_state(x) for x in state.get('ranked_candidates', ())),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('debug assignment digest mismatch')
        return row


class DebugProfileRegistry:
    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        self._profiles: dict[str, DebugProfile] = {}
        for identity in registry.identities():
            config = _PROFILE_CONFIG.get(identity.agent_id)
            if identity.region != 'debugging-failure' or config is None:
                continue
            domains, signals = config
            self._profiles[identity.agent_id] = DebugProfile(
                identity.agent_id, domains, identity.external_core_bindings, signals, identity.neural_version,
            )
        if set(self._profiles) != set(_PROFILE_CONFIG):
            raise ValueError('debug profile registry requires exact six permanent debugging identities')

    def profiles(self) -> tuple[DebugProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))

    def get(self, agent_id: str) -> DebugProfile:
        try:
            return self._profiles[str(agent_id)]
        except KeyError as exc:
            raise KeyError(f'unknown debug profile: {agent_id}') from exc

    def _score(self, profile: DebugProfile, request: DebugWorkRequest) -> DebugCandidateScore:
        score = 0
        reasons: list[str] = []
        for domain in request.requested_domains:
            if domain in profile.domains:
                score += 100
                reasons.append(f'domain:{domain.value}')
        signals = set(profile.signals)
        for hint in sorted({str(x).strip().lower() for x in request.scope_hints if str(x).strip()}):
            if hint in signals:
                score += 10
                reasons.append(f'signal:{hint}')
        if self.registry.get(profile.agent_id).current_task is None:
            score += 1
            reasons.append('available')
        return DebugCandidateScore(profile.agent_id, score, tuple(reasons))

    def route(self, request: DebugWorkRequest) -> DebugAssignmentReceipt:
        ranked = tuple(sorted((self._score(row, request) for row in self.profiles()), key=lambda x: (-x.score, x.agent_id)))
        if not ranked:
            raise ValueError('no debug profiles available')
        payload = {
            'work_id': request.work_id, 'case_id': request.case_id,
            'selected_agent_id': ranked[0].agent_id,
            'ranked_candidates': [x.to_state() for x in ranked],
        }
        return DebugAssignmentReceipt(
            request.work_id, request.case_id, ranked[0].agent_id, ranked, canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {'profiles': [x.to_state() for x in self.profiles()]}

    @classmethod
    def from_state(cls, registry: AgentRegistry, state: Mapping[str, Any]) -> 'DebugProfileRegistry':
        result = cls(registry)
        supplied = tuple(DebugProfile.from_state(x) for x in state.get('profiles', ()))
        if supplied and supplied != result.profiles():
            raise ValueError('serialized debug profiles do not match accepted registry identities')
        return result
