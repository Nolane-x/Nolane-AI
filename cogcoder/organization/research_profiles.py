from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .registry import AgentRegistry
from .types import canonical_digest


class ResearchDomain(str, Enum):
    REPOSITORY_ARCHAEOLOGY = 'repository_archaeology'
    DOCS_API = 'docs_api'
    PRIOR_ART = 'prior_art'
    CROSS_RESEARCH = 'cross_research'


@dataclass(frozen=True, slots=True)
class _ProfileSpec:
    agent_id: str
    domains: tuple[ResearchDomain, ...]
    primary_domains: tuple[ResearchDomain, ...]
    signals: tuple[str, ...]


_PROFILE_SPECS = (
    _ProfileSpec(
        'research.chief',
        (ResearchDomain.CROSS_RESEARCH, ResearchDomain.REPOSITORY_ARCHAEOLOGY, ResearchDomain.DOCS_API, ResearchDomain.PRIOR_ART),
        (ResearchDomain.CROSS_RESEARCH,),
        ('synthesis', 'cross-domain', 'conflict', 'high-stakes'),
    ),
    _ProfileSpec(
        'research.repo-archaeology.01',
        (ResearchDomain.REPOSITORY_ARCHAEOLOGY,),
        (ResearchDomain.REPOSITORY_ARCHAEOLOGY,),
        ('history', 'repository', 'commit', 'convention'),
    ),
    _ProfileSpec(
        'research.docs-api.01',
        (ResearchDomain.DOCS_API,),
        (ResearchDomain.DOCS_API,),
        ('official-docs', 'api', 'sdk', 'release-note', 'advisory', 'package'),
    ),
    _ProfileSpec(
        'research.prior-art.01',
        (ResearchDomain.PRIOR_ART,),
        (ResearchDomain.PRIOR_ART,),
        ('paper', 'algorithm', 'prior-art', 'literature'),
    ),
)
_SPEC_BY_ID = {row.agent_id: row for row in _PROFILE_SPECS}


@dataclass(frozen=True, slots=True)
class ResearchProfile:
    agent_id: str
    region: str
    domains: tuple[ResearchDomain, ...]
    primary_domains: tuple[ResearchDomain, ...]
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
    def from_state(cls, state: Mapping[str, Any]) -> 'ResearchProfile':
        return cls(
            agent_id=str(state['agent_id']),
            region=str(state['region']),
            domains=tuple(ResearchDomain(str(x)) for x in state.get('domains', ())),
            primary_domains=tuple(ResearchDomain(str(x)) for x in state.get('primary_domains', ())),
            signals=tuple(str(x) for x in state.get('signals', ())),
            preferred_external_cores=tuple(str(x) for x in state.get('preferred_external_cores', ())),
            accepted_neural_version=str(state['accepted_neural_version']),
        )


@dataclass(frozen=True, slots=True)
class ResearchWorkRequest:
    work_id: str
    question: str
    requested_domains: tuple[ResearchDomain, ...]
    scope_hints: tuple[str, ...]
    priority: int
    requester_agent_id: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.work_id, self.question, self.requester_agent_id)):
            raise ValueError('research work id, question and requester must be explicit')
        if not self.requested_domains or not self.evidence_refs:
            raise ValueError('research work requires domains and evidence refs')
        if not 0 <= int(self.priority) <= 100:
            raise ValueError('research work priority must be in [0,100]')

    def to_state(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id,
            'question': self.question,
            'requested_domains': [x.value for x in self.requested_domains],
            'scope_hints': list(self.scope_hints),
            'priority': int(self.priority),
            'requester_agent_id': self.requester_agent_id,
            'evidence_refs': list(self.evidence_refs),
        }


@dataclass(frozen=True, slots=True)
class ResearchCandidateScore:
    agent_id: str
    score: int
    reasons: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {'agent_id': self.agent_id, 'score': self.score, 'reasons': list(self.reasons)}


@dataclass(frozen=True, slots=True)
class ResearchAssignmentReceipt:
    work_id: str
    selected_agent_id: str
    ranked_candidates: tuple[ResearchCandidateScore, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id,
            'selected_agent_id': self.selected_agent_id,
            'ranked_candidates': [x.to_state() for x in self.ranked_candidates],
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}


class ResearchProfileRegistry:
    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        actual = {row.agent_id for row in registry.identities() if row.region == 'research-external'}
        if actual != set(_SPEC_BY_ID):
            raise ValueError('research profile registry requires exact four Research identities')

    def _profile(self, spec: _ProfileSpec) -> ResearchProfile:
        identity = self.registry.get(spec.agent_id)
        if identity.region != 'research-external':
            raise ValueError(f'research identity region mismatch: {spec.agent_id}')
        return ResearchProfile(
            agent_id=spec.agent_id,
            region=identity.region,
            domains=spec.domains,
            primary_domains=spec.primary_domains,
            signals=spec.signals,
            preferred_external_cores=identity.external_core_bindings,
            accepted_neural_version=identity.neural_version,
        )

    def profiles(self) -> tuple[ResearchProfile, ...]:
        return tuple(self._profile(spec) for spec in _PROFILE_SPECS)

    def get(self, agent_id: str) -> ResearchProfile:
        try:
            return self._profile(_SPEC_BY_ID[str(agent_id)])
        except KeyError as exc:
            raise KeyError(f'unknown research profile: {agent_id}') from exc

    def _score(self, profile: ResearchProfile, request: ResearchWorkRequest) -> ResearchCandidateScore:
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
        return ResearchCandidateScore(profile.agent_id, score, tuple(reasons))

    def route(self, request: ResearchWorkRequest) -> ResearchAssignmentReceipt:
        self.registry.get(request.requester_agent_id)
        ranked = tuple(sorted(
            (self._score(profile, request) for profile in self.profiles()),
            key=lambda x: (-x.score, x.agent_id),
        ))
        if not ranked or ranked[0].score <= 1:
            raise ValueError('no research profile covers requested domains')
        payload = {
            'work_id': request.work_id,
            'selected_agent_id': ranked[0].agent_id,
            'ranked_candidates': [x.to_state() for x in ranked],
        }
        return ResearchAssignmentReceipt(
            work_id=request.work_id,
            selected_agent_id=ranked[0].agent_id,
            ranked_candidates=ranked,
            digest=canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {'profiles': [row.to_state() for row in self.profiles()]}

    @classmethod
    def from_state(cls, registry: AgentRegistry, state: Mapping[str, Any]) -> 'ResearchProfileRegistry':
        result = cls(registry)
        supplied = tuple(ResearchProfile.from_state(x) for x in state.get('profiles', ()))
        if supplied and supplied != result.profiles():
            raise ValueError('serialized research profiles do not match current registry identities')
        return result
