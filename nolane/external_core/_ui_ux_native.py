from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .artifacts import ArtifactStore
from .evolution import SkillEvolutionEngine, SkillRecord
from .ui_coding import UICodingControlPlane
from .ui_design import UXDesignLedger
from .ui_observations import UIObservationLedger, Viewport
from .ui_profiles import UIAssignmentReceipt, UIProfileRegistry, UIWorkRequest
from .types import EventKind, canonical_digest


class UIQualityKind(str, Enum):
    VISUAL_DIFF = 'visual_diff'
    RESPONSIVE = 'responsive'
    ACCESSIBILITY = 'accessibility'
    INTERACTION_E2E = 'interaction_e2e'


@dataclass(frozen=True, slots=True)
class UIQualityEvidence:
    evidence_id: str
    verifier_agent_id: str
    kind: UIQualityKind
    passed: bool
    observation_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    false_accepts: int = 0
    regressions: int = 0

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or not self.verifier_agent_id.strip():
            raise ValueError('UI quality evidence/verifier must be explicit')
        if self.false_accepts < 0 or self.regressions < 0:
            raise ValueError('UI quality counters must be non-negative')
        if not self.observation_ids or not self.evidence_refs:
            raise ValueError('UI quality evidence requires observations and evidence refs')

    def to_state(self) -> dict[str, Any]:
        return {
            'evidence_id': self.evidence_id, 'verifier_agent_id': self.verifier_agent_id,
            'kind': self.kind.value, 'passed': self.passed,
            'observation_ids': list(self.observation_ids), 'evidence_refs': list(self.evidence_refs),
            'false_accepts': self.false_accepts, 'regressions': self.regressions,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'UIQualityEvidence':
        return cls(
            evidence_id=str(state['evidence_id']), verifier_agent_id=str(state['verifier_agent_id']),
            kind=UIQualityKind(str(state['kind'])), passed=bool(state['passed']),
            observation_ids=tuple(str(x) for x in state.get('observation_ids', ())),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            false_accepts=int(state.get('false_accepts', 0)), regressions=int(state.get('regressions', 0)),
        )


@dataclass(frozen=True, slots=True)
class UIReadinessReceipt:
    receipt_id: str
    patch_id: str
    coding_readiness_receipt_id: str
    ready: bool
    reasons: tuple[str, ...]
    observation_ids: tuple[str, ...]
    quality_evidence_ids: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'receipt_id': self.receipt_id, 'patch_id': self.patch_id,
            'coding_readiness_receipt_id': self.coding_readiness_receipt_id,
            'ready': self.ready, 'reasons': list(self.reasons),
            'observation_ids': list(self.observation_ids), 'quality_evidence_ids': list(self.quality_evidence_ids),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'UIReadinessReceipt':
        row = cls(
            receipt_id=str(state['receipt_id']), patch_id=str(state['patch_id']),
            coding_readiness_receipt_id=str(state['coding_readiness_receipt_id']), ready=bool(state['ready']),
            reasons=tuple(str(x) for x in state.get('reasons', ())),
            observation_ids=tuple(str(x) for x in state.get('observation_ids', ())),
            quality_evidence_ids=tuple(str(x) for x in state.get('quality_evidence_ids', ())),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('UI readiness receipt digest mismatch')
        return row


class UIControlPlane:
    def __init__(
        self, *, registry: Any, ledger: Any, tasks: Any, evolution: SkillEvolutionEngine,
        artifacts: ArtifactStore, authority: Any, planning: Any, architecture: Any,
        coding: UICodingControlPlane, profiles: UIProfileRegistry | None = None,
        observations: UIObservationLedger | None = None, design: UXDesignLedger | None = None,
        requests: Mapping[str, UIWorkRequest] | None = None,
        assignments: Mapping[str, UIAssignmentReceipt] | None = None,
        quality: Mapping[str, UIQualityEvidence] | None = None,
        readiness: tuple[UIReadinessReceipt, ...] = (), readiness_counter: int = 0,
    ) -> None:
        self.registry, self.ledger, self.tasks = registry, ledger, tasks
        self.evolution, self.artifacts, self.authority = evolution, artifacts, authority
        self.planning, self.architecture, self.coding = planning, architecture, coding
        self.profiles = profiles or UIProfileRegistry(registry)
        self.observations = observations or UIObservationLedger(artifacts)
        self.design = design or UXDesignLedger(registry=registry, authority=authority, ledger=ledger)
        self._requests = dict(requests or {})
        self._assignments = dict(assignments or {})
        self._quality = dict(quality or {})
        self._readiness = list(readiness)
        self._readiness_counter = int(readiness_counter)

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def request_work(self, request: UIWorkRequest) -> UIAssignmentReceipt:
        self.registry.get(request.requester_agent_id)
        self.tasks.get(request.task_id)
        if request.work_id in self._requests:
            if self._requests[request.work_id] == request:
                return self._assignments[request.work_id]
            raise ValueError('UI work id cannot be rebound')
        receipt = self.profiles.route(request)
        self._requests[request.work_id] = request
        self._assignments[request.work_id] = receipt
        target = self.registry.get(receipt.selected_agent_id)
        self.ledger.append(
            EventKind.TASK_ASSIGNED, source_agent_id=request.requester_agent_id,
            target_agent_id=receipt.selected_agent_id, region=target.region,
            evidence_refs=request.evidence_refs,
            payload={'ui_action': 'assignment', 'work_id': request.work_id, 'task_id': request.task_id, 'assignment_digest': receipt.digest},
        )
        return receipt

    def record_observation(self, *, patch_id: str | None = None, **kwargs: Any):
        producer = self.registry.get(kwargs['producer_agent_id'])
        if producer.region != 'frontend-ui':
            raise PermissionError('render observations require frontend-ui producer')
        task_id, work_id = str(kwargs['task_id']), str(kwargs['work_id'])
        self.tasks.get(task_id)
        if work_id not in self._requests:
            raise KeyError(f'unknown UI work: {work_id}')
        if patch_id is not None:
            patch = self.coding.patches.get_patch(patch_id)
            if patch.task_id != task_id or patch.work_id != work_id:
                raise ValueError('render observation patch lineage mismatch')
        row = self.observations.record(patch_id=patch_id, **kwargs)
        self.ledger.append(
            EventKind.EVIDENCE_ADDED, source_agent_id=producer.agent_id, target_agent_id='frontend.chief',
            region='frontend-ui', object_refs=(row.observation_id, row.screenshot_artifact_id),
            evidence_refs=row.evidence_refs,
            payload={'ui_action': 'render_observed', 'task_id': row.task_id, 'work_id': row.work_id, 'patch_id': row.patch_id},
        )
        return row

    def record_quality_evidence(self, evidence: UIQualityEvidence) -> UIQualityEvidence:
        verifier = self.registry.get(evidence.verifier_agent_id)
        if verifier.region != 'verification-testing':
            raise PermissionError('UI quality evidence requires verification-testing authority')
        for observation_id in evidence.observation_ids:
            observation = self.observations.get(observation_id)
            if observation.producer_agent_id == evidence.verifier_agent_id:
                raise PermissionError('UI quality self-verification is forbidden')
        old = self._quality.get(evidence.evidence_id)
        if old is not None and old != evidence:
            raise ValueError('UI quality evidence id cannot be rebound')
        self._quality[evidence.evidence_id] = evidence
        return evidence

    def _coding_readiness(self, receipt_id: str):
        for row in self.coding.readiness_receipts():
            if row.receipt_id == str(receipt_id):
                return row
        raise KeyError(f'unknown coding readiness receipt: {receipt_id}')

    def assess_readiness(
        self, *, patch_id: str, coding_readiness_receipt_id: str,
        observation_ids: tuple[str, ...], quality_evidence_ids: tuple[str, ...], require_interaction: bool = False,
    ) -> UIReadinessReceipt:
        patch = self.coding.patches.get_patch(patch_id)
        coding_receipt = self._coding_readiness(coding_readiness_receipt_id)
        reasons: list[str] = []
        if coding_receipt.patch_id != patch.patch_id or not coding_receipt.ready:
            reasons.append('coding_readiness_not_ready')
        producer = self.registry.get(patch.producer_agent_id)
        if producer.region != 'frontend-ui':
            reasons.append('invalid_frontend_producer')
        if not self.coding.has_active_external_grant(patch.producer_agent_id, patch.task_id):
            reasons.append('missing_active_external_coding_grant')
        observations = []
        if not observation_ids:
            reasons.append('missing_render_observation')
        for oid in observation_ids:
            row = self.observations.get(oid)
            observations.append(row)
            if row.task_id != patch.task_id or row.work_id != patch.work_id or row.patch_id != patch.patch_id:
                reasons.append('render_observation_lineage_mismatch')
        quality = []
        for eid in quality_evidence_ids:
            try:
                row = self._quality[str(eid)]
            except KeyError as exc:
                raise KeyError(f'unknown UI quality evidence: {eid}') from exc
            quality.append(row)
            if not row.passed:
                reasons.append('quality_failed')
            if row.false_accepts:
                reasons.append('quality_false_accepts')
            if row.regressions:
                reasons.append('quality_regressions')
            if not set(row.observation_ids).issubset(set(observation_ids)):
                reasons.append('quality_observation_scope_mismatch')
        clean_kinds = {
            row.kind for row in quality
            if row.passed and row.false_accepts == 0 and row.regressions == 0
        }
        required = {UIQualityKind.VISUAL_DIFF: 'missing_visual_evidence', UIQualityKind.RESPONSIVE: 'missing_responsive_evidence', UIQualityKind.ACCESSIBILITY: 'missing_accessibility_evidence'}
        if require_interaction:
            required[UIQualityKind.INTERACTION_E2E] = 'missing_interaction_evidence'
        for kind, reason in required.items():
            if kind not in clean_kinds:
                reasons.append(reason)
        responsive = [row for row in quality if row.kind is UIQualityKind.RESPONSIVE and row.passed and not row.false_accepts and not row.regressions]
        if responsive:
            responsive_obs = {oid for row in responsive for oid in row.observation_ids}
            classes = {self.observations.get(oid).viewport.viewport_class for oid in responsive_obs}
            if len(classes) < 2:
                reasons.append('responsive_viewport_coverage_insufficient')
        request = self._requests.get(patch.work_id)
        if request is not None and request.expected_ux_flow_id is not None:
            try:
                current = self.design.current(request.expected_ux_flow_id)
                if current.revision != request.expected_ux_revision:
                    reasons.append('stale_ux_revision')
            except KeyError:
                reasons.append('missing_ux_revision')
        reasons = list(dict.fromkeys(reasons))
        self._readiness_counter += 1
        receipt_id = f'ui-ready-{self._readiness_counter:08d}'
        payload = {
            'receipt_id': receipt_id, 'patch_id': patch.patch_id,
            'coding_readiness_receipt_id': coding_receipt.receipt_id,
            'ready': not reasons, 'reasons': reasons,
            'observation_ids': list(observation_ids), 'quality_evidence_ids': list(quality_evidence_ids),
        }
        row = UIReadinessReceipt(
            receipt_id, patch.patch_id, coding_receipt.receipt_id, not reasons, tuple(reasons),
            tuple(observation_ids), tuple(quality_evidence_ids), canonical_digest(payload),
        )
        self._readiness.append(row)
        self.ledger.append(
            EventKind.TEST_PASSED if row.ready else EventKind.VERIFICATION_REJECTED,
            source_agent_id='verification.chief', target_agent_id=patch.producer_agent_id,
            region='frontend-ui', object_refs=(patch.patch_id,),
            evidence_refs=tuple(evidence_id for evidence_id in quality_evidence_ids),
            payload={'ui_action': 'readiness_assessed', 'receipt_id': row.receipt_id, 'ready': row.ready, 'reasons': list(row.reasons)},
        )
        return row

    def report_plan_gap(self, *, source_agent_id: str, task_id: str, reason: str, suggested_nodes: tuple[str, ...], evidence_refs: tuple[str, ...]):
        self.profiles.get(source_agent_id)
        return self.tasks.propose_plan_gap(
            source_agent_id=source_agent_id, task_id=task_id, reason=reason,
            suggested_nodes=suggested_nodes, evidence_ids=evidence_refs,
        )

    def report_architecture_concern(self, *, source_agent_id: str, component_refs: tuple[str, ...], observation: str, alternatives: tuple[str, ...], evidence_refs: tuple[str, ...], severity: int):
        self.profiles.get(source_agent_id)
        return self.architecture.propose_concern(
            source_agent_id=source_agent_id, component_refs=component_refs, observation=observation,
            alternatives=alternatives, evidence_refs=evidence_refs, severity=severity,
        )

    def propose_personal_skill(self, *, agent_id: str, name: str, body: str, object_refs: tuple[str, ...], evidence_refs: tuple[str, ...]) -> SkillRecord:
        profile = self.profiles.get(agent_id)
        if not evidence_refs or not object_refs:
            raise ValueError('UI personal skill candidate requires object and evidence refs')
        skill = self.evolution.propose(owner_agent_id=agent_id, region=profile.region, name=name, body=body)
        self.ledger.append(
            EventKind.SKILL_CANDIDATE, source_agent_id=agent_id, target_agent_id=agent_id,
            region=profile.region, object_refs=(skill.skill_id,) + tuple(object_refs), evidence_refs=evidence_refs,
            payload={'ui_action': 'personal_skill_candidate', 'skill_id': skill.skill_id},
        )
        return skill

    def to_state(self) -> dict[str, Any]:
        return {
            'profiles': self.profiles.to_state(),
            'observations': self.observations.to_state(),
            'design': self.design.to_state(),
            'requests': [self._requests[key].to_state() for key in sorted(self._requests)],
            'assignments': [self._assignments[key].to_state() for key in sorted(self._assignments)],
            'quality': [self._quality[key].to_state() for key in sorted(self._quality)],
            'readiness': [x.to_state() for x in self._readiness],
            'readiness_counter': self._readiness_counter,
        }

    @classmethod
    def from_state(cls, *, state: Mapping[str, Any], registry: Any, ledger: Any, tasks: Any, evolution: SkillEvolutionEngine, artifacts: ArtifactStore, authority: Any, planning: Any, architecture: Any, coding: UICodingControlPlane) -> 'UIControlPlane':
        profiles = UIProfileRegistry.from_state(registry, state.get('profiles', {}))
        observations = UIObservationLedger.from_state(artifacts=artifacts, state=state.get('observations', {}))
        design = UXDesignLedger.from_state(registry=registry, authority=authority, ledger=ledger, state=state.get('design', {}))
        requests: dict[str, UIWorkRequest] = {}
        for value in state.get('requests', ()):
            row = UIWorkRequest.from_state(value)
            if row.work_id in requests:
                raise ValueError('duplicate UI work id')
            requests[row.work_id] = row
        assignments: dict[str, UIAssignmentReceipt] = {}
        for value in state.get('assignments', ()):
            row = UIAssignmentReceipt.from_state(value)
            if row.work_id in assignments:
                raise ValueError('duplicate UI assignment')
            profiles.get(row.selected_agent_id)
            assignments[row.work_id] = row
        if set(requests) != set(assignments):
            raise ValueError('UI requests/assignments snapshot mismatch')
        quality: dict[str, UIQualityEvidence] = {}
        for value in state.get('quality', ()):
            row = UIQualityEvidence.from_state(value)
            if row.evidence_id in quality:
                raise ValueError('duplicate UI quality evidence id')
            verifier = registry.get(row.verifier_agent_id)
            if verifier.region != 'verification-testing':
                raise ValueError('invalid restored UI verifier authority')
            for oid in row.observation_ids:
                observations.get(oid)
            quality[row.evidence_id] = row
        readiness = tuple(UIReadinessReceipt.from_state(x) for x in state.get('readiness', ()))
        max_counter = 0
        for row in readiness:
            coding.patches.get_patch(row.patch_id)
            for oid in row.observation_ids:
                observations.get(oid)
            for eid in row.quality_evidence_ids:
                if eid not in quality:
                    raise ValueError('UI readiness references unknown quality evidence')
            try:
                max_counter = max(max_counter, int(row.receipt_id.rsplit('-', 1)[1]))
            except Exception as exc:
                raise ValueError('non-canonical UI readiness id') from exc
        counter = int(state.get('readiness_counter', max_counter))
        if counter < max_counter:
            raise ValueError('UI readiness counter is behind history')
        return cls(
            registry=registry, ledger=ledger, tasks=tasks, evolution=evolution, artifacts=artifacts,
            authority=authority, planning=planning, architecture=architecture, coding=coding,
            profiles=profiles, observations=observations, design=design, requests=requests,
            assignments=assignments, quality=quality, readiness=readiness, readiness_counter=counter,
        )
