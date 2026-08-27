from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.organization.identity import AgentRegistry


class CodingDomain(str, Enum):
    CROSS_SYSTEM = 'cross_system'
    ALGORITHM = 'algorithm'
    BACKEND = 'backend'
    SYSTEMS = 'systems'
    REFACTOR = 'refactor'
    API = 'api'
    BUILD_DEPENDENCY = 'build_dependency'


_PROFILE_CONFIG: dict[str, tuple[tuple[CodingDomain, ...], tuple[str, ...]]] = {
    'coding.chief': ((CodingDomain.CROSS_SYSTEM,), ('cross-system', 'integration', 'architecture-aware')),
    'coding.core-algorithm.01': ((CodingDomain.ALGORITHM,), ('algorithm', 'data-structure', 'numerical', 'formal')),
    'coding.backend.01': ((CodingDomain.BACKEND,), ('backend', 'service', 'api', 'persistence')),
    'coding.systems.01': ((CodingDomain.SYSTEMS,), ('systems', 'runtime', 'concurrency', 'low-level', 'performance')),
    'coding.refactor.01': ((CodingDomain.REFACTOR,), ('refactor', 'migration', 'cross-file', 'behavior-preserving')),
    'coding.api-interface.01': ((CodingDomain.API,), ('api', 'interface', 'schema', 'compatibility')),
    'coding.build-dependency.01': ((CodingDomain.BUILD_DEPENDENCY,), ('build', 'dependency', 'packaging', 'toolchain')),
}


@dataclass(frozen=True, slots=True)
class CodingProfile:
    agent_id: str
    domains: tuple[CodingDomain, ...]
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
    def from_state(cls, state: Mapping[str, Any]) -> 'CodingProfile':
        return cls(
            agent_id=str(state['agent_id']),
            domains=tuple(CodingDomain(str(x)) for x in state.get('domains', ())),
            preferred_external_cores=tuple(str(x) for x in state.get('preferred_external_cores', ())),
            signals=tuple(str(x) for x in state.get('signals', ())),
            accepted_neural_version=str(state['accepted_neural_version']),
        )


