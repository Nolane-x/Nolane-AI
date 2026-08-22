from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .registry import AgentRegistry
from .types import canonical_digest


class AssuranceDomain(str, Enum):
    UNIT_PROPERTY = 'unit_property'
    INTEGRATION_E2E = 'integration_e2e'
    SPEC_ACCEPTANCE = 'spec_acceptance'
    FUZZ_REGRESSION = 'fuzz_regression'
    THREAT_MODEL = 'threat_model'
    SUPPLY_CHAIN = 'supply_chain'
    ADVERSARIAL = 'adversarial'
    CROSS_VERIFICATION = 'cross_verification'
    CROSS_SECURITY = 'cross_security'


@dataclass(frozen=True, slots=True)
class _ProfileSpec:
    agent_id: str
    region: str
    domains: tuple[AssuranceDomain, ...]
    primary_domains: tuple[AssuranceDomain, ...]
    signals: tuple[str, ...]


_PROFILE_SPECS = (
    _ProfileSpec(
        'verification.chief', 'verification-testing',
        (
            AssuranceDomain.CROSS_VERIFICATION, AssuranceDomain.UNIT_PROPERTY,
            AssuranceDomain.INTEGRATION_E2E, AssuranceDomain.SPEC_ACCEPTANCE,
            AssuranceDomain.FUZZ_REGRESSION,
        ),
        (AssuranceDomain.CROSS_VERIFICATION,),
        ('cross-domain', 'arbitration', 'falsification', 'acceptance'),
    ),
    _ProfileSpec(
        'verification.unit-property.01', 'verification-testing',
        (AssuranceDomain.UNIT_PROPERTY,), (AssuranceDomain.UNIT_PROPERTY,),
        ('unit', 'property', 'invariant', 'deterministic'),
    ),
    _ProfileSpec(
        'verification.integration-e2e.01', 'verification-testing',
        (AssuranceDomain.INTEGRATION_E2E,), (AssuranceDomain.INTEGRATION_E2E,),
        ('integration', 'e2e', 'end-to-end', 'subsystem'),
    ),
    _ProfileSpec(
        'verification.spec-acceptance.01', 'verification-testing',
        (AssuranceDomain.SPEC_ACCEPTANCE,), (AssuranceDomain.SPEC_ACCEPTANCE,),
        ('spec', 'acceptance', 'requirement', 'contract'),
    ),
    _ProfileSpec(
        'verification.fuzz-regression.01', 'verification-testing',
        (AssuranceDomain.FUZZ_REGRESSION,), (AssuranceDomain.FUZZ_REGRESSION,),
        ('fuzz', 'regression', 'mutation', 'counterexample'),
    ),
    _ProfileSpec(
        'security.chief', 'security-adversarial',
        (
            AssuranceDomain.CROSS_SECURITY, AssuranceDomain.THREAT_MODEL,
            AssuranceDomain.SUPPLY_CHAIN, AssuranceDomain.ADVERSARIAL,
        ),
        (AssuranceDomain.CROSS_SECURITY,),
        ('cross-threat', 'security-arbitration', 'adversarial', 'threat'),
    ),
    _ProfileSpec(
        'security.threat-model.01', 'security-adversarial',
        (AssuranceDomain.THREAT_MODEL,), (AssuranceDomain.THREAT_MODEL,),
        ('threat', 'trust-boundary', 'asset', 'abuse-case'),
    ),
    _ProfileSpec(
        'security.supply-chain.01', 'security-adversarial',
        (AssuranceDomain.SUPPLY_CHAIN,), (AssuranceDomain.SUPPLY_CHAIN,),
        ('dependency', 'supply-chain', 'package', 'provenance'),
    ),
    _ProfileSpec(
        'security.adversarial.01', 'security-adversarial',
        (AssuranceDomain.ADVERSARIAL,), (AssuranceDomain.ADVERSARIAL,),
        ('attack', 'exploit', 'adversarial', 'malformed-state'),
    ),
)

_SPEC_BY_ID = {row.agent_id: row for row in _PROFILE_SPECS}


@dataclass(frozen=True, slots=True)
class AssuranceProfile:
    agent_id: str
    region: str
    domains: tuple[AssuranceDomain, ...]
    primary_domains: tuple[AssuranceDomain, ...]
    signals: tuple[str, ...]
    preferred_external_cores: tuple[str, ...]
    accepted_neural_version: str

    def to_state(self) -> dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'region': self.region,
            'domains': [x.value for x in self.domains],
            'primary_domains': [x.value for x in self.primary_domains],
            'signals': list(self.signals),
            'preferred_external_cores': list(self.preferred_external_cores),
            'accepted_neural_version': self.accepted_neural_version,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'AssuranceProfile':
        return cls(
            agent_id=str(state['agent_id']),
            region=str(state['region']),
            domains=tuple(AssuranceDomain(str(x)) for x in state.get('domains', ())),
            primary_domains=tuple(AssuranceDomain(str(x)) for x in state.get('primary_domains', ())),
            signals=tuple(str(x) for x in state.get('signals', ())),
            preferred_external_cores=tuple(str(x) for x in state.get('preferred_external_cores', ())),
            accepted_neural_version=str(state['accepted_neural_version']),
        )


