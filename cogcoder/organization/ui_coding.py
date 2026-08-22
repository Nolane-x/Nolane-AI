from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from .coding import CodingControlPlane
from .coding_patches import CodingPatchCandidate
from .coding_profiles import CodingWorkRequest
from .types import EventKind, canonical_digest


class CrossRegionGrantStatus(str, Enum):
    ACTIVE = 'active'
    REVOKED = 'revoked'


@dataclass(frozen=True, slots=True)
class CrossRegionCodingGrant:
    grant_id: str
    agent_id: str
    task_id: str
    actor_agent_id: str
    reason: str
    evidence_refs: tuple[str, ...]
    status: CrossRegionGrantStatus
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'grant_id': self.grant_id, 'agent_id': self.agent_id, 'task_id': self.task_id,
            'actor_agent_id': self.actor_agent_id, 'reason': self.reason,
            'evidence_refs': list(self.evidence_refs), 'status': self.status.value,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CrossRegionCodingGrant':
        row = cls(
            grant_id=str(state['grant_id']), agent_id=str(state['agent_id']), task_id=str(state['task_id']),
            actor_agent_id=str(state['actor_agent_id']), reason=str(state['reason']),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            status=CrossRegionGrantStatus(str(state['status'])), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('cross-region coding grant digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ExternalCodingAssignmentReceipt:
    work_id: str
    selected_agent_id: str
    grant_id: str
    architecture_version: int
    plan_version: int
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'work_id': self.work_id, 'selected_agent_id': self.selected_agent_id,
            'grant_id': self.grant_id, 'architecture_version': self.architecture_version,
            'plan_version': self.plan_version,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ExternalCodingAssignmentReceipt':
        row = cls(
            work_id=str(state['work_id']), selected_agent_id=str(state['selected_agent_id']),
            grant_id=str(state['grant_id']), architecture_version=int(state['architecture_version']),
            plan_version=int(state['plan_version']), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('external coding assignment digest mismatch')
        return row


class UICodingControlPlane(CodingControlPlane):
    def __init__(
        self,
        *,
        external_grants: Mapping[str, CrossRegionCodingGrant] | None = None,
        external_requests: Mapping[str, CodingWorkRequest] | None = None,
        external_assignments: Mapping[str, ExternalCodingAssignmentReceipt] | None = None,
        external_grant_counter: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._external_grants = dict(external_grants or {})
        self._external_requests = dict(external_requests or {})
        self._external_assignments = dict(external_assignments or {})
        self._external_grant_counter = int(external_grant_counter)

    def external_grants(self) -> tuple[CrossRegionCodingGrant, ...]:
        return tuple(self._external_grants[key] for key in sorted(self._external_grants))

    def external_assignments(self) -> tuple[ExternalCodingAssignmentReceipt, ...]:
        return tuple(self._external_assignments[key] for key in sorted(self._external_assignments))

    def grant_external_coder(
        self, *, agent_id: str, task_id: str, actor_agent_id: str, reason: str,
        evidence_refs: tuple[str, ...],
    ) -> CrossRegionCodingGrant:
        if actor_agent_id not in {'coding.chief', 'nolane.central'}:
            raise PermissionError('cross-region coding grant requires Coding Chief or Nolane Central')
        identity = self.registry.get(agent_id)
        self.registry.get(actor_agent_id)
        if identity.region != 'frontend-ui':
            raise PermissionError('Part-VII cross-region coding grants are limited to frontend-ui identities')
        self.tasks.get(task_id)
        if not str(reason).strip() or not evidence_refs:
            raise ValueError('cross-region coding grant requires reason and evidence')
        self._external_grant_counter += 1
        grant_id = f'coding-external-grant-{self._external_grant_counter:08d}'
        payload = {
            'grant_id': grant_id, 'agent_id': str(agent_id), 'task_id': str(task_id),
            'actor_agent_id': str(actor_agent_id), 'reason': str(reason),
            'evidence_refs': list(evidence_refs), 'status': CrossRegionGrantStatus.ACTIVE.value,
        }
        row = CrossRegionCodingGrant(
            grant_id, str(agent_id), str(task_id), str(actor_agent_id), str(reason), tuple(evidence_refs),
            CrossRegionGrantStatus.ACTIVE, canonical_digest(payload),
        )
        self._external_grants[row.grant_id] = row
        self.ledger.append(
            EventKind.TASK_PROGRESS, source_agent_id=actor_agent_id, target_agent_id=agent_id,
            region=identity.region, evidence_refs=row.evidence_refs, object_refs=(row.grant_id,),
            payload={'coding_action': 'external_grant_issued', 'grant_id': row.grant_id, 'task_id': row.task_id},
        )
        return row

    def revoke_external_grant(self, grant_id: str, *, actor_agent_id: str, reason: str) -> CrossRegionCodingGrant:
        if actor_agent_id not in {'coding.chief', 'nolane.central'}:
            raise PermissionError('cross-region coding revocation requires Coding Chief or Nolane Central')
        try:
            old = self._external_grants[str(grant_id)]
        except KeyError as exc:
            raise KeyError(f'unknown cross-region coding grant: {grant_id}') from exc
        if not str(reason).strip():
            raise ValueError('grant revocation reason must be explicit')
        if old.status is CrossRegionGrantStatus.REVOKED:
            return old
        payload = {**old.payload(), 'status': CrossRegionGrantStatus.REVOKED.value, 'reason': old.reason}
        row = replace(old, status=CrossRegionGrantStatus.REVOKED, digest=canonical_digest(payload))
        self._external_grants[row.grant_id] = row
        self.ledger.append(
            EventKind.TASK_PROGRESS, source_agent_id=actor_agent_id, target_agent_id=row.agent_id,
            region='frontend-ui', object_refs=(row.grant_id,),
            payload={'coding_action': 'external_grant_revoked', 'grant_id': row.grant_id, 'task_id': row.task_id, 'reason': str(reason)},
        )
        return row

    def _active_grant(self, grant_id: str, *, agent_id: str, task_id: str, require_lease: bool) -> CrossRegionCodingGrant:
        try:
            row = self._external_grants[str(grant_id)]
        except KeyError as exc:
            raise PermissionError('unknown external coding grant') from exc
        if row.status is not CrossRegionGrantStatus.ACTIVE or row.agent_id != str(agent_id) or row.task_id != str(task_id):
            raise PermissionError('external coding grant is inactive or out of scope')
        task = self.tasks.get(task_id)
        if task.completed_by is not None or task.aborted_by is not None:
            raise PermissionError('external coding grant task is no longer active')
        if require_lease and task.leased_to != str(agent_id):
            raise PermissionError('external coding grant requires current task lease')
        return row

    def has_active_external_grant(self, agent_id: str, task_id: str | None) -> bool:
        if task_id is None:
            return False
        for row in self._external_grants.values():
            if row.agent_id == str(agent_id) and row.task_id == str(task_id) and row.status is CrossRegionGrantStatus.ACTIVE:
                try:
                    self._active_grant(row.grant_id, agent_id=agent_id, task_id=task_id, require_lease=True)
                    return True
                except PermissionError:
                    continue
        return False

    def request_external_work(
        self, request: CodingWorkRequest, *, assignee_agent_id: str, grant_id: str,
    ) -> ExternalCodingAssignmentReceipt:
        self.registry.get(request.requester_agent_id)
        identity = self.registry.get(assignee_agent_id)
        if identity.region != 'frontend-ui':
            raise PermissionError('external coding assignment requires frontend-ui assignee')
        task = self.tasks.get(request.task_id)
        if task.plan_node_id != request.plan_node_id:
            raise ValueError('external coding work plan node does not match TaskGraph')
        self._active_grant(grant_id, agent_id=assignee_agent_id, task_id=request.task_id, require_lease=True)
        if request.work_id in self._requests or request.work_id in self._external_requests:
            existing = self._external_requests.get(request.work_id)
            existing_assignment = self._external_assignments.get(request.work_id)
            if existing == request and existing_assignment is not None:
                return existing_assignment
            raise ValueError('coding work id cannot be rebound')
        payload = {
            'work_id': request.work_id, 'selected_agent_id': str(assignee_agent_id), 'grant_id': str(grant_id),
            'architecture_version': request.architecture_version, 'plan_version': request.plan_version,
        }
        row = ExternalCodingAssignmentReceipt(
            request.work_id, str(assignee_agent_id), str(grant_id), request.architecture_version,
            request.plan_version, canonical_digest(payload),
        )
        self._external_requests[request.work_id] = request
        self._external_assignments[request.work_id] = row
        self.ledger.append(
            EventKind.TASK_ASSIGNED, source_agent_id=request.requester_agent_id, target_agent_id=assignee_agent_id,
            region=identity.region, evidence_refs=request.evidence_refs, object_refs=(grant_id,),
            payload={
                'coding_action': 'external_assignment', 'work_id': request.work_id, 'task_id': request.task_id,
                'grant_id': grant_id, 'assignment_digest': row.digest,
            },
        )
        return row

    def _grant_for_agent_task(self, agent_id: str, task_id: str) -> CrossRegionCodingGrant:
        candidates = [
            row for row in self._external_grants.values()
            if row.agent_id == str(agent_id) and row.task_id == str(task_id) and row.status is CrossRegionGrantStatus.ACTIVE
        ]
        if not candidates:
            raise PermissionError('agent is neither a core coder nor an active external coder')
        candidates.sort(key=lambda x: x.grant_id)
        return self._active_grant(candidates[-1].grant_id, agent_id=agent_id, task_id=task_id, require_lease=True)

    def claim_sources(self, *, agent_id: str, task_id: str, **kwargs: Any):
        try:
            self.profiles.get(agent_id)
            return super().claim_sources(agent_id=agent_id, task_id=task_id, **kwargs)
        except KeyError:
            self._grant_for_agent_task(agent_id, task_id)
        task = self.tasks.get(task_id)
        if task.leased_to != str(agent_id):
            raise PermissionError('source claim requires current task lease')
        row = self.claims.claim(agent_id=agent_id, task_id=task_id, **kwargs)
        self.ledger.append(
            EventKind.TASK_PROGRESS, source_agent_id=str(agent_id), target_agent_id='coding.chief',
            region=self.registry.get(agent_id).region, object_refs=(row.claim_id,),
            payload={
                'coding_action': 'external_source_claim', 'claim_id': row.claim_id, 'task_id': row.task_id,
                'mode': row.mode.value, 'file_paths': list(row.file_paths), 'symbol_ids': list(row.symbol_ids),
                'directory_prefixes': list(row.directory_prefixes),
            },
        )
        return row

    def submit_patch(self, *, producer_agent_id: str, task_id: str, work_id: str, **kwargs: Any) -> CodingPatchCandidate:
        if str(work_id) not in self._external_assignments:
            return super().submit_patch(producer_agent_id=producer_agent_id, task_id=task_id, work_id=work_id, **kwargs)
        request = self._external_requests[str(work_id)]
        assignment = self._external_assignments[str(work_id)]
        if assignment.selected_agent_id != str(producer_agent_id) or request.task_id != str(task_id):
            raise PermissionError('external patch producer/task does not match assignment')
        self._active_grant(assignment.grant_id, agent_id=producer_agent_id, task_id=task_id, require_lease=True)
        patch = self.patches.register_patch(
            producer_agent_id=producer_agent_id, task_id=task_id, work_id=work_id,
            base_plan_version=request.plan_version, base_architecture_version=request.architecture_version, **kwargs,
        )
        self.ledger.append(
            EventKind.EVIDENCE_ADDED, source_agent_id=producer_agent_id, target_agent_id='coding.chief',
            region='frontend-ui', object_refs=(patch.patch_id, patch.patch_artifact_id),
            evidence_refs=patch.compile_evidence_refs + patch.test_evidence_refs + patch.static_evidence_refs,
            payload={'coding_action': 'external_patch_submitted', 'patch_id': patch.patch_id, 'task_id': task_id, 'work_id': work_id},
        )
        return patch

    def assess_readiness(self, patch_id: str, verification):
        patch = self.patches.get_patch(patch_id)
        if patch.work_id in self._external_assignments:
            assignment = self._external_assignments[patch.work_id]
            self._active_grant(assignment.grant_id, agent_id=patch.producer_agent_id, task_id=patch.task_id, require_lease=True)
        return super().assess_readiness(patch_id, verification)

    def to_state(self) -> dict[str, Any]:
        state = super().to_state()
        state.update({
            'external_grants': [x.to_state() for x in self.external_grants()],
            'external_requests': [self._external_requests[key].to_state() for key in sorted(self._external_requests)],
            'external_assignments': [x.to_state() for x in self.external_assignments()],
            'external_grant_counter': self._external_grant_counter,
        })
        return state

    @classmethod
    def from_state(cls, *, state: Mapping[str, Any], **kwargs: Any) -> 'UICodingControlPlane':
        base = CodingControlPlane.from_state(state=state, **kwargs)
        grants: dict[str, CrossRegionCodingGrant] = {}
        for value in state.get('external_grants', ()):
            row = CrossRegionCodingGrant.from_state(value)
            if row.grant_id in grants:
                raise ValueError('duplicate external coding grant id')
            identity = base.registry.get(row.agent_id)
            if identity.region != 'frontend-ui' or row.actor_agent_id not in {'coding.chief', 'nolane.central'}:
                raise ValueError('invalid external coding grant authority')
            base.tasks.get(row.task_id)
            grants[row.grant_id] = row
        requests: dict[str, CodingWorkRequest] = {}
        for value in state.get('external_requests', ()):
            row = CodingWorkRequest.from_state(value)
            if row.work_id in requests or row.work_id in base._requests:
                raise ValueError('duplicate external coding work id')
            requests[row.work_id] = row
        assignments: dict[str, ExternalCodingAssignmentReceipt] = {}
        for value in state.get('external_assignments', ()):
            row = ExternalCodingAssignmentReceipt.from_state(value)
            if row.work_id in assignments:
                raise ValueError('duplicate external coding assignment')
            request = requests.get(row.work_id)
            grant = grants.get(row.grant_id)
            if request is None or grant is None or row.selected_agent_id != grant.agent_id or request.task_id != grant.task_id:
                raise ValueError('external coding assignment provenance mismatch')
            if row.architecture_version != request.architecture_version or row.plan_version != request.plan_version:
                raise ValueError('external coding assignment authoritative version mismatch')
            assignments[row.work_id] = row
        if set(assignments) != set(requests):
            raise ValueError('external coding requests/assignments snapshot mismatch')
        max_counter = 0
        for row in grants.values():
            try:
                max_counter = max(max_counter, int(row.grant_id.rsplit('-', 1)[1]))
            except Exception as exc:
                raise ValueError('non-canonical external coding grant id') from exc
        counter = int(state.get('external_grant_counter', max_counter))
        if counter < max_counter:
            raise ValueError('external coding grant counter is behind history')
        return cls(
            registry=base.registry, ledger=base.ledger, tasks=base.tasks, evolution=base.evolution,
            planning=base.planning, architecture=base.architecture, integration=base.integration,
            profiles=base.profiles, claims=base.claims, patches=base.patches,
            requests=base._requests, assignments=base._assignments,
            readiness=tuple(base._readiness), readiness_counter=base._readiness_counter,
            external_grants=grants, external_requests=requests, external_assignments=assignments,
            external_grant_counter=counter,
        )
