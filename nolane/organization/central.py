from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from cogcoder.organization.types import AgentStatus, EventKind

from .central_access import CentralCoreAccessPolicy, CoreLease
from .central_conflicts import CentralConflictPacket, CentralConflictRegistry
from .central_resources import CentralResourceArbiter, ResourceAllocationReceipt, ResourceReleaseReceipt
from .central_state import CentralCapabilityMap, CentralWorldState, build_world_state


# Part II is stacked on the Part-I snapshot schema. Until the shared event
# vocabulary receives its own schema migration, Central organizational actions
# preserve the accepted runtime aliases of CENTRAL_INTERVENTION and carry the
# specific action subtype in immutable event payloads.
for _name in (
    'CENTRAL_RESOURCE_ALLOCATED', 'CENTRAL_RESOURCE_RELEASED',
    'CENTRAL_CONFLICT_OPENED', 'CENTRAL_CONFLICT_RESOLVED',
    'CENTRAL_DIRECT_WORK', 'CENTRAL_CORE_LEASE_GRANTED', 'CENTRAL_CORE_LEASE_REVOKED',
):
    if not hasattr(EventKind, _name):
        setattr(EventKind, _name, EventKind.CENTRAL_INTERVENTION)


DEFAULT_CENTRAL_RESOURCE_CAPACITY = {
    'compute': 1_000,
    'agent_slots': 16,
    'tool_calls': 10_000,
    'external_core_calls': 1_000,
}


