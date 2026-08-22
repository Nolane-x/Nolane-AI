from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .coding import CodingControlPlane, CodingReadinessReceipt
from .coding_profiles import CodingAssignmentReceipt, CodingWorkRequest
from .debug_evidence import (
    DebugEvidenceArtifact, DebugEvidenceKind, DebugEvidenceLedger, FailureCase, FailureClass, ReproductionReceipt,
)
from .debug_hypotheses import DebugHypothesis, DebugHypothesisLedger, HypothesisStatus
from .debug_profiles import DebugAssignmentReceipt, DebugProfileRegistry, DebugWorkRequest
from .evolution import SkillEvolutionEngine, SkillRecord
from .registry import AgentRegistry
from .tasks import TaskGraph
from .types import EventKind, canonical_digest


@dataclass(frozen=True, slots=True)
class DebugPatchHandoff:
    handoff_id: str
    case_id: str
    hypothesis_id: str
    coding_work_id: str
    coding_task_id: str
    selected_coder_agent_id: str
    coding_assignment_digest: str
    affected_source_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'handoff_id': self.handoff_id, 'case_id': self.case_id, 'hypothesis_id': self.hypothesis_id,
            'coding_work_id': self.coding_work_id, 'coding_task_id': self.coding_task_id,
            'selected_coder_agent_id': self.selected_coder_agent_id,
            'coding_assignment_digest': self.coding_assignment_digest,
            'affected_source_refs': list(self.affected_source_refs), 'evidence_refs': list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'DebugPatchHandoff':
        row = cls(
            handoff_id=str(state['handoff_id']), case_id=str(state['case_id']),
            hypothesis_id=str(state['hypothesis_id']), coding_work_id=str(state['coding_work_id']),
            coding_task_id=str(state['coding_task_id']), selected_coder_agent_id=str(state['selected_coder_agent_id']),
            coding_assignment_digest=str(state['coding_assignment_digest']),
            affected_source_refs=tuple(str(x) for x in state.get('affected_source_refs', ())),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('debug patch handoff digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class DebugResolutionReceipt:
    resolution_id: str
    case_id: str
    handoff_id: str
    hypothesis_id: str
    patch_id: str
    coding_readiness_receipt_id: str
    resolver_agent_id: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'resolution_id': self.resolution_id, 'case_id': self.case_id, 'handoff_id': self.handoff_id,
            'hypothesis_id': self.hypothesis_id, 'patch_id': self.patch_id,
            'coding_readiness_receipt_id': self.coding_readiness_receipt_id,
            'resolver_agent_id': self.resolver_agent_id,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'DebugResolutionReceipt':
        row = cls(
            resolution_id=str(state['resolution_id']), case_id=str(state['case_id']), handoff_id=str(state['handoff_id']),
            hypothesis_id=str(state['hypothesis_id']), patch_id=str(state['patch_id']),
            coding_readiness_receipt_id=str(state['coding_readiness_receipt_id']),
            resolver_agent_id=str(state['resolver_agent_id']), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('debug resolution digest mismatch')
        return row


class DebugControlPlane:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        ledger: Any,
        tasks: TaskGraph,
        evolution: SkillEvolutionEngine,
        coding: CodingControlPlane,
        profiles: DebugProfileRegistry | None = None,
        evidence: DebugEvidenceLedger | None = None,
        hypotheses: DebugHypothesisLedger | None = None,
        requests: Mapping[str, DebugWorkRequest] | None = None,
        assignments: Mapping[str, DebugAssignmentReceipt] | None = None,
        handoffs: tuple[DebugPatchHandoff, ...] = (),
        resolutions: tuple[DebugResolutionReceipt, ...] = (),
        handoff_counter: int = 0,
        resolution_counter: int = 0,
    ) -> None:
        self.registry = registry
        self.ledger = ledger
        self.tasks = tasks
        self.evolution = evolution
        self.coding = coding
        self.profiles = profiles or DebugProfileRegistry(registry)
        self.evidence = evidence or DebugEvidenceLedger()
        self.hypotheses = hypotheses or DebugHypothesisLedger(self.evidence)
        self._requests = dict(requests or {})
        self._assignments = dict(assignments or {})
        self._handoffs = list(handoffs)
        self._resolutions = list(resolutions)
        self._handoff_counter = int(handoff_counter)
        self._resolution_counter = int(resolution_counter)

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def open_case(self, **kwargs) -> FailureCase:
        task = self.tasks.get(str(kwargs['task_id']))
        self.registry.get(str(kwargs['reporter_agent_id']))
        case = self.evidence.open_case(**kwargs)
        self.ledger.append(
            EventKind.BUG_DISCOVERED,
            source_agent_id=case.reporter_agent_id,
            target_agent_id='debug.chief', region='debugging-failure',
            object_refs=(case.case_id, case.task_id), evidence_refs=case.initial_evidence_refs,
            payload={
                'debug_action': 'case_opened', 'case_id': case.case_id, 'task_id': task.task_id,
                'failure_class': case.failure_class.value, 'symptom': case.symptom,
            },
        )
        return case

    def request_investigation(self, request: DebugWorkRequest) -> DebugAssignmentReceipt:
        case = self.evidence.get_case(request.case_id)
        if case.task_id != request.task_id:
            raise ValueError('debug work task does not match failure case')
        self.tasks.get(request.task_id)
        self.registry.get(request.requester_agent_id)
        existing_request = self._requests.get(request.work_id)
        if existing_request is not None and existing_request != request:
            raise ValueError('debug work id cannot be rebound')
        existing = self._assignments.get(request.work_id)
        if existing_request == request and existing is not None:
            return existing
        receipt = self.profiles.route(request)
        self._requests[request.work_id] = request
        self._assignments[request.work_id] = receipt
        self.ledger.append(
            EventKind.TASK_ASSIGNED,
            source_agent_id=request.requester_agent_id,
            target_agent_id=receipt.selected_agent_id, region='debugging-failure',
            object_refs=(case.case_id,), evidence_refs=request.evidence_refs,
            payload={
                'debug_action': 'investigation_assigned', 'work_id': request.work_id,
                'case_id': case.case_id, 'task_id': request.task_id, 'assignment_digest': receipt.digest,
            },
        )
        return receipt

    def record_reproduction(self, **kwargs) -> ReproductionReceipt:
        self.profiles.get(str(kwargs['reproducer_agent_id']))
        row = self.evidence.record_reproduction(**kwargs)
        self.ledger.append(
            EventKind.EVIDENCE_ADDED,
            source_agent_id=row.reproducer_agent_id, target_agent_id='debug.chief', region='debugging-failure',
            object_refs=(row.case_id, row.receipt_id) + row.artifact_refs, evidence_refs=row.evidence_refs,
            payload={
                'debug_action': 'reproduction_recorded', 'case_id': row.case_id,
                'receipt_id': row.receipt_id, 'deterministic': row.deterministic, 'minimized': row.minimized,
                'failure_fingerprint': row.failure_fingerprint,
            },
        )
        return row

    def add_evidence(self, **kwargs) -> DebugEvidenceArtifact:
        self.profiles.get(str(kwargs['producer_agent_id']))
        row = self.evidence.add_evidence(**kwargs)
        self.ledger.append(
            EventKind.EVIDENCE_ADDED,
            source_agent_id=row.producer_agent_id, target_agent_id='debug.chief', region='debugging-failure',
            object_refs=(row.case_id, row.artifact_id) + row.output_artifact_refs, evidence_refs=row.evidence_refs,
            payload={
                'debug_action': 'evidence_added', 'case_id': row.case_id,
                'artifact_id': row.artifact_id, 'kind': row.kind.value, 'summary': row.summary,
            },
        )
        return row

    def propose_hypothesis(self, **kwargs) -> DebugHypothesis:
        self.profiles.get(str(kwargs['proposer_agent_id']))
        row = self.hypotheses.propose(**kwargs)
        self.ledger.append(
            EventKind.HYPOTHESIS_PROPOSED,
            source_agent_id=row.proposer_agent_id, target_agent_id='debug.chief', region='debugging-failure',
            object_refs=(row.case_id, row.hypothesis_id) + row.supporting_evidence_ids,
            payload={
                'debug_action': 'hypothesis_proposed', 'case_id': row.case_id,
                'hypothesis_id': row.hypothesis_id, 'confidence': row.confidence,
            },
        )
        return row

    def reject_hypothesis(self, hypothesis_id: str, **kwargs) -> DebugHypothesis:
        row = self.hypotheses.reject(hypothesis_id, **kwargs)
        self.ledger.append(
            EventKind.VERIFICATION_REJECTED,
            source_agent_id=str(kwargs['actor_agent_id']), target_agent_id=row.proposer_agent_id,
            region='debugging-failure', object_refs=(row.case_id, row.hypothesis_id),
            payload={
                'debug_action': 'hypothesis_rejected', 'case_id': row.case_id,
                'hypothesis_id': row.hypothesis_id, 'reason': row.rejection_reason,
            },
        )
        return row

    def accept_hypothesis(self, hypothesis_id: str, *, actor_agent_id: str) -> DebugHypothesis:
        row = self.hypotheses.accept(hypothesis_id, actor_agent_id=actor_agent_id)
        self.ledger.append(
            EventKind.EVIDENCE_ADDED,
            source_agent_id=str(actor_agent_id), target_agent_id=row.proposer_agent_id,
            region='debugging-failure', object_refs=(row.case_id, row.hypothesis_id),
            evidence_refs=tuple(
                evidence_ref
                for artifact_id in row.supporting_evidence_ids
                for evidence_ref in self.evidence.get_evidence(artifact_id).evidence_refs
            ),
            payload={
                'debug_action': 'root_cause_accepted', 'case_id': row.case_id,
                'hypothesis_id': row.hypothesis_id,
            },
        )
        return row

    def handoff_to_coding(
        self, *, case_id: str, hypothesis_id: str, work_request: CodingWorkRequest,
        affected_source_refs: tuple[str, ...], evidence_refs: tuple[str, ...],
    ) -> DebugPatchHandoff:
        case = self.evidence.get_case(case_id)
        root = self.hypotheses.current_root_cause(case_id)
        if root.hypothesis_id != str(hypothesis_id):
            raise PermissionError('coding handoff requires current accepted root cause')
        if not affected_source_refs or not evidence_refs:
            raise ValueError('debug coding handoff requires source and evidence refs')
        assignment: CodingAssignmentReceipt = self.coding.request_work(work_request)
        self._handoff_counter += 1
        handoff_id = f'debug-handoff-{self._handoff_counter:08d}'
        payload = {
            'handoff_id': handoff_id, 'case_id': case.case_id, 'hypothesis_id': root.hypothesis_id,
            'coding_work_id': work_request.work_id, 'coding_task_id': work_request.task_id,
            'selected_coder_agent_id': assignment.selected_agent_id,
            'coding_assignment_digest': assignment.digest,
            'affected_source_refs': [str(x) for x in affected_source_refs],
            'evidence_refs': [str(x) for x in evidence_refs],
        }
        row = DebugPatchHandoff(
            handoff_id, case.case_id, root.hypothesis_id, work_request.work_id, work_request.task_id,
            assignment.selected_agent_id, assignment.digest, tuple(payload['affected_source_refs']),
            tuple(payload['evidence_refs']), canonical_digest(payload),
        )
        self._handoffs.append(row)
        self.evidence.mark_patch_in_progress(case.case_id)
        self.ledger.append(
            EventKind.TASK_PROGRESS,
            source_agent_id='debug.chief', target_agent_id=assignment.selected_agent_id,
            region='debugging-failure', object_refs=(case.case_id, row.handoff_id, row.hypothesis_id),
            evidence_refs=row.evidence_refs,
            payload={
                'debug_action': 'coding_handoff', 'case_id': case.case_id,
                'handoff_id': row.handoff_id, 'work_id': row.coding_work_id,
                'assignment_digest': row.coding_assignment_digest,
            },
        )
        return row

    def _get_handoff(self, handoff_id: str) -> DebugPatchHandoff:
        for row in self._handoffs:
            if row.handoff_id == str(handoff_id):
                return row
        raise KeyError(f'unknown debug handoff: {handoff_id}')

    def _get_readiness(self, receipt_id: str) -> CodingReadinessReceipt:
        for row in self.coding.readiness_receipts():
            if row.receipt_id == str(receipt_id):
                return row
        raise KeyError(f'unknown coding readiness receipt: {receipt_id}')

    def resolve(
        self, *, case_id: str, handoff_id: str, patch_id: str,
        coding_readiness_receipt_id: str,
    ) -> DebugResolutionReceipt:
        case = self.evidence.get_case(case_id)
        handoff = self._get_handoff(handoff_id)
        if handoff.case_id != case.case_id:
            raise ValueError('handoff belongs to another case')
        root = self.hypotheses.current_root_cause(case.case_id)
        if root.hypothesis_id != handoff.hypothesis_id:
            raise PermissionError('accepted root cause changed after handoff')
        patch = self.coding.patches.get_patch(patch_id)
        if patch.work_id != handoff.coding_work_id or patch.task_id != handoff.coding_task_id:
            raise ValueError('coding patch does not match debug handoff')
        readiness = self._get_readiness(coding_readiness_receipt_id)
        if readiness.patch_id != patch.patch_id:
            raise ValueError('coding readiness receipt references another patch')
        if not readiness.ready:
            raise PermissionError('debug case cannot resolve from non-ready coding patch')
        self._resolution_counter += 1
        resolution_id = f'debug-resolution-{self._resolution_counter:08d}'
        payload = {
            'resolution_id': resolution_id, 'case_id': case.case_id, 'handoff_id': handoff.handoff_id,
            'hypothesis_id': root.hypothesis_id, 'patch_id': patch.patch_id,
            'coding_readiness_receipt_id': readiness.receipt_id,
            'resolver_agent_id': root.proposer_agent_id,
        }
        row = DebugResolutionReceipt(
            resolution_id, case.case_id, handoff.handoff_id, root.hypothesis_id, patch.patch_id,
            readiness.receipt_id, root.proposer_agent_id, canonical_digest(payload),
        )
        self._resolutions.append(row)
        self.evidence.mark_resolved(case.case_id)
        self.ledger.append(
            EventKind.TEST_PASSED,
            source_agent_id=readiness.verification.verifier_agent_id,
            target_agent_id=root.proposer_agent_id, region='debugging-failure',
            object_refs=(case.case_id, row.resolution_id, patch.patch_id),
            evidence_refs=(readiness.verification.evidence_id,),
            payload={
                'debug_action': 'case_resolved', 'case_id': case.case_id,
                'resolution_id': row.resolution_id, 'patch_id': patch.patch_id,
                'root_cause_hypothesis_id': root.hypothesis_id,
            },
        )
        return row

    def get_resolution(self, resolution_id: str) -> DebugResolutionReceipt:
        for row in self._resolutions:
            if row.resolution_id == str(resolution_id):
                return row
        raise KeyError(f'unknown debug resolution: {resolution_id}')

    def propose_personal_skill_from_resolution(
        self, resolution_id: str, *, name: str, body: str,
    ) -> SkillRecord:
        resolution = self.get_resolution(resolution_id)
        root = self.hypotheses.get(resolution.hypothesis_id)
        if root.status is not HypothesisStatus.ACCEPTED:
            raise ValueError('debug skill requires accepted root cause')
        identity = self.registry.get(resolution.resolver_agent_id)
        skill = self.evolution.propose(
            owner_agent_id=identity.agent_id, region=identity.region, name=name, body=body,
        )
        self.ledger.append(
            EventKind.SKILL_CANDIDATE,
            source_agent_id=identity.agent_id, target_agent_id=identity.agent_id,
            region=identity.region, object_refs=(skill.skill_id, resolution.resolution_id),
            payload={
                'debug_action': 'personal_skill_candidate', 'skill_id': skill.skill_id,
                'resolution_id': resolution.resolution_id,
            },
        )
        return skill

    def to_state(self) -> dict[str, Any]:
        return {
            'profiles': self.profiles.to_state(), 'evidence': self.evidence.to_state(),
            'hypotheses': self.hypotheses.to_state(),
            'requests': [self._requests[key].to_state() for key in sorted(self._requests)],
            'assignments': [self._assignments[key].to_state() for key in sorted(self._assignments)],
            'handoffs': [x.to_state() for x in self._handoffs],
            'resolutions': [x.to_state() for x in self._resolutions],
            'handoff_counter': self._handoff_counter, 'resolution_counter': self._resolution_counter,
        }

    @classmethod
    def from_state(
        cls, *, registry: AgentRegistry, ledger: Any, tasks: TaskGraph,
        evolution: SkillEvolutionEngine, coding: CodingControlPlane, state: Mapping[str, Any],
    ) -> 'DebugControlPlane':
        profiles = DebugProfileRegistry.from_state(registry, state.get('profiles', {}))
        evidence = DebugEvidenceLedger.from_state(state.get('evidence', {}))
        hypotheses = DebugHypothesisLedger.from_state(evidence, state.get('hypotheses', {}))
        requests: dict[str, DebugWorkRequest] = {}
        for value in state.get('requests', ()):
            row = DebugWorkRequest.from_state(value)
            if row.work_id in requests:
                raise ValueError('duplicate debug work id')
            evidence.get_case(row.case_id)
            requests[row.work_id] = row
        assignments: dict[str, DebugAssignmentReceipt] = {}
        for value in state.get('assignments', ()):
            row = DebugAssignmentReceipt.from_state(value)
            if row.work_id in assignments:
                raise ValueError('duplicate debug assignment')
            profiles.get(row.selected_agent_id)
            assignments[row.work_id] = row
        if set(requests) != set(assignments):
            raise ValueError('debug requests/assignments snapshot mismatch')
        handoffs = tuple(DebugPatchHandoff.from_state(x) for x in state.get('handoffs', ()))
        resolutions = tuple(DebugResolutionReceipt.from_state(x) for x in state.get('resolutions', ()))
        for row in handoffs:
            evidence.get_case(row.case_id)
            hypotheses.get(row.hypothesis_id)
        for row in resolutions:
            evidence.get_case(row.case_id)
            hypotheses.get(row.hypothesis_id)
            coding.patches.get_patch(row.patch_id)
        handoff_counter = int(state.get('handoff_counter', len(handoffs)))
        resolution_counter = int(state.get('resolution_counter', len(resolutions)))
        return cls(
            registry=registry, ledger=ledger, tasks=tasks, evolution=evolution, coding=coding,
            profiles=profiles, evidence=evidence, hypotheses=hypotheses,
            requests=requests, assignments=assignments, handoffs=handoffs, resolutions=resolutions,
            handoff_counter=handoff_counter, resolution_counter=resolution_counter,
        )