@dataclass(frozen=True, slots=True)
class CodingWorkRequest:
    work_id: str
    task_id: str
    plan_node_id: str
    requirement_refs: tuple[str, ...]
    architecture_version: int
    plan_version: int
    requested_domains: tuple[CodingDomain, ...]
    scope_hints: tuple[str, ...]
    acceptance_refs: tuple[str, ...]
    priority: int
    requester_agent_id: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.work_id, self.task_id, self.plan_node_id, self.requester_agent_id)):
            raise ValueError('coding work identity/task/plan/requester must be explicit')
        if self.architecture_version < 0 or self.plan_version < 0:
            raise ValueError('coding work authoritative versions must be non-negative')
        if not 0 <= int(self.priority) <= 100:
            raise ValueError('coding work priority must be in [0,100]')
        if not self.requested_domains or not self.evidence_refs:
            raise ValueError('coding work requires domains and evidence')

    def to_state(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id,
            'task_id': self.task_id,
            'plan_node_id': self.plan_node_id,
            'requirement_refs': list(self.requirement_refs),
            'architecture_version': self.architecture_version,
            'plan_version': self.plan_version,
            'requested_domains': [x.value for x in self.requested_domains],
            'scope_hints': list(self.scope_hints),
            'acceptance_refs': list(self.acceptance_refs),
            'priority': self.priority,
            'requester_agent_id': self.requester_agent_id,
            'evidence_refs': list(self.evidence_refs),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CodingWorkRequest':
        return cls(
            work_id=str(state['work_id']),
            task_id=str(state['task_id']),
            plan_node_id=str(state['plan_node_id']),
            requirement_refs=tuple(str(x) for x in state.get('requirement_refs', ())),
            architecture_version=int(state.get('architecture_version', 0)),
            plan_version=int(state.get('plan_version', 0)),
            requested_domains=tuple(CodingDomain(str(x)) for x in state.get('requested_domains', ())),
            scope_hints=tuple(str(x) for x in state.get('scope_hints', ())),
            acceptance_refs=tuple(str(x) for x in state.get('acceptance_refs', ())),
            priority=int(state.get('priority', 0)),
            requester_agent_id=str(state['requester_agent_id']),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
        )


@dataclass(frozen=True, slots=True)
class CodingCandidateScore:
    agent_id: str
    score: int
    reasons: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {'agent_id': self.agent_id, 'score': self.score, 'reasons': list(self.reasons)}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CodingCandidateScore':
        return cls(str(state['agent_id']), int(state['score']), tuple(str(x) for x in state.get('reasons', ())))


@dataclass(frozen=True, slots=True)
class CodingAssignmentReceipt:
    work_id: str
    selected_agent_id: str
    ranked_candidates: tuple[CodingCandidateScore, ...]
    architecture_version: int
    plan_version: int
    override_actor_id: str | None
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id,
            'selected_agent_id': self.selected_agent_id,
            'ranked_candidates': [x.to_state() for x in self.ranked_candidates],
            'architecture_version': self.architecture_version,
            'plan_version': self.plan_version,
            'override_actor_id': self.override_actor_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CodingAssignmentReceipt':
        row = cls(
            work_id=str(state['work_id']),
            selected_agent_id=str(state['selected_agent_id']),
            ranked_candidates=tuple(CodingCandidateScore.from_state(x) for x in state.get('ranked_candidates', ())),
            architecture_version=int(state['architecture_version']),
            plan_version=int(state['plan_version']),
            override_actor_id=None if state.get('override_actor_id') is None else str(state['override_actor_id']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('coding assignment receipt digest mismatch')
        return row


class CodingProfileRegistry:
    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        self._profiles: dict[str, CodingProfile] = {}
        for identity in registry.identities():
            config = _PROFILE_CONFIG.get(identity.agent_id)
            if identity.region != 'core-coding' or config is None:
                continue
            domains, signals = config
            self._profiles[identity.agent_id] = CodingProfile(
                agent_id=identity.agent_id,
                domains=domains,
                preferred_external_cores=identity.external_core_bindings,
                signals=signals,
                accepted_neural_version=identity.neural_version,
            )
        if set(self._profiles) != set(_PROFILE_CONFIG):
            raise ValueError('coding profile registry requires the exact seven permanent coding identities')

    def profiles(self) -> tuple[CodingProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))

    def get(self, agent_id: str) -> CodingProfile:
        try:
            return self._profiles[str(agent_id)]
        except KeyError as exc:
            raise KeyError(f'unknown coding profile: {agent_id}') from exc

    def _score(self, profile: CodingProfile, request: CodingWorkRequest) -> CodingCandidateScore:
        score = 0
        reasons: list[str] = []
        for domain in request.requested_domains:
            if domain in profile.domains:
                score += 100
                reasons.append(f'domain:{domain.value}')
        profile_signals = set(profile.signals)
        for hint in sorted({str(x).strip().lower() for x in request.scope_hints if str(x).strip()}):
            if hint in profile_signals:
                score += 10
                reasons.append(f'signal:{hint}')
        identity = self.registry.get(profile.agent_id)
        if identity.current_task is None:
            score += 1
            reasons.append('available')
        return CodingCandidateScore(profile.agent_id, score, tuple(reasons))

    def route(
        self,
        request: CodingWorkRequest,
        *,
        override_agent_id: str | None = None,
        override_actor_id: str | None = None,
    ) -> CodingAssignmentReceipt:
        ranked = tuple(sorted(
            (self._score(profile, request) for profile in self.profiles()),
            key=lambda row: (-row.score, row.agent_id),
        ))
        if not ranked:
            raise ValueError('no coding profiles are available')
        selected = ranked[0].agent_id
        actor = None
        if override_agent_id is not None:
            self.get(override_agent_id)
            if override_actor_id not in {'coding.chief', 'nolane.central'}:
                raise PermissionError('coding routing override requires Coding Chief or Nolane Central')
            selected = str(override_agent_id)
            actor = str(override_actor_id)
        payload = {
            'work_id': request.work_id,
            'selected_agent_id': selected,
            'ranked_candidates': [x.to_state() for x in ranked],
            'architecture_version': request.architecture_version,
            'plan_version': request.plan_version,
            'override_actor_id': actor,
        }
        return CodingAssignmentReceipt(
            work_id=request.work_id,
            selected_agent_id=selected,
            ranked_candidates=ranked,
            architecture_version=request.architecture_version,
            plan_version=request.plan_version,
            override_actor_id=actor,
            digest=canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {'profiles': [row.to_state() for row in self.profiles()]}

    @classmethod
    def from_state(cls, registry: AgentRegistry, state: Mapping[str, Any]) -> 'CodingProfileRegistry':
        result = cls(registry)
        supplied = tuple(CodingProfile.from_state(x) for x in state.get('profiles', ()))
        if supplied and supplied != result.profiles():
            raise ValueError('serialized coding profiles do not match accepted registry identities')
        return result


__all__ = (
    'CodingDomain',
    'CodingProfile',
    'CodingWorkRequest',
    'CodingCandidateScore',
    'CodingAssignmentReceipt',
    'CodingProfileRegistry',
)
