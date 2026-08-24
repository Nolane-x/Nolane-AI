from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json

from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.fabric import MemoryEntry, MemoryScope, MemoryStatus


PHYSICAL_PARAMETER_CEILING = 100_000_000


class AgentRank(str, Enum):
    CENTRAL = 'central'
    CHIEF = 'chief'
    SENIOR_SPECIALIST = 'senior_specialist'
    SPECIALIST = 'specialist'


class AgentStatus(str, Enum):
    SLEEPING = 'sleeping'
    WAKING = 'waking'
    ACTIVE = 'active'
    WAITING = 'waiting'
    BLOCKED = 'blocked'
    CHECKPOINTING = 'checkpointing'
    PAUSED = 'paused'
    QUARANTINED = 'quarantined'


class SkillScope(str, Enum):
    CANDIDATE = 'candidate'
    PERSONAL = 'personal'
    REGIONAL = 'regional'
    GLOBAL = 'global'


class EventKind(str, Enum):
    TASK_ASSIGNED = 'task_assigned'
    TASK_STARTED = 'task_started'
    TASK_PROGRESS = 'task_progress'
    TASK_BLOCKED = 'task_blocked'
    TASK_COMPLETED = 'task_completed'
    PLAN_GAP_DETECTED = 'plan_gap_detected'
    PLAN_CHANGE_PROPOSED = 'plan_change_proposed'
    PLAN_AMENDED = 'plan_amended'
    ARCHITECTURE_CONCERN = 'architecture_concern'
    BUG_DISCOVERED = 'bug_discovered'
    HYPOTHESIS_PROPOSED = 'hypothesis_proposed'
    EVIDENCE_ADDED = 'evidence_added'
    TEST_FAILED = 'test_failed'
    TEST_PASSED = 'test_passed'
    VERIFICATION_REJECTED = 'verification_rejected'
    SKILL_CANDIDATE = 'skill_candidate'
    SKILL_PROMOTED = 'skill_promoted'
    SKILL_REJECTED = 'skill_rejected'
    SKILL_QUARANTINED = 'skill_quarantined'
    MEMORY_CONFLICT = 'memory_conflict'
    MEMORY_PROMOTED = 'memory_promoted'
    CENTRAL_INTERVENTION = 'central_intervention'
    CENTRAL_QUESTION = 'central_question'
    CENTRAL_CORRECTION = 'central_correction'
    CENTRAL_REDIRECT = 'central_redirect'
    CENTRAL_PAUSE = 'central_pause'
    CENTRAL_ABORT = 'central_abort'
    CENTRAL_REQUEST_EVIDENCE = 'central_request_evidence'
    AGENT_CHECKPOINTED = 'agent_checkpointed'
    AGENT_SLEEP = 'agent_sleep'
    AGENT_WAKE = 'agent_wake'
    CHIEF_DIRECT_WORK = 'chief_direct_work'
    NEURAL_CANDIDATE_EVALUATED = 'neural_candidate_evaluated'
    NEURAL_PROMOTED = 'neural_promoted'
    NEURAL_ROLLBACK = 'neural_rollback'
    TASK_LEASE_GRANTED = 'task_lease_granted'
    TASK_LEASE_RENEWED = 'task_lease_renewed'
    TASK_LEASE_REVOKED = 'task_lease_revoked'
    COORDINATION_ACK = 'coordination_ack'
    COORDINATION_ESCALATED = 'coordination_escalated'
    CONFLICT_OPENED = 'conflict_opened'
    CONFLICT_CLAIM_ADDED = 'conflict_claim_added'
    CONFLICT_RESOLVED = 'conflict_resolved'
    WAKE_RESERVED = 'wake_reserved'
    WAKE_DEFERRED = 'wake_deferred'
    STALE_AGENT_DETECTED = 'stale_agent_detected'