@dataclass(frozen=True, slots=True)
class AssuranceWorkRequest:
    work_id: str
    subject_id: str
    requested_domains: tuple[AssuranceDomain, ...]
    scope_hints: tuple[str, ...]
    priority: int
    requester_agent_id: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.work_id, self.subject_id, self.requester_agent_id)):
            raise ValueError('assurance work id, subject and requester must be explicit')
        if not self.requested_domains:
            raise ValueError('assurance work requires at least one requested domain')
        if not self.evidence_refs:
            raise ValueError('assurance work requires evidence refs')
        if not 0 <= int(self.priority) <= 100:
            raise ValueError('assurance work priority must be in [0,100]')

    def to_state(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id,
            'subject_id': self.subject_id,
            'requested_domains': [x.value for x in self.requested_domains],
            'scope_hints': list(self.scope_hints),
            'priority': self.priority,
            'requester_agent_id': self.requester_agent_id,
            'evidence_refs': list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class AssuranceCandidateScore:
    agent_id: str
    score: int
    reasons: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {'agent_id': self.agent_id, 'score': self.score, 'reasons': list(self.reasons)}


@dataclass(frozen=True, slots=True)
class AssuranceAssignmentReceipt:
    work_id: str
    selected_agent_id: str
    ranked_candidates: tuple[AssuranceCandidateScore, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id,
            'selected_agent_id': self.selected_agent_id,
            'ranked_candidates': [x.to_state() for x in self.ranked_candidates],
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}


class AssuranceProfileRegistry:
    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        actual = {
            row.agent_id for row in registry.identities()
            if row.region in {'verification-testing', 'security-adversarial'}
        }
        expected = set(_SPEC_BY_ID)
        if actual != expected:
            raise ValueError('assurance profile registry requires the exact nine permanent assurance identities')

    def _profile(self, spec: _ProfileSpec) -> AssuranceProfile:
        identity = self.registry.get(spec.agent_id)
        if identity.region != spec.region:
            raise ValueError(f'assurance identity region mismatch: {spec.agent_id}')
        return AssuranceProfile(
            agent_id=spec.agent_id,
            region=spec.region,
            domains=spec.domains,
            primary_domains=spec.primary_domains,
            signals=spec.signals,
            preferred_external_cores=identity.external_core_bindings,
            accepted_neural_version=identity.neural_version,
        )

    def profiles(self) -> tuple[AssuranceProfile, ...]:
        return tuple(self._profile(spec) for spec in _PROFILE_SPECS)

    def get(self, agent_id: str) -> AssuranceProfile:
        try:
            spec = _SPEC_BY_ID[str(agent_id)]
        except KeyError as exc:
            raise KeyError(f'unknown assurance profile: {agent_id}') from exc
        return self._profile(spec)

    def _score(self, profile: AssuranceProfile, request: AssuranceWorkRequest) -> AssuranceCandidateScore:
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
        return AssuranceCandidateScore(profile.agent_id, score, tuple(reasons))

    def route(self, request: AssuranceWorkRequest) -> AssuranceAssignmentReceipt:
        self.registry.get(request.requester_agent_id)
        ranked = tuple(sorted(
            (self._score(profile, request) for profile in self.profiles()),
            key=lambda row: (-row.score, row.agent_id),
        ))
        if not ranked or ranked[0].score <= 1:
            raise ValueError('no assurance profile covers requested domains')
        payload = {
            'work_id': request.work_id,
            'selected_agent_id': ranked[0].agent_id,
            'ranked_candidates': [x.to_state() for x in ranked],
        }
        return AssuranceAssignmentReceipt(
            work_id=request.work_id,
            selected_agent_id=ranked[0].agent_id,
            ranked_candidates=ranked,
            digest=canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {'profiles': [row.to_state() for row in self.profiles()]}

    @classmethod
    def from_state(cls, registry: AgentRegistry, state: Mapping[str, Any]) -> 'AssuranceProfileRegistry':
        result = cls(registry)
        supplied = tuple(AssuranceProfile.from_state(x) for x in state.get('profiles', ()))
        if supplied and supplied != result.profiles():
            raise ValueError('serialized assurance profiles do not match current registry identities')
        return result
