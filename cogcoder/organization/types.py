from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest, canonical_json

from nolane.schemas.identity import (
    PHYSICAL_PARAMETER_CEILING,
    AgentIdentity,
    AgentRank,
    AgentStatus,
    ParameterAccounting,
)

from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.fabric import MemoryEntry, MemoryScope, MemoryStatus








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