@dataclass(frozen=True, slots=True)
class ParameterAccounting:
    shared_physical_parameters: int
    local_physical_parameters: int

    def __post_init__(self) -> None:
        if isinstance(self.shared_physical_parameters, bool) or isinstance(self.local_physical_parameters, bool):
            raise TypeError('parameter counts must be integers')
        if self.shared_physical_parameters < 0 or self.local_physical_parameters < 0:
            raise ValueError('parameter counts must be non-negative')
        if self.total_physical_parameters >= PHYSICAL_PARAMETER_CEILING:
            raise ValueError('first-generation physical parameters must remain below 100,000,000')

    @property
    def total_physical_parameters(self) -> int:
        return self.shared_physical_parameters + self.local_physical_parameters

    def to_state(self) -> dict[str, int]:
        return {
            'shared_physical_parameters': self.shared_physical_parameters,
            'local_physical_parameters': self.local_physical_parameters,
            'total_physical_parameters': self.total_physical_parameters,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ParameterAccounting':
        return cls(
            shared_physical_parameters=int(state['shared_physical_parameters']),
            local_physical_parameters=int(state['local_physical_parameters']),
        )


@dataclass(frozen=True, slots=True)
class AgentIdentity:
    agent_id: str
    name: str
    region: str
    role: str
    rank: AgentRank
    neural_version: str
    parameter_accounting: ParameterAccounting
    region_chief_id: str | None
    direct_work_capable: bool
    learning_capable: bool
    cognitive_capabilities: tuple[str, ...]
    memory_namespace: str
    skill_namespace: str
    external_core_bindings: tuple[str, ...] = ()
    tool_permissions: tuple[str, ...] = ()
    status: AgentStatus = AgentStatus.SLEEPING
    current_task: str | None = None
    specialization_version: str = 'specialization-0.1'
    authority_scope: tuple[str, ...] = ('task',)
    subscriptions: tuple[str, ...] = ()
    checkpoint_id: str | None = None
    self_model_version: str = 'self-model-0.1'

    def __post_init__(self) -> None:
        for value, label in (
            (self.agent_id, 'agent_id'), (self.name, 'name'), (self.region, 'region'),
            (self.role, 'role'), (self.neural_version, 'neural_version'),
            (self.memory_namespace, 'memory_namespace'), (self.skill_namespace, 'skill_namespace'),
            (self.specialization_version, 'specialization_version'), (self.self_model_version, 'self_model_version'),
        ):
            if not str(value).strip(): raise ValueError(f'{label} must be non-empty')
        if not self.cognitive_capabilities: raise ValueError('every permanent identity needs a cognitive capability floor')
        if not self.authority_scope: raise ValueError('every permanent identity needs an authority scope')
        if not self.learning_capable: raise ValueError('permanent identities must be learning capable')
        if self.rank in (AgentRank.CENTRAL, AgentRank.CHIEF) and not self.direct_work_capable:
            raise ValueError('Central and Regional Chiefs must be direct workers')
        if self.rank is AgentRank.CENTRAL and self.region_chief_id is not None: raise ValueError('Central cannot have a regional chief')
        if self.rank is AgentRank.CHIEF and self.region_chief_id != self.agent_id: raise ValueError('Regional Chief must identify itself as region chief')

    def to_state(self) -> dict[str, Any]:
        return {
            'agent_id': self.agent_id, 'name': self.name, 'region': self.region, 'role': self.role,
            'rank': self.rank.value, 'neural_version': self.neural_version,
            'parameter_accounting': self.parameter_accounting.to_state(), 'region_chief_id': self.region_chief_id,
            'direct_work_capable': self.direct_work_capable, 'learning_capable': self.learning_capable,
            'cognitive_capabilities': list(self.cognitive_capabilities), 'memory_namespace': self.memory_namespace,
            'skill_namespace': self.skill_namespace, 'external_core_bindings': list(self.external_core_bindings),
            'tool_permissions': list(self.tool_permissions), 'status': self.status.value, 'current_task': self.current_task,
            'specialization_version': self.specialization_version, 'authority_scope': list(self.authority_scope),
            'subscriptions': list(self.subscriptions), 'checkpoint_id': self.checkpoint_id,
            'self_model_version': self.self_model_version,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'AgentIdentity':
        return cls(
            agent_id=str(state['agent_id']), name=str(state['name']), region=str(state['region']), role=str(state['role']),
            rank=AgentRank(str(state['rank'])), neural_version=str(state['neural_version']),
            parameter_accounting=ParameterAccounting.from_state(state['parameter_accounting']),
            region_chief_id=None if state.get('region_chief_id') is None else str(state['region_chief_id']),
            direct_work_capable=bool(state['direct_work_capable']), learning_capable=bool(state['learning_capable']),
            cognitive_capabilities=tuple(str(row) for row in state['cognitive_capabilities']),
            memory_namespace=str(state['memory_namespace']), skill_namespace=str(state['skill_namespace']),
            external_core_bindings=tuple(str(row) for row in state.get('external_core_bindings', ())),
            tool_permissions=tuple(str(row) for row in state.get('tool_permissions', ())),
            status=AgentStatus(str(state.get('status', AgentStatus.SLEEPING.value))),
            current_task=None if state.get('current_task') is None else str(state['current_task']),
            specialization_version=str(state.get('specialization_version', 'specialization-0.1')),
            authority_scope=tuple(str(row) for row in state.get('authority_scope', ('task',))),
            subscriptions=tuple(str(row) for row in state.get('subscriptions', ())),
            checkpoint_id=None if state.get('checkpoint_id') is None else str(state['checkpoint_id']),
            self_model_version=str(state.get('self_model_version', 'self-model-0.1')),
        )


@dataclass(frozen=True, slots=True)
class CognitiveEvent:
    event_id: str
    sequence: int
    kind: EventKind
    source_agent_id: str
    target_agent_id: str | None
    region: str | None
    payload_json: str
    digest: str
    scope: str = 'organization'
    causal_parent_ids: tuple[str, ...] = ()
    object_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    priority: int = 0
    requires_ack: bool = False
    status: str = 'emitted'
    created_at_logical: int = 0

    @property
    def payload(self) -> dict[str, Any]:
        value = json.loads(self.payload_json)
        if not isinstance(value, dict): raise ValueError('event payload must decode to an object')
        return value

    def to_state(self) -> dict[str, Any]:
        return {
            'event_id': self.event_id, 'sequence': self.sequence, 'kind': self.kind.value,
            'source_agent_id': self.source_agent_id, 'target_agent_id': self.target_agent_id,
            'region': self.region, 'payload_json': self.payload_json, 'digest': self.digest,
            'scope': self.scope, 'causal_parent_ids': list(self.causal_parent_ids),
            'object_refs': list(self.object_refs), 'evidence_refs': list(self.evidence_refs),
            'priority': self.priority, 'requires_ack': self.requires_ack, 'status': self.status,
            'created_at_logical': self.created_at_logical,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CognitiveEvent':
        return cls(
            event_id=str(state['event_id']), sequence=int(state['sequence']), kind=EventKind(str(state['kind'])),
            source_agent_id=str(state['source_agent_id']),
            target_agent_id=None if state.get('target_agent_id') is None else str(state['target_agent_id']),
            region=None if state.get('region') is None else str(state['region']), payload_json=str(state['payload_json']),
            digest=str(state['digest']), scope=str(state.get('scope', 'organization')),
            causal_parent_ids=tuple(str(row) for row in state.get('causal_parent_ids', ())),
            object_refs=tuple(str(row) for row in state.get('object_refs', ())),
            evidence_refs=tuple(str(row) for row in state.get('evidence_refs', ())),
            priority=int(state.get('priority', 0)), requires_ack=bool(state.get('requires_ack', False)),
            status=str(state.get('status', 'emitted')), created_at_logical=int(state.get('created_at_logical', state.get('sequence', 0))),
        )


@dataclass(frozen=True, slots=True)
class ContextCapsule:
    agent_id: str
    task_id: str | None
    plan_version: int
    since_event_id: str | None
    memories: tuple[MemoryEntry, ...]
    event_delta: tuple[CognitiveEvent, ...]
    authoritative_artifacts: tuple[tuple[str, int], ...] = ()
    tools: tuple[str, ...] = ()
    external_cores: tuple[str, ...] = ()
    applicable_skill_ids: tuple[str, ...] = ()
    identity_summary: tuple[tuple[str, str], ...] = ()
    authority_boundary: tuple[str, ...] = ()
    semantic_delta_digest: str | None = None
    context_compilation_receipt_id: str | None = None
    context_budget_units: int = 0
    context_overload_ratio: float = 0.0
    stale_context_warnings: tuple[str, ...] = ()
