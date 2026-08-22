from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .architecture import ArchitectureControlPlane
from .code_claims import ClaimMode, CodeClaim, CodeClaimLedger
from .coding_patches import CodingPatchCandidate, CodingPatchLedger, CodingPatchStatus
from .coding_profiles import CodingAssignmentReceipt, CodingProfileRegistry, CodingWorkRequest
from .evolution import SkillEvolutionEngine, SkillRecord
from .planning import PlanningControlPlane
from .registry import AgentRegistry
from .tasks import TaskGraph
from .types import EventKind, canonical_digest


@dataclass(frozen=True, slots=True)
class PatchVerificationEvidence:
    evidence_id: str
    verifier_agent_id: str
    passed: bool
    false_accepts: int = 0
    regressions: int = 0

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or not self.verifier_agent_id.strip():
            raise ValueError('patch verification evidence/verifier must be explicit')
        if self.false_accepts < 0 or self.regressions < 0:
            raise ValueError('patch verification counters must be non-negative')

    def to_state(self) -> dict[str, Any]:
        return {
            'evidence_id': self.evidence_id,
            'verifier_agent_id': self.verifier_agent_id,
            'passed': self.passed,
            'false_accepts': self.false_accepts,
            'regressions': self.regressions,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'PatchVerificationEvidence':
        return cls(
            evidence_id=str(state['evidence_id']),
            verifier_agent_id=str(state['verifier_agent_id']),
            passed=bool(state['passed']),
            false_accepts=int(state.get('false_accepts', 0)),
            regressions=int(state.get('regressions', 0)),
        )


@dataclass(frozen=True, slots=True)
class CodingReadinessReceipt:
    receipt_id: str
    patch_id: str
    ready: bool
    reasons: tuple[str, ...]
    verification: PatchVerificationEvidence
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'receipt_id': self.receipt_id,
            'patch_id': self.patch_id,
            'ready': self.ready,
            'reasons': list(self.reasons),
            'verification': self.verification.to_state(),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CodingReadinessReceipt':
        verification = PatchVerificationEvidence.from_state(state['verification'])
        row = cls(
            receipt_id=str(state['receipt_id']),
            patch_id=str(state['patch_id']),
            ready=bool(state['ready']),
            reasons=tuple(str(x) for x in state.get('reasons', ())),
            verification=verification,
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('coding readiness receipt digest mismatch')
        return row


class CodingControlPlane:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        ledger: Any,
        tasks: TaskGraph,
        evolution: SkillEvolutionEngine,
        planning: PlanningControlPlane,
        architecture: ArchitectureControlPlane,
        integration: Any = None,
        profiles: CodingProfileRegistry | None = None,
        claims: CodeClaimLedger | None = None,
        patches: CodingPatchLedger | None = None,
        requests: Mapping[str, CodingWorkRequest] | None = None,
        assignments: Mapping[str, CodingAssignmentReceipt] | None = None,
        readiness: tuple[CodingReadinessReceipt, ...] = (),
        readiness_counter: int = 0,
    ) -> None:
        self.registry = registry
        self.ledger = ledger
        self.tasks = tasks
        self.evolution = evolution
        self.planning = planning
        self.architecture = architecture
        self.integration = integration
        self.profiles = profiles or CodingProfileRegistry(registry)
        self.claims = claims or CodeClaimLedger()
        self.patches = patches or CodingPatchLedger(self.claims)
        self._requests = dict(requests or {})
        self._assignments = dict(assignments or {})
        self._readiness: list[CodingReadinessReceipt] = list(readiness)
        self._readiness_counter = int(readiness_counter)

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def requests(self) -> tuple[CodingWorkRequest, ...]:
        return tuple(self._requests[key] for key in sorted(self._requests))

    def assignments(self) -> tuple[CodingAssignmentReceipt, ...]:
        return tuple(self._assignments[key] for key in sorted(self._assignments))

    def readiness_receipts(self) -> tuple[CodingReadinessReceipt, ...]:
        return tuple(self._readiness)

    def request_work(
        self,
        request: CodingWorkRequest,
        *,
        override_agent_id: str | None = None,
        override_actor_id: str | None = None,
    ) -> CodingAssignmentReceipt:
        self.registry.get(request.requester_agent_id)
        task = self.tasks.get(request.task_id)
        if task.plan_node_id != request.plan_node_id:
            raise ValueError('coding work plan node does not match TaskGraph record')
        existing_request = self._requests.get(request.work_id)
        if existing_request is not None and existing_request != request:
            raise ValueError('coding work id cannot be rebound to different request')
        existing_assignment = self._assignments.get(request.work_id)
        if existing_request == request and existing_assignment is not None and override_agent_id is None:
            return existing_assignment
        receipt = self.profiles.route(
            request,
            override_agent_id=override_agent_id,
            override_actor_id=override_actor_id,
        )
        self._requests[request.work_id] = request
        self._assignments[request.work_id] = receipt
        selected = self.registry.get(receipt.selected_agent_id)
        self.ledger.append(
            EventKind.TASK_ASSIGNED,
            source_agent_id=request.requester_agent_id,
            target_agent_id=receipt.selected_agent_id,
            region=selected.region,
            evidence_refs=request.evidence_refs,
            payload={
                'coding_action': 'assignment',
                'work_id': request.work_id,
                'task_id': request.task_id,
                'assignment_digest': receipt.digest,
                'plan_version': request.plan_version,
                'architecture_version': request.architecture_version,
            },
        )
        return receipt

    def claim_sources(
        self,
        *,
        agent_id: str,
        task_id: str,
        file_paths: tuple[str, ...] = (),
        symbol_ids: tuple[str, ...] = (),
        directory_prefixes: tuple[str, ...] = (),
        mode: ClaimMode = ClaimMode.EXCLUSIVE_WRITE,
    ) -> CodeClaim:
        self.profiles.get(agent_id)
        task = self.tasks.get(task_id)
        if task.leased_to != str(agent_id):
            raise PermissionError('source claim requires current task lease')
        row = self.claims.claim(
            agent_id=agent_id,
            task_id=task_id,
            file_paths=file_paths,
            symbol_ids=symbol_ids,
            directory_prefixes=directory_prefixes,
            mode=mode,
        )
        self.ledger.append(
            EventKind.TASK_PROGRESS,
            source_agent_id=str(agent_id),
            target_agent_id='coding.chief',
            region=self.registry.get(agent_id).region,
            object_refs=(row.claim_id,),
            payload={
                'coding_action': 'source_claim',
                'claim_id': row.claim_id,
                'task_id': row.task_id,
                'mode': row.mode.value,
                'file_paths': list(row.file_paths),
                'symbol_ids': list(row.symbol_ids),
                'directory_prefixes': list(row.directory_prefixes),
            },
        )
        return row

    def submit_patch(
        self,
        *,
        producer_agent_id: str,
        task_id: str,
        work_id: str,
        touched_files: tuple[str, ...] = (),
        touched_symbols: tuple[str, ...] = (),
        patch_artifact_id: str,
        compile_evidence_refs: tuple[str, ...] = (),
        test_evidence_refs: tuple[str, ...] = (),
        static_evidence_refs: tuple[str, ...] = (),
        known_risks: tuple[str, ...] = (),
        plan_gap_event_refs: tuple[str, ...] = (),
        architecture_concern_event_refs: tuple[str, ...] = (),
    ) -> CodingPatchCandidate:
        request = self._requests.get(str(work_id))
        assignment = self._assignments.get(str(work_id))
        if request is None or assignment is None:
            raise KeyError(f'unknown coding work assignment: {work_id}')
        if request.task_id != str(task_id):
            raise ValueError('patch task does not match coding work request')
        if assignment.selected_agent_id != str(producer_agent_id):
            raise PermissionError('patch producer is not the selected coding assignee')
        task = self.tasks.get(task_id)
        if task.leased_to != str(producer_agent_id):
            raise PermissionError('patch producer must own current task lease')
        row = self.patches.register_patch(
            producer_agent_id=producer_agent_id,
            task_id=task_id,
            work_id=work_id,
            base_plan_version=request.plan_version,
            base_architecture_version=request.architecture_version,
            touched_files=touched_files,
            touched_symbols=touched_symbols,
            patch_artifact_id=patch_artifact_id,
            compile_evidence_refs=compile_evidence_refs,
            test_evidence_refs=test_evidence_refs,
            static_evidence_refs=static_evidence_refs,
            known_risks=known_risks,
            plan_gap_event_refs=plan_gap_event_refs,
            architecture_concern_event_refs=architecture_concern_event_refs,
        )
        self.ledger.append(
            EventKind.EVIDENCE_ADDED,
            source_agent_id=str(producer_agent_id),
            target_agent_id='coding.chief',
            region=self.registry.get(producer_agent_id).region,
            object_refs=(row.patch_id, row.patch_artifact_id),
            evidence_refs=row.compile_evidence_refs + row.test_evidence_refs + row.static_evidence_refs,
            payload={
                'coding_action': 'patch_submitted',
                'patch_id': row.patch_id,
                'task_id': row.task_id,
                'work_id': row.work_id,
                'status': row.status.value,
            },
        )
        return row

    def assess_readiness(
        self,
        patch_id: str,
        verification: PatchVerificationEvidence,
    ) -> CodingReadinessReceipt:
        patch = self.patches.get_patch(patch_id)
        reasons: list[str] = []
        task = self.tasks.get(patch.task_id)
        if task.leased_to != patch.producer_agent_id:
            reasons.append('task_lease_mismatch')
        if patch.base_plan_version != int(self.planning.graph.version):
            reasons.append('stale_plan_version')
        if patch.base_architecture_version != int(self.architecture.graph.version):
            reasons.append('stale_architecture_version')
        if not self.patches.claim_coverage(patch.patch_id):
            reasons.append('unclaimed_source_scope')
        if not patch.compile_evidence_refs:
            reasons.append('missing_compile_evidence')
        if not patch.test_evidence_refs:
            reasons.append('missing_test_evidence')

        verifier = self.registry.get(verification.verifier_agent_id)
        if verification.verifier_agent_id == patch.producer_agent_id:
            reasons.append('self_verification_forbidden')
        if verifier.region != 'verification-testing':
            reasons.append('invalid_verifier_authority')
        if not verification.passed:
            reasons.append('verification_failed')
        if verification.false_accepts:
            reasons.append('verification_false_accepts')
        if verification.regressions:
            reasons.append('verification_regressions')

        ready = not reasons
        self._readiness_counter += 1
        receipt_id = f'coding-ready-{self._readiness_counter:08d}'
        payload = {
            'receipt_id': receipt_id,
            'patch_id': patch.patch_id,
            'ready': ready,
            'reasons': reasons,
            'verification': verification.to_state(),
        }
        row = CodingReadinessReceipt(
            receipt_id=receipt_id,
            patch_id=patch.patch_id,
            ready=ready,
            reasons=tuple(reasons),
            verification=verification,
            digest=canonical_digest(payload),
        )
        self._readiness.append(row)
        self.patches.set_status(
            patch.patch_id,
            CodingPatchStatus.VERIFIED if ready else (
                CodingPatchStatus.REJECTED
                if any(reason.startswith('verification_') or reason == 'self_verification_forbidden' for reason in reasons)
                else patch.status
            ),
        )
        self.ledger.append(
            EventKind.TEST_PASSED if ready else EventKind.VERIFICATION_REJECTED,
            source_agent_id=verification.verifier_agent_id,
            target_agent_id=patch.producer_agent_id,
            region=self.registry.get(patch.producer_agent_id).region,
            object_refs=(patch.patch_id,),
            evidence_refs=(verification.evidence_id,),
            payload={
                'coding_action': 'readiness_assessed',
                'receipt_id': row.receipt_id,
                'patch_id': patch.patch_id,
                'ready': ready,
                'reasons': list(row.reasons),
            },
        )
        return row

    def report_plan_gap(
        self,
        *,
        source_agent_id: str,
        task_id: str,
        reason: str,
        suggested_nodes: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ):
        self.profiles.get(source_agent_id)
        return self.tasks.propose_plan_gap(
            source_agent_id=source_agent_id,
            task_id=task_id,
            reason=reason,
            suggested_nodes=suggested_nodes,
            evidence_ids=evidence_refs,
        )

    def report_architecture_concern(
        self,
        *,
        source_agent_id: str,
        component_refs: tuple[str, ...],
        observation: str,
        alternatives: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        severity: int,
    ):
        self.profiles.get(source_agent_id)
        return self.architecture.propose_concern(
            source_agent_id=source_agent_id,
            component_refs=component_refs,
            observation=observation,
            alternatives=alternatives,
            evidence_refs=evidence_refs,
            severity=severity,
        )

    def propose_personal_skill_from_patch(
        self,
        patch_id: str,
        *,
        name: str,
        body: str,
    ) -> SkillRecord:
        patch = self.patches.get_patch(patch_id)
        identity = self.registry.get(patch.producer_agent_id)
        skill = self.evolution.propose(
            owner_agent_id=patch.producer_agent_id,
            region=identity.region,
            name=name,
            body=body,
        )
        self.ledger.append(
            EventKind.SKILL_CANDIDATE,
            source_agent_id=patch.producer_agent_id,
            target_agent_id=patch.producer_agent_id,
            region=identity.region,
            object_refs=(skill.skill_id, patch.patch_id),
            payload={
                'coding_action': 'personal_skill_candidate',
                'skill_id': skill.skill_id,
                'patch_id': patch.patch_id,
            },
        )
        return skill

    def to_state(self) -> dict[str, Any]:
        return {
            'profiles': self.profiles.to_state(),
            'requests': [row.to_state() for row in self.requests()],
            'assignments': [row.to_state() for row in self.assignments()],
            'claims': self.claims.to_state(),
            'patches': self.patches.to_state(),
            'readiness': [row.to_state() for row in self._readiness],
            'readiness_counter': self._readiness_counter,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        ledger: Any,
        tasks: TaskGraph,
        evolution: SkillEvolutionEngine,
        planning: PlanningControlPlane,
        architecture: ArchitectureControlPlane,
        integration: Any = None,
        state: Mapping[str, Any],
    ) -> 'CodingControlPlane':
        profiles = CodingProfileRegistry.from_state(registry, state.get('profiles', {}))
        claims = CodeClaimLedger.from_state(state.get('claims', {}))
        patches = CodingPatchLedger.from_state(claims=claims, state=state.get('patches', {}))
        requests: dict[str, CodingWorkRequest] = {}
        for value in state.get('requests', ()):
            row = CodingWorkRequest.from_state(value)
            if row.work_id in requests:
                raise ValueError('duplicate coding work id in snapshot')
            requests[row.work_id] = row
        assignments: dict[str, CodingAssignmentReceipt] = {}
        for value in state.get('assignments', ()):
            row = CodingAssignmentReceipt.from_state(value)
            if row.work_id in assignments:
                raise ValueError('duplicate coding assignment in snapshot')
            assignments[row.work_id] = row
        if set(assignments) != set(requests):
            raise ValueError('coding requests/assignments snapshot mismatch')
        for work_id, receipt in assignments.items():
            profiles.get(receipt.selected_agent_id)
            if receipt.architecture_version != requests[work_id].architecture_version or receipt.plan_version != requests[work_id].plan_version:
                raise ValueError('coding assignment authoritative version mismatch')
        readiness = tuple(CodingReadinessReceipt.from_state(x) for x in state.get('readiness', ()))
        for row in readiness:
            patches.get_patch(row.patch_id)
            registry.get(row.verification.verifier_agent_id)
        counter = int(state.get('readiness_counter', len(readiness)))
        max_counter = 0
        for row in readiness:
            try:
                max_counter = max(max_counter, int(row.receipt_id.rsplit('-', 1)[1]))
            except Exception as exc:
                raise ValueError('non-canonical coding readiness id') from exc
        if counter < max_counter:
            raise ValueError('coding readiness counter is behind history')
        return cls(
            registry=registry,
            ledger=ledger,
            tasks=tasks,
            evolution=evolution,
            planning=planning,
            architecture=architecture,
            integration=integration,
            profiles=profiles,
            claims=claims,
            patches=patches,
            requests=requests,
            assignments=assignments,
            readiness=readiness,
            readiness_counter=counter,
        )