@dataclass(frozen=True, slots=True)
class CentralDirectWorkReceipt:
    receipt_id: str
    task_id: str
    producer_agent_id: str
    artifact_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    event_id: str

    def to_state(self) -> dict[str, Any]:
        return {
            'receipt_id': self.receipt_id, 'task_id': self.task_id,
            'producer_agent_id': self.producer_agent_id, 'artifact_ids': list(self.artifact_ids),
            'evidence_refs': list(self.evidence_refs), 'event_id': self.event_id,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CentralDirectWorkReceipt':
        return cls(
            receipt_id=str(state['receipt_id']), task_id=str(state['task_id']),
            producer_agent_id=str(state['producer_agent_id']),
            artifact_ids=tuple(str(x) for x in state.get('artifact_ids', ())),
            evidence_refs=tuple(str(x) for x in state.get('evidence_refs', ())),
            event_id=str(state['event_id']),
        )


class CentralControlPlane:
    def __init__(self, *, registry: Any, ledger: Any, authority: Any, tasks: Any, scheduler: Any,
                 artifacts: Any, external_cores: Any, self_models: Any, evolution: Any,
                 verification: Any, capabilities: CentralCapabilityMap | None = None,
                 resources: CentralResourceArbiter | None = None,
                 conflicts: CentralConflictRegistry | None = None,
                 core_access: CentralCoreAccessPolicy | None = None,
                 direct_work_receipts: tuple[CentralDirectWorkReceipt, ...] = (),
                 direct_work_counter: int = 0) -> None:
        central = registry.get('nolane.central')
        if not central.direct_work_capable:
            raise ValueError('Nolane Central must remain direct-work capable')
        self.registry = registry
        self.ledger = ledger
        self.authority = authority
        self.tasks = tasks
        self.scheduler = scheduler
        self.artifacts = artifacts
        self.external_cores = external_cores
        self.self_models = self_models
        self.evolution = evolution
        self.verification = verification
        self.capabilities = capabilities or CentralCapabilityMap(registry)
        self.resources = resources or CentralResourceArbiter(DEFAULT_CENTRAL_RESOURCE_CAPACITY)
        self.conflicts = conflicts or CentralConflictRegistry()
        self.core_access = core_access or CentralCoreAccessPolicy(registry, external_cores)
        self._direct_work_receipts = list(direct_work_receipts)
        self._direct_work_counter = int(direct_work_counter)
        if self._direct_work_counter != len(self._direct_work_receipts):
            raise ValueError('Central direct-work counter is not canonical')

    @staticmethod
    def _evidence(values: tuple[str, ...], *, required: bool) -> tuple[str, ...]:
        rows = tuple(str(x).strip() for x in values if str(x).strip())
        if required and not rows:
            raise ValueError('state-changing Central action requires evidence refs')
        return rows

    def _emit_action(self, kind: EventKind, *, target_agent_id: str, directive: str,
                     evidence_refs: tuple[str, ...] = (), evidence_required: bool):
        target = self.registry.get(target_agent_id)
        directive = str(directive).strip()
        if not directive:
            raise ValueError('Central directive must be explicit')
        evidence = self._evidence(evidence_refs, required=evidence_required)
        event = self.ledger.append(
            kind, source_agent_id='nolane.central', target_agent_id=target.agent_id,
            region=target.region, evidence_refs=evidence, priority=100, requires_ack=True,
            payload={'directive': directive, 'region_chief_id': target.region_chief_id},
        )
        self.scheduler.notify_event(event)
        return event

    def question(self, *, target_agent_id: str, directive: str, evidence_refs: tuple[str, ...] = ()):
        return self._emit_action(EventKind.CENTRAL_QUESTION, target_agent_id=target_agent_id,
                                 directive=directive, evidence_refs=evidence_refs, evidence_required=False)

    def correct(self, *, target_agent_id: str, directive: str, evidence_refs: tuple[str, ...]):
        return self._emit_action(EventKind.CENTRAL_CORRECTION, target_agent_id=target_agent_id,
                                 directive=directive, evidence_refs=evidence_refs, evidence_required=True)

    def redirect(self, *, target_agent_id: str, directive: str, evidence_refs: tuple[str, ...]):
        return self._emit_action(EventKind.CENTRAL_REDIRECT, target_agent_id=target_agent_id,
                                 directive=directive, evidence_refs=evidence_refs, evidence_required=True)

    def pause(self, *, target_agent_id: str, directive: str, evidence_refs: tuple[str, ...]):
        event = self._emit_action(EventKind.CENTRAL_PAUSE, target_agent_id=target_agent_id,
                                  directive=directive, evidence_refs=evidence_refs, evidence_required=True)
        self.registry.set_status(target_agent_id, AgentStatus.PAUSED)
        return event

    def abort(self, *, target_agent_id: str, directive: str, evidence_refs: tuple[str, ...]):
        target = self.registry.get(target_agent_id)
        evidence = self._evidence(evidence_refs, required=True)
        directive = str(directive).strip()
        if not directive:
            raise ValueError('Central directive must be explicit')
        if target.current_task is not None:
            self.tasks.abort(target.current_task, 'nolane.central', reason=directive)
        self.registry.set_status(target_agent_id, AgentStatus.PAUSED)
        event = self.ledger.append(
            EventKind.CENTRAL_ABORT, source_agent_id='nolane.central', target_agent_id=target.agent_id,
            region=target.region, evidence_refs=evidence, priority=100, requires_ack=True,
            payload={'directive': directive, 'region_chief_id': target.region_chief_id},
        )
        self.scheduler.notify_event(event)
        return event

    def request_evidence(self, *, target_agent_id: str, directive: str,
                         evidence_refs: tuple[str, ...] = ()):
        return self._emit_action(EventKind.CENTRAL_REQUEST_EVIDENCE, target_agent_id=target_agent_id,
                                 directive=directive, evidence_refs=evidence_refs, evidence_required=False)

    def allocate_resource(self, *, beneficiary: str, resource: str, amount: int, reason: str,
                          evidence_refs: tuple[str, ...]) -> ResourceAllocationReceipt:
        identity = self.registry.get(beneficiary)
        receipt = self.resources.allocate(beneficiary=beneficiary, resource=resource, amount=amount,
                                          reason=reason, evidence_refs=evidence_refs)
        event = self.ledger.append(
            EventKind.CENTRAL_RESOURCE_ALLOCATED, source_agent_id='nolane.central',
            target_agent_id=beneficiary, region=identity.region, evidence_refs=receipt.evidence_refs,
            payload={'central_action': 'resource_allocated', **receipt.to_state()},
        )
        self.scheduler.notify_event(event)
        return receipt

    def release_resource(self, allocation_id: str, *, amount: int, reason: str,
                         evidence_refs: tuple[str, ...]) -> ResourceReleaseReceipt:
        receipt = self.resources.release(allocation_id, amount=amount, reason=reason, evidence_refs=evidence_refs)
        event = self.ledger.append(
            EventKind.CENTRAL_RESOURCE_RELEASED, source_agent_id='nolane.central',
            target_agent_id=receipt.beneficiary, region=self.registry.get(receipt.beneficiary).region,
            evidence_refs=receipt.evidence_refs,
            payload={'central_action': 'resource_released', **receipt.to_state()},
        )
        self.scheduler.notify_event(event)
        return receipt

    def grant_core_lease(self, *, core_id: str, owner: str, call_budget: int,
                         expires_at_token: int, reason: str, evidence_refs: tuple[str, ...]) -> CoreLease:
        lease = self.core_access.grant_lease(core_id=core_id, owner=owner, call_budget=call_budget,
                                             expires_at_token=expires_at_token, reason=reason,
                                             evidence_refs=evidence_refs)
        self.ledger.append(
            EventKind.CENTRAL_CORE_LEASE_GRANTED, source_agent_id='nolane.central',
            evidence_refs=lease.evidence_refs, object_refs=(lease.core_id,),
            payload={'central_action': 'core_lease_granted', **lease.to_state()},
        )
        return lease

    def revoke_core_lease(self, lease_id: str, *, reason: str,
                          evidence_refs: tuple[str, ...]) -> CoreLease:
        lease = self.core_access.revoke(lease_id, reason=reason, evidence_refs=evidence_refs)
        self.ledger.append(
            EventKind.CENTRAL_CORE_LEASE_REVOKED, source_agent_id='nolane.central',
            evidence_refs=lease.revoke_evidence_refs, object_refs=(lease.core_id,),
            payload={'central_action': 'core_lease_revoked', **lease.to_state()},
        )
        return lease

    def open_conflict(self, *, submitted_by: tuple[str, ...], regions: tuple[str, ...],
                      object_refs: tuple[str, ...], claims: tuple[tuple[str, str, tuple[str, ...]], ...],
                      severity: int, affected_refs: tuple[str, ...] = ()) -> CentralConflictPacket:
        for agent_id in submitted_by:
            self.registry.get(agent_id)
        packet = self.conflicts.open(submitted_by=submitted_by, regions=regions, object_refs=object_refs,
                                     claims=claims, severity=severity, affected_refs=affected_refs)
        evidence = tuple(x for claim in packet.claims for x in claim.evidence_refs)
        self.ledger.append(
            EventKind.CENTRAL_CONFLICT_OPENED, source_agent_id='nolane.central',
            object_refs=packet.object_refs, evidence_refs=evidence, priority=packet.severity,
            payload={'central_action': 'conflict_opened', 'conflict_id': packet.conflict_id,
                     'regions': list(packet.regions)},
        )
        return packet

    def resolve_conflict(self, conflict_id: str, *, decision: str, rationale: str,
                         evidence_refs: tuple[str, ...]) -> CentralConflictPacket:
        packet = self.conflicts.resolve(conflict_id, resolver_agent_id='nolane.central', decision=decision,
                                        rationale=rationale, evidence_refs=evidence_refs)
        self.ledger.append(
            EventKind.CENTRAL_CONFLICT_RESOLVED, source_agent_id='nolane.central',
            object_refs=packet.object_refs, evidence_refs=packet.resolution_evidence_refs,
            priority=packet.severity,
            payload={'central_action': 'conflict_resolved', 'conflict_id': packet.conflict_id,
                     'decision': packet.decision, 'rationale': packet.rationale},
        )
        return packet

    def complete_direct_work(self, *, task_id: str, artifact_ids: tuple[str, ...],
                             evidence_refs: tuple[str, ...]) -> CentralDirectWorkReceipt:
        evidence = self._evidence(evidence_refs, required=True)
        artifacts = tuple(str(x).strip() for x in artifact_ids if str(x).strip())
        if not artifacts:
            raise ValueError('Central direct work requires artifact ids')
        for artifact_id in artifacts:
            artifact = self.artifacts.get(artifact_id)
            if artifact.producer_agent_id != 'nolane.central':
                raise PermissionError('Central direct-work artifact must be produced by nolane.central')
        task = self.tasks.get(task_id)
        if task.leased_to != 'nolane.central':
            raise PermissionError('Central must own the task lease before direct completion')
        self.tasks.complete(task_id, 'nolane.central', output_artifact_ids=artifacts)
        event = self.ledger.append(
            EventKind.CENTRAL_DIRECT_WORK, source_agent_id='nolane.central', target_agent_id='nolane.central',
            region='global-command', object_refs=artifacts, evidence_refs=evidence,
            payload={'central_action': 'direct_work', 'task_id': str(task_id), 'mode': 'direct_work'},
        )
        counter = self._direct_work_counter + 1
        receipt = CentralDirectWorkReceipt(
            receipt_id=f'central-work-{counter:08d}', task_id=str(task_id),
            producer_agent_id='nolane.central', artifact_ids=artifacts,
            evidence_refs=evidence, event_id=event.event_id,
        )
        self._direct_work_counter = counter
        self._direct_work_receipts.append(receipt)
        return receipt

    def direct_work_receipts(self) -> tuple[CentralDirectWorkReceipt, ...]:
        return tuple(self._direct_work_receipts)

    def _world_extra_state(self) -> dict[str, Any]:
        return {
            'resources': self.resources.to_state(), 'conflicts': self.conflicts.to_state(),
            'core_access': self.core_access.to_state(),
            'direct_work_receipts': [x.to_state() for x in self._direct_work_receipts],
            'direct_work_counter': self._direct_work_counter,
        }

    def world_state(self) -> CentralWorldState:
        runtime_view = type('_RuntimeView', (), {
            'registry': self.registry, 'tasks': self.tasks, 'authority': self.authority,
            'ledger': self.ledger, 'verification': self.verification,
        })()
        return build_world_state(runtime_view, self.capabilities, central_extra=self._world_extra_state())

    def to_state(self) -> dict[str, Any]:
        return {'capabilities': self.capabilities.to_state(), **self._world_extra_state()}

    @classmethod
    def from_state(cls, *, registry: Any, ledger: Any, authority: Any, tasks: Any, scheduler: Any,
                   artifacts: Any, external_cores: Any, self_models: Any, evolution: Any,
                   verification: Any, state: Mapping[str, Any]) -> 'CentralControlPlane':
        capabilities = CentralCapabilityMap.from_state(registry, state.get('capabilities', {}))
        resources = CentralResourceArbiter.from_state(state['resources'])
        conflicts = CentralConflictRegistry.from_state(state.get('conflicts', {}))
        core_access = CentralCoreAccessPolicy.from_state(registry, external_cores, state.get('core_access', {}))
        receipts = tuple(CentralDirectWorkReceipt.from_state(x) for x in state.get('direct_work_receipts', ()))
        counter = int(state.get('direct_work_counter', len(receipts)))
        return cls(
            registry=registry, ledger=ledger, authority=authority, tasks=tasks, scheduler=scheduler,
            artifacts=artifacts, external_cores=external_cores, self_models=self_models,
            evolution=evolution, verification=verification, capabilities=capabilities,
            resources=resources, conflicts=conflicts, core_access=core_access,
            direct_work_receipts=receipts, direct_work_counter=counter,
        )


COMPONENT_ID = 'organization.central'
COMPONENT_VERSION = '0.0.1'
MIGRATED_FROM = 'cogcoder.organization.central'
