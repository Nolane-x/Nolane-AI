from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .registry import AgentRegistry
from .types import canonical_digest


class UIDomain(str, Enum):
    FRONTEND_CROSS_SYSTEM = 'frontend_cross_system'
    FRONTEND_LOGIC = 'frontend_logic'
    COMPONENT = 'component'
    BROWSER_RUNTIME = 'browser_runtime'
    UX_CROSS_PRODUCT = 'ux_cross_product'
    UX_FLOW = 'ux_flow'
    VISUAL_ACCESSIBILITY = 'visual_accessibility'


_PROFILE_CONFIG: dict[str, tuple[str, tuple[UIDomain, ...], tuple[str, ...]]] = {
    'frontend.chief': ('frontend-ui', (UIDomain.FRONTEND_CROSS_SYSTEM,), ('cross-frontend', 'integration', 'rendered-integration')),
    'frontend.logic.01': ('frontend-ui', (UIDomain.FRONTEND_LOGIC,), ('state', 'data-flow', 'frontend-logic', 'interaction-state')),
    'frontend.component.01': ('frontend-ui', (UIDomain.COMPONENT,), ('component', 'design-system', 'composition', 'styles')),
    'frontend.browser-runtime.01': ('frontend-ui', (UIDomain.BROWSER_RUNTIME,), ('browser', 'runtime', 'dom', 'cssom', 'render')),
    'ux.chief': ('ux-product-design', (UIDomain.UX_CROSS_PRODUCT,), ('cross-product', 'acceptance', 'interaction-design')),
    'ux.flow.01': ('ux-product-design', (UIDomain.UX_FLOW,), ('journey', 'interaction', 'information-architecture', 'flow')),
    'ux.visual-accessibility.01': ('ux-product-design', (UIDomain.VISUAL_ACCESSIBILITY,), ('visual', 'accessibility', 'responsive', 'design-token')),
}


@dataclass(frozen=True, slots=True)
class UIProfile:
    agent_id: str
    region: str
    domains: tuple[UIDomain, ...]
    preferred_external_cores: tuple[str, ...]
    signals: tuple[str, ...]
    accepted_neural_version: str

    def to_state(self) -> dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'region': self.region,
            'domains': [x.value for x in self.domains],
            'preferred_external_cores': list(self.preferred_external_cores),
            'signals': list(self.signals),
            'accepted_neural_version': self.accepted_neural_version,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'UIProfile':
        return cls(
            agent_id=str(state['agent_id']),
            region=str(state['region']),
            domains=tuple(UIDomain(str(x)) for x in state.get('domains', ())),
            preferred_external_cores=tuple(str(x) for x in state.get('preferred_external_cores', ())),
            signals=tuple(str(x) for x in state.get('signals', ())),
            accepted_neural_version=str(state['accepted_neural_version']),
        )


