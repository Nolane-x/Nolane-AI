from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.organization.identity import AgentRegistry
from nolane.core.canonical_digest import canonical_digest


class OperationsDomain(str, Enum):
    SCHEMA_MIGRATION = 'schema_migration'
    PERSISTENCE = 'persistence'
    CACHE_CONSISTENCY = 'cache_consistency'
    CROSS_DATA = 'cross_data'
    CI_ENVIRONMENT = 'ci_environment'
    DEPLOYMENT = 'deployment'
    OBSERVABILITY_RELEASE = 'observability_release'
    CROSS_INFRASTRUCTURE = 'cross_infrastructure'
    PERFORMANCE = 'performance'
    CONCURRENCY = 'concurrency'
    RECOVERY = 'recovery'
    CROSS_RELIABILITY = 'cross_reliability'


@dataclass(frozen=True, slots=True)
class _ProfileSpec:
    agent_id: str
    region: str
    domains: tuple[OperationsDomain, ...]
    primary_domains: tuple[OperationsDomain, ...]
    signals: tuple[str, ...]


_PROFILE_SPECS = (
    _ProfileSpec('data.chief', 'data-storage-migration',
                 (OperationsDomain.CROSS_DATA, OperationsDomain.SCHEMA_MIGRATION, OperationsDomain.PERSISTENCE, OperationsDomain.CACHE_CONSISTENCY),
                 (OperationsDomain.CROSS_DATA,), ('cross-data', 'schema', 'storage', 'consistency')),
    _ProfileSpec('data.schema-migration.01', 'data-storage-migration',
                 (OperationsDomain.SCHEMA_MIGRATION,), (OperationsDomain.SCHEMA_MIGRATION,), ('schema', 'migration', 'rollback', 'compatibility')),
    _ProfileSpec('data.persistence.01', 'data-storage-migration',
                 (OperationsDomain.PERSISTENCE,), (OperationsDomain.PERSISTENCE,), ('transaction', 'durability', 'persistence', 'storage')),
    _ProfileSpec('data.cache-consistency.01', 'data-storage-migration',
                 (OperationsDomain.CACHE_CONSISTENCY,), (OperationsDomain.CACHE_CONSISTENCY,), ('cache', 'consistency', 'coherence', 'invalidation')),
    _ProfileSpec('infrastructure.chief', 'infrastructure-release',
                 (OperationsDomain.CROSS_INFRASTRUCTURE, OperationsDomain.CI_ENVIRONMENT, OperationsDomain.DEPLOYMENT, OperationsDomain.OBSERVABILITY_RELEASE),
                 (OperationsDomain.CROSS_INFRASTRUCTURE,), ('cross-infra', 'ci', 'deploy', 'observability')),
    _ProfileSpec('infrastructure.ci-env.01', 'infrastructure-release',
                 (OperationsDomain.CI_ENVIRONMENT,), (OperationsDomain.CI_ENVIRONMENT,), ('ci', 'environment', 'toolchain', 'build')),
    _ProfileSpec('infrastructure.deployment.01', 'infrastructure-release',
                 (OperationsDomain.DEPLOYMENT,), (OperationsDomain.DEPLOYMENT,), ('deploy', 'rollout', 'rollback', 'topology')),
    _ProfileSpec('infrastructure.observability-release.01', 'infrastructure-release',
                 (OperationsDomain.OBSERVABILITY_RELEASE,), (OperationsDomain.OBSERVABILITY_RELEASE,), ('observability', 'release', 'logs', 'metrics', 'traces')),
    _ProfileSpec('reliability.chief', 'performance-reliability',
                 (OperationsDomain.CROSS_RELIABILITY, OperationsDomain.PERFORMANCE, OperationsDomain.CONCURRENCY, OperationsDomain.RECOVERY),
                 (OperationsDomain.CROSS_RELIABILITY,), ('cross-reliability', 'profile', 'ordering', 'recovery')),
    _ProfileSpec('reliability.performance.01', 'performance-reliability',
                 (OperationsDomain.PERFORMANCE,), (OperationsDomain.PERFORMANCE,), ('profile', 'performance', 'latency', 'resource')),
    _ProfileSpec('reliability.concurrency.01', 'performance-reliability',
                 (OperationsDomain.CONCURRENCY,), (OperationsDomain.CONCURRENCY,), ('ordering', 'concurrency', 'duplicate', 'race')),
    _ProfileSpec('reliability.recovery.01', 'performance-reliability',
                 (OperationsDomain.RECOVERY,), (OperationsDomain.RECOVERY,), ('recovery', 'retry', 'idempotency', 'checkpoint')),
)
_SPEC_BY_ID = {row.agent_id: row for row in _PROFILE_SPECS}


