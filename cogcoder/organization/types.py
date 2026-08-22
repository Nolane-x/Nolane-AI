from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


PHYSICAL_PARAMETER_CEILING = 100_000_000


class AgentRank(str, Enum):
    CENTRAL = 'central'
    CHIEF = 'chief'
    SENIOR_SPECIALIST = 'senior_specialist'
    SPECIALIST = 'specialist'


class AgentStatus(str, Enum):
    SLEEPING = 'sleeping'
    ACTIVE = 'active'
    PAUSED = 'paused'
    BLOCKED = 'blocked'


class MemoryScope(str, Enum):
    GLOBAL = 'global'
    REGION = 'region'
    PERSONAL = 'personal'
    TASK = 'task'
    PRIVATE = 'private'


class SkillScope(str, Enum):
    CANDIDATE = 'candidate'
    PERSONAL = 'personal'
    REGIONAL = 'regional'
    GLOBAL = 'global'


class EventKind(str, Enum):
    CENTRAL_INTERVENTION = 'central_intervention'
    TASK_STARTED = 'task_started'
    TASK_COMPLETED = 'task_completed'
    TASK_BLOCKED = 'task_blocked'
    PLAN_GAP_DETECTED = 'plan_gap_detected'
    PLAN_AMENDED = 'plan_amended'
    TEST_FAILED = 'test_failed'
    VERIFICATION_REJECTED = 'verification_rejected'
    CHIEF_DIRECT_WORK = 'chief_direct_work'
    MEMORY_PROMOTED = 'memory_promoted'
    SKILL_PROMOTED = 'skill_promoted'
    SKILL_QUARANTINED = 'skill_quarantined'
    NEURAL_CANDIDATE_EVALUATED = 'neural_candidate_evaluated'
    NEURAL_PROMOTED = 'neural_promoted'
    NEURAL_ROLLBACK = 'neural_rollback'
    AGENT_SLEEP = 'agent_sleep'
    AGENT_WAKE = 'agent_wake'


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


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

    def __post_init__(self) -> None:
        for value, label in (
            (self.agent_id, 'agent_id'),
            (self.name, 'name'),
            (self.region, 'region'),
            (self.role, 'role'),
            (self.neural_version, 'neural_version'),
            (self.memory_namespace, 'memory_namespace'),
            (self.skill_namespace, 'skill_namespace'),
        ):
            if not str(value).strip():
                raise ValueError(f'{label} must be non-empty')
        if not self.cognitive_capabilities:
            raise ValueError('every permanent identity needs a cognitive capability floor')
        if not self.learning_capable:
            raise ValueError('permanent identities must be learning capable')
        if self.rank in (AgentRank.CENTRAL, AgentRank.CHIEF) and not self.direct_work_capable:
            raise ValueError('Central and Regional Chiefs must be direct workers')
        if self.rank is AgentRank.CENTRAL and self.region_chief_id is not None:
            raise ValueError('Central cannot have a regional chief')
        if self.rank is AgentRank.CHIEF and self.region_chief_id != self.agent_id:
            raise ValueError('Regional Chief must identify itself as region chief')

    def to_state(self) -> dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'name': self.name,
            'region': self.region,
            'role': self.role,
            'rank': self.rank.value,
            'neural_version': self.neural_version,
            'parameter_accounting': self.parameter_accounting.to_state(),
            'region_chief_id': self.region_chief_id,
            'direct_work_capable': self.direct_work_capable,
            'learning_capable': self.learning_capable,
            'cognitive_capabilities': list(self.cognitive_capabilities),
            'memory_namespace': self.memory_namespace,
            'skill_namespace': self.skill_namespace,
            'external_core_bindings': list(self.external_core_bindings),
            'tool_permissions': list(self.tool_permissions),
            'status': self.status.value,
            'current_task': self.current_task,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'AgentIdentity':
        return cls(
            agent_id=str(state['agent_id']),
            name=str(state['name']),
            region=str(state['region']),
            role=str(state['role']),
            rank=AgentRank(str(state['rank'])),
            neural_version=str(state['neural_version']),
            parameter_accounting=ParameterAccounting.from_state(state['parameter_accounting']),
            region_chief_id=None if state.get('region_chief_id') is None else str(state['region_chief_id']),
            direct_work_capable=bool(state['direct_work_capable']),
            learning_capable=bool(state['learning_capable']),
            cognitive_capabilities=tuple(str(row) for row in state['cognitive_capabilities']),
            memory_namespace=str(state['memory_namespace']),
            skill_namespace=str(state['skill_namespace']),
            external_core_bindings=tuple(str(row) for row in state.get('external_core_bindings', ())),
            tool_permissions=tuple(str(row) for row in state.get('tool_permissions', ())),
            status=AgentStatus(str(state.get('status', AgentStatus.SLEEPING.value))),
            current_task=None if state.get('current_task') is None else str(state['current_task']),
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

    @property
    def payload(self) -> dict[str, Any]:
        value = json.loads(self.payload_json)
        if not isinstance(value, dict):
            raise ValueError('event payload must decode to an object')
        return value

    def to_state(self) -> dict[str, Any]:
        return {
            'event_id': self.event_id,
            'sequence': self.sequence,
            'kind': self.kind.value,
            'source_agent_id': self.source_agent_id,
            'target_agent_id': self.target_agent_id,
            'region': self.region,
            'payload_json': self.payload_json,
            'digest': self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CognitiveEvent':
        return cls(
            event_id=str(state['event_id']),
            sequence=int(state['sequence']),
            kind=EventKind(str(state['kind'])),
            source_agent_id=str(state['source_agent_id']),
            target_agent_id=None if state.get('target_agent_id') is None else str(state['target_agent_id']),
            region=None if state.get('region') is None else str(state['region']),
            payload_json=str(state['payload_json']),
            digest=str(state['digest']),
        )


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    verifier_agent_id: str
    passed: bool
    false_accepts: int = 0
    regressions: int = 0
    notes: str = ''

    def __post_init__(self) -> None:
        if self.false_accepts < 0 or self.regressions < 0:
            raise ValueError('evidence counters must be non-negative')
        if not self.evidence_id or not self.verifier_agent_id:
            raise ValueError('evidence identity must be explicit')

    def to_state(self) -> dict[str, Any]:
        return {
            'evidence_id': self.evidence_id,
            'verifier_agent_id': self.verifier_agent_id,
            'passed': self.passed,
            'false_accepts': self.false_accepts,
            'regressions': self.regressions,
            'notes': self.notes,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'EvidenceRecord':
        return cls(
            evidence_id=str(state['evidence_id']),
            verifier_agent_id=str(state['verifier_agent_id']),
            passed=bool(state['passed']),
            false_accepts=int(state.get('false_accepts', 0)),
            regressions=int(state.get('regressions', 0)),
            notes=str(state.get('notes', '')),
        )


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    memory_id: str
    sequence: int
    scope: MemoryScope
    text: str
    owner_agent_id: str
    region: str | None = None
    task_id: str | None = None
    tags: tuple[str, ...] = ()
    parent_memory_id: str | None = None
    promotion_receipt_id: str | None = None

    def to_state(self) -> dict[str, Any]:
        return {
            'memory_id': self.memory_id,
            'sequence': self.sequence,
            'scope': self.scope.value,
            'text': self.text,
            'owner_agent_id': self.owner_agent_id,
            'region': self.region,
            'task_id': self.task_id,
            'tags': list(self.tags),
            'parent_memory_id': self.parent_memory_id,
            'promotion_receipt_id': self.promotion_receipt_id,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'MemoryEntry':
        return cls(
            memory_id=str(state['memory_id']),
            sequence=int(state['sequence']),
            scope=MemoryScope(str(state['scope'])),
            text=str(state['text']),
            owner_agent_id=str(state['owner_agent_id']),
            region=None if state.get('region') is None else str(state['region']),
            task_id=None if state.get('task_id') is None else str(state['task_id']),
            tags=tuple(str(row) for row in state.get('tags', ())),
            parent_memory_id=None if state.get('parent_memory_id') is None else str(state['parent_memory_id']),
            promotion_receipt_id=None if state.get('promotion_receipt_id') is None else str(state['promotion_receipt_id']),
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