@dataclass(frozen=True, slots=True)
class UIWorkRequest:
    work_id: str
    task_id: str
    requested_domains: tuple[UIDomain, ...]
    scope_hints: tuple[str, ...]
    priority: int
    requester_agent_id: str
    evidence_refs: tuple[str, ...]
    expected_ux_flow_id: str | None = None
    expected_ux_revision: int | None = None

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.work_id, self.task_id, self.requester_agent_id)):
            raise ValueError('UI work identity/task/requester must be explicit')
        if not self.requested_domains or not self.evidence_refs:
            raise ValueError('UI work requires domain and evidence')
        if not 0 <= int(self.priority) <= 100:
            raise ValueError('UI work priority must be in [0,100]')
        if (self.expected_ux_flow_id is None) != (self.expected_ux_revision is None):
            raise ValueError('expected UX flow id and revision must be supplied together')
        if self.expected_ux_revision is not None and self.expected_ux_revision < 1:
            raise ValueError('expected UX revision must be positive')

    def to_state(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id,
            'task_id': self.task_id,
            'requested_domains': [x.value for x in self.requested_domains],
            'scope_hints': list(self.scope_hints),
            'priority': self.priority,
            'requester_agent_id': self.requester_agent_id,
            'evidence_refs': list(self.evidence_refs),
            'expected_ux_flow_id': self.expected_ux_flow_id,
            'expected_ux_revision': self.expected_ux_revision,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'UIWorkRequest':
        return cls(
            work_id=str(state['work_id']),
            task_id=str(state['task_id']),
            requested_domains=tuple(UIDomain(str(x)) for x in state.get('requested_domains', ())),
            scope_hints=tuple(str(x) for x in state.get('scope_hints', ())),
            priority=int(state.get('priority', 0)),
            requester_agent_id=str(state['requester_agent_id']),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            expected_ux_flow_id=None if state.get('expected_ux_flow_id') is None else str(state['expected_ux_flow_id']),
            expected_ux_revision=None if state.get('expected_ux_revision') is None else int(state['expected_ux_revision']),
        )


@dataclass(frozen=True, slots=True)
class UICandidateScore:
    agent_id: str
    score: int
    reasons: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {'agent_id': self.agent_id, 'score': self.score, 'reasons': list(self.reasons)}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'UICandidateScore':
        return cls(str(state['agent_id']), int(state['score']), tuple(str(x) for x in state.get('reasons', ())))


@dataclass(frozen=True, slots=True)
class UIAssignmentReceipt:
    work_id: str
    selected_agent_id: str
    ranked_candidates: tuple[UICandidateScore, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id,
            'selected_agent_id': self.selected_agent_id,
            'ranked_candidates': [x.to_state() for x in self.ranked_candidates],
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'UIAssignmentReceipt':
        row = cls(
            work_id=str(state['work_id']),
            selected_agent_id=str(state['selected_agent_id']),
            ranked_candidates=tuple(UICandidateScore.from_state(x) for x in state.get('ranked_candidates', ())),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('UI assignment digest mismatch')
        return row


class UIProfileRegistry:
    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry
        found = {
            identity.agent_id
            for identity in registry.identities()
            if identity.agent_id in _PROFILE_CONFIG and identity.region == _PROFILE_CONFIG[identity.agent_id][0]
        }
        if found != set(_PROFILE_CONFIG):
            raise ValueError('UI profile registry requires exact seven permanent UI/UX identities')

    def _profile(self, agent_id: str) -> UIProfile:
        key = str(agent_id)
        try:
            region, domains, signals = _PROFILE_CONFIG[key]
        except KeyError as exc:
            raise KeyError(f'unknown UI profile: {agent_id}') from exc
        identity = self.registry.get(key)
        if identity.region != region:
            raise ValueError('UI identity region does not match profile configuration')
        return UIProfile(
            agent_id=key,
            region=region,
            domains=domains,
            preferred_external_cores=identity.external_core_bindings,
            signals=signals,
            accepted_neural_version=identity.neural_version,
        )

    def profiles(self) -> tuple[UIProfile, ...]:
        return tuple(self._profile(key) for key in sorted(_PROFILE_CONFIG))

    def get(self, agent_id: str) -> UIProfile:
        return self._profile(agent_id)

    def _score(self, profile: UIProfile, request: UIWorkRequest) -> UICandidateScore:
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
        return UICandidateScore(profile.agent_id, score, tuple(reasons))

    def route(self, request: UIWorkRequest) -> UIAssignmentReceipt:
        requested_frontend = any(x in {
            UIDomain.FRONTEND_CROSS_SYSTEM, UIDomain.FRONTEND_LOGIC, UIDomain.COMPONENT, UIDomain.BROWSER_RUNTIME,
        } for x in request.requested_domains)
        target_region = 'frontend-ui' if requested_frontend else 'ux-product-design'
        ranked = tuple(sorted(
            (self._score(row, request) for row in self.profiles() if row.region == target_region),
            key=lambda x: (-x.score, x.agent_id),
        ))
        if not ranked:
            raise ValueError('no UI profiles available for requested region')
        payload = {
            'work_id': request.work_id,
            'selected_agent_id': ranked[0].agent_id,
            'ranked_candidates': [x.to_state() for x in ranked],
        }
        return UIAssignmentReceipt(request.work_id, ranked[0].agent_id, ranked, canonical_digest(payload))

    def to_state(self) -> dict[str, Any]:
        return {'profiles': [row.to_state() for row in self.profiles()]}

    @classmethod
    def from_state(cls, registry: AgentRegistry, state: Mapping[str, Any]) -> 'UIProfileRegistry':
        result = cls(registry)
        supplied = tuple(UIProfile.from_state(x) for x in state.get('profiles', ()))
        if supplied and supplied != result.profiles():
            raise ValueError('serialized UI profiles do not match current authoritative identities')
        return result