@dataclass(frozen=True, slots=True)
class OperationsProfile:
    agent_id: str
    region: str
    domains: tuple[OperationsDomain, ...]
    primary_domains: tuple[OperationsDomain, ...]
    signals: tuple[str, ...]
    preferred_external_cores: tuple[str, ...]
    accepted_neural_version: str

    def to_state(self) -> dict[str, Any]:
        return {
            'agent_id': self.agent_id, 'region': self.region,
            'domains': [x.value for x in self.domains],
            'primary_domains': [x.value for x in self.primary_domains],
            'signals': list(self.signals), 'preferred_external_cores': list(self.preferred_external_cores),
            'accepted_neural_version': self.accepted_neural_version,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'OperationsProfile':
        return cls(
            agent_id=str(state['agent_id']), region=str(state['region']),
            domains=tuple(OperationsDomain(str(x)) for x in state.get('domains', ())),
            primary_domains=tuple(OperationsDomain(str(x)) for x in state.get('primary_domains', ())),
            signals=tuple(str(x) for x in state.get('signals', ())),
            preferred_external_cores=tuple(str(x) for x in state.get('preferred_external_cores', ())),
            accepted_neural_version=str(state['accepted_neural_version']),
        )


@dataclass(frozen=True, slots=True)
class OperationsWorkRequest:
    work_id: str
    object_id: str
    requested_domains: tuple[OperationsDomain, ...]
    scope_hints: tuple[str, ...]
    priority: int
    requester_agent_id: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.work_id, self.object_id, self.requester_agent_id)):
            raise ValueError('operations work id, object and requester must be explicit')
        if not self.requested_domains or not self.evidence_refs:
            raise ValueError('operations work requires domains and evidence')
        if not 0 <= int(self.priority) <= 100:
            raise ValueError('operations work priority must be in [0,100]')

    def to_state(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id, 'object_id': self.object_id,
            'requested_domains': [x.value for x in self.requested_domains],
            'scope_hints': list(self.scope_hints), 'priority': self.priority,
            'requester_agent_id': self.requester_agent_id, 'evidence_refs': list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class OperationsCandidateScore:
    agent_id: str
    score: int
    reasons: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {'agent_id': self.agent_id, 'score': self.score, 'reasons': list(self.reasons)}


@dataclass(frozen=True, slots=True)
class OperationsAssignmentReceipt:
    work_id: str
    selected_agent_id: str
    ranked_candidates: tuple[OperationsCandidateScore, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {'work_id': self.work_id, 'selected_agent_id': self.selected_agent_id,
                'ranked_candidates': [x.to_state() for x in self.ranked_candidates]}

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}


class OperationsProfileRegistry:
    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        actual = {row.agent_id for row in registry.identities() if row.region in {
            'data-storage-migration', 'infrastructure-release', 'performance-reliability'
        }}
        if actual != set(_SPEC_BY_ID):
            raise ValueError('operations profile registry requires exact twelve operational identities')

    def _profile(self, spec: _ProfileSpec) -> OperationsProfile:
        identity = self.registry.get(spec.agent_id)
        if identity.region != spec.region:
            raise ValueError(f'operations identity region mismatch: {spec.agent_id}')
        return OperationsProfile(
            agent_id=spec.agent_id, region=spec.region, domains=spec.domains,
            primary_domains=spec.primary_domains, signals=spec.signals,
            preferred_external_cores=identity.external_core_bindings,
            accepted_neural_version=identity.neural_version,
        )

    def profiles(self) -> tuple[OperationsProfile, ...]:
        return tuple(self._profile(spec) for spec in _PROFILE_SPECS)

    def get(self, agent_id: str) -> OperationsProfile:
        try:
            return self._profile(_SPEC_BY_ID[str(agent_id)])
        except KeyError as exc:
            raise KeyError(f'unknown operations profile: {agent_id}') from exc

    def _score(self, profile: OperationsProfile, request: OperationsWorkRequest) -> OperationsCandidateScore:
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
        for hint in sorted({str(x).strip().lower() for x in request.scope_hints if str(x).strip()}):
            if hint in signals:
                score += 10
                reasons.append(f'signal:{hint}')
        if self.registry.get(profile.agent_id).current_task is None:
            score += 1
            reasons.append('available')
        return OperationsCandidateScore(profile.agent_id, score, tuple(reasons))

    def route(self, request: OperationsWorkRequest) -> OperationsAssignmentReceipt:
        self.registry.get(request.requester_agent_id)
        ranked = tuple(sorted((self._score(profile, request) for profile in self.profiles()), key=lambda x: (-x.score, x.agent_id)))
        if not ranked or ranked[0].score <= 1:
            raise ValueError('no operations profile covers requested domains')
        payload = {'work_id': request.work_id, 'selected_agent_id': ranked[0].agent_id,
                   'ranked_candidates': [x.to_state() for x in ranked]}
        return OperationsAssignmentReceipt(request.work_id, ranked[0].agent_id, ranked, canonical_digest(payload))

    def to_state(self) -> dict[str, Any]:
        return {'profiles': [row.to_state() for row in self.profiles()]}

    @classmethod
    def from_state(cls, registry: AgentRegistry, state: Mapping[str, Any]) -> 'OperationsProfileRegistry':
        result = cls(registry)
        supplied = tuple(OperationsProfile.from_state(x) for x in state.get('profiles', ()))
        if supplied and supplied != result.profiles():
            raise ValueError('serialized operations profiles do not match current registry identities')
        return result
