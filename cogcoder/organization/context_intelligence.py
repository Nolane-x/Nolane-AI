from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import ceil
from typing import Any, Mapping

from .events import EventLedger
from .evolution import SkillEvolutionEngine
from .memory import MemoryFabric
from .memory_lifecycle import MemoryLifecycleLedger
from .memory_retrieval import MemoryRetrievalBudget, MemoryRetrievalEngine
from .registry import AgentRegistry
from .scheduler import WakeSleepScheduler
from .tasks import TaskGraph
from .types import CognitiveEvent, ContextCapsule, EventKind, MemoryStatus, canonical_digest


_ADMIN_EVENT_KINDS = {EventKind.AGENT_CHECKPOINTED, EventKind.AGENT_SLEEP, EventKind.AGENT_WAKE}
_CENTRAL_EVENT_KINDS = {
    EventKind.CENTRAL_INTERVENTION,
    EventKind.CENTRAL_QUESTION,
    EventKind.CENTRAL_CORRECTION,
    EventKind.CENTRAL_REDIRECT,
    EventKind.CENTRAL_PAUSE,
    EventKind.CENTRAL_ABORT,
    EventKind.CENTRAL_REQUEST_EVIDENCE,
}
_PLAN_EVENT_KINDS = {
    EventKind.PLAN_GAP_DETECTED,
    EventKind.PLAN_CHANGE_PROPOSED,
    EventKind.PLAN_AMENDED,
}
_TASK_EVENT_KINDS = {
    EventKind.TASK_ASSIGNED,
    EventKind.TASK_STARTED,
    EventKind.TASK_PROGRESS,
    EventKind.TASK_BLOCKED,
    EventKind.TASK_COMPLETED,
}
_EVIDENCE_EVENT_KINDS = {
    EventKind.EVIDENCE_ADDED,
    EventKind.TEST_FAILED,
    EventKind.TEST_PASSED,
    EventKind.VERIFICATION_REJECTED,
}


@dataclass(frozen=True, slots=True)
class ContextBudget:
    max_memories: int
    max_events: int
    max_estimated_units: int

    def __post_init__(self) -> None:
        if int(self.max_memories) < 1 or int(self.max_events) < 1 or int(self.max_estimated_units) < 1:
            raise ValueError('context budget values must be positive')

    def to_state(self) -> dict[str, int]:
        return {
            'max_memories': int(self.max_memories),
            'max_events': int(self.max_events),
            'max_estimated_units': int(self.max_estimated_units),
        }


class ContextDeltaKind(str, Enum):
    TASK_CHANGED = 'task_changed'
    PLAN_CHANGED = 'plan_changed'
    REQUIREMENTS_CHANGED = 'requirements_changed'
    ARCHITECTURE_CHANGED = 'architecture_changed'
    MEMORY_ADDED = 'memory_added'
    MEMORY_SUPERSEDED = 'memory_superseded'
    MEMORY_CONTRADICTED = 'memory_contradicted'
    MEMORY_QUARANTINED = 'memory_quarantined'
    SKILL_CHANGED = 'skill_changed'
    CENTRAL_INTERVENTION = 'central_intervention'
    EVIDENCE_CHANGED = 'evidence_changed'
    ARTIFACT_FRONTIER_CHANGED = 'artifact_frontier_changed'


@dataclass(frozen=True, slots=True)
class SemanticContextDeltaItem:
    kind: ContextDeltaKind
    object_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    source_ref: str | None
    summary: str

    def to_state(self) -> dict[str, Any]:
        return {
            'kind': self.kind.value,
            'object_refs': list(self.object_refs),
            'evidence_refs': list(self.evidence_refs),
            'source_ref': self.source_ref,
            'summary': self.summary,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'SemanticContextDeltaItem':
        return cls(
            kind=ContextDeltaKind(str(state['kind'])),
            object_refs=tuple(str(value) for value in state.get('object_refs', ())),
            evidence_refs=tuple(str(value) for value in state.get('evidence_refs', ())),
            source_ref=None if state.get('source_ref') is None else str(state['source_ref']),
            summary=str(state.get('summary', '')),
        )


@dataclass(frozen=True, slots=True)
class SemanticContextDelta:
    delta_id: str
    agent_id: str
    task_id: str | None
    checkpoint_id: str | None
    items: tuple[SemanticContextDeltaItem, ...]
    digest: str

    def content_payload(self) -> dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'task_id': self.task_id,
            'checkpoint_id': self.checkpoint_id,
            'items': [row.to_state() for row in self.items],
        }

    def to_state(self) -> dict[str, Any]:
        return {
            'delta_id': self.delta_id,
            **self.content_payload(),
            'digest': self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'SemanticContextDelta':
        items = tuple(SemanticContextDeltaItem.from_state(row) for row in state.get('items', ()))
        row = cls(
            delta_id=str(state['delta_id']),
            agent_id=str(state['agent_id']),
            task_id=None if state.get('task_id') is None else str(state['task_id']),
            checkpoint_id=None if state.get('checkpoint_id') is None else str(state['checkpoint_id']),
            items=items,
            digest=str(state['digest']),
        )
        expected = canonical_digest(row.content_payload())
        if expected != row.digest or row.delta_id != 'context-delta-' + expected[:20]:
            raise ValueError('semantic context delta digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ContinuityCheckpoint:
    checkpoint_id: str
    agent_id: str
    scheduler_checkpoint_event_id: str
    current_task_id: str | None
    plan_version: int
    requirements_version: int
    architecture_version: int
    latest_visible_memory_sequence: int
    memory_state_digest: str
    skill_frontier_digest: str
    authoritative_frontier: tuple[tuple[str, str], ...]
    compiler_version: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'checkpoint_id': self.checkpoint_id,
            'agent_id': self.agent_id,
            'scheduler_checkpoint_event_id': self.scheduler_checkpoint_event_id,
            'current_task_id': self.current_task_id,
            'plan_version': self.plan_version,
            'requirements_version': self.requirements_version,
            'architecture_version': self.architecture_version,
            'latest_visible_memory_sequence': self.latest_visible_memory_sequence,
            'memory_state_digest': self.memory_state_digest,
            'skill_frontier_digest': self.skill_frontier_digest,
            'authoritative_frontier': [[name, value] for name, value in self.authoritative_frontier],
            'compiler_version': self.compiler_version,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ContinuityCheckpoint':
        row = cls(
            checkpoint_id=str(state['checkpoint_id']),
            agent_id=str(state['agent_id']),
            scheduler_checkpoint_event_id=str(state['scheduler_checkpoint_event_id']),
            current_task_id=None if state.get('current_task_id') is None else str(state['current_task_id']),
            plan_version=int(state.get('plan_version', 0)),
            requirements_version=int(state.get('requirements_version', 0)),
            architecture_version=int(state.get('architecture_version', 0)),
            latest_visible_memory_sequence=int(state.get('latest_visible_memory_sequence', 0)),
            memory_state_digest=str(state['memory_state_digest']),
            skill_frontier_digest=str(state['skill_frontier_digest']),
            authoritative_frontier=tuple((str(value[0]), str(value[1])) for value in state.get('authoritative_frontier', ())),
            compiler_version=str(state['compiler_version']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('continuity checkpoint digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ContextCompilationReceipt:
    receipt_id: str
    agent_id: str
    task_id: str | None
    continuity_checkpoint_id: str | None
    semantic_delta_digest: str
    memory_selection_receipt_id: str
    candidate_units: int
    selected_units: int
    overload_ratio: float
    memory_candidate_count: int
    event_candidate_count: int
    selected_event_count: int
    dropped_event_count: int
    dropped_object_ids: tuple[str, ...]
    authoritative_frontier: tuple[tuple[str, str], ...]
    stale_context_warnings: tuple[str, ...]
    replayed_full_history: bool
    compiler_version: str
    capsule_digest: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'receipt_id': self.receipt_id,
            'agent_id': self.agent_id,
            'task_id': self.task_id,
            'continuity_checkpoint_id': self.continuity_checkpoint_id,
            'semantic_delta_digest': self.semantic_delta_digest,
            'memory_selection_receipt_id': self.memory_selection_receipt_id,
            'candidate_units': self.candidate_units,
            'selected_units': self.selected_units,
            'overload_ratio': self.overload_ratio,
            'memory_candidate_count': self.memory_candidate_count,
            'event_candidate_count': self.event_candidate_count,
            'selected_event_count': self.selected_event_count,
            'dropped_event_count': self.dropped_event_count,
            'dropped_object_ids': list(self.dropped_object_ids),
            'authoritative_frontier': [[name, value] for name, value in self.authoritative_frontier],
            'stale_context_warnings': list(self.stale_context_warnings),
            'replayed_full_history': self.replayed_full_history,
            'compiler_version': self.compiler_version,
            'capsule_digest': self.capsule_digest,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ContextCompilationReceipt':
        row = cls(
            receipt_id=str(state['receipt_id']),
            agent_id=str(state['agent_id']),
            task_id=None if state.get('task_id') is None else str(state['task_id']),
            continuity_checkpoint_id=None if state.get('continuity_checkpoint_id') is None else str(state['continuity_checkpoint_id']),
            semantic_delta_digest=str(state['semantic_delta_digest']),
            memory_selection_receipt_id=str(state['memory_selection_receipt_id']),
            candidate_units=int(state.get('candidate_units', 0)),
            selected_units=int(state.get('selected_units', 0)),
            overload_ratio=float(state.get('overload_ratio', 0.0)),
            memory_candidate_count=int(state.get('memory_candidate_count', 0)),
            event_candidate_count=int(state.get('event_candidate_count', 0)),
            selected_event_count=int(state.get('selected_event_count', 0)),
            dropped_event_count=int(state.get('dropped_event_count', 0)),
            dropped_object_ids=tuple(str(value) for value in state.get('dropped_object_ids', ())),
            authoritative_frontier=tuple((str(value[0]), str(value[1])) for value in state.get('authoritative_frontier', ())),
            stale_context_warnings=tuple(str(value) for value in state.get('stale_context_warnings', ())),
            replayed_full_history=bool(state.get('replayed_full_history', False)),
            compiler_version=str(state['compiler_version']),
            capsule_digest=str(state['capsule_digest']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('context compilation receipt digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ContextCompilationResult:
    capsule: ContextCapsule
    delta: SemanticContextDelta
    receipt: ContextCompilationReceipt


class ContextIntelligenceCompiler:
    COMPILER_VERSION = 'memory-context-compiler-1.0'

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        memory: MemoryFabric,
        events: EventLedger,
        tasks: TaskGraph,
        scheduler: WakeSleepScheduler,
        evolution: SkillEvolutionEngine,
        retrieval: MemoryRetrievalEngine,
        lifecycle: MemoryLifecycleLedger,
        requirements: Any = None,
        planning: Any = None,
        architecture: Any = None,
        checkpoints: tuple[ContinuityCheckpoint, ...] = (),
        deltas: tuple[SemanticContextDelta, ...] = (),
        receipts: tuple[ContextCompilationReceipt, ...] = (),
        checkpoint_counter: int = 0,
        receipt_counter: int = 0,
    ) -> None:
        self.registry = registry
        self.memory = memory
        self.events = events
        self.tasks = tasks
        self.scheduler = scheduler
        self.evolution = evolution
        self.retrieval = retrieval
        self.lifecycle = lifecycle
        self.requirements = requirements
        self.planning = planning
        self.architecture = architecture
        self._base_context: Any = None
        self._checkpoints = {row.checkpoint_id: row for row in checkpoints}
        self._deltas = {row.delta_id: row for row in deltas}
        self._receipts = {row.receipt_id: row for row in receipts}
        self._checkpoint_counter = int(checkpoint_counter)
        self._receipt_counter = int(receipt_counter)

    def bind_base_context(self, base_context: Any) -> None:
        self._base_context = base_context

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def _planning_version(self) -> int:
        graph_version = 0 if self.planning is None else int(self.planning.graph.version)
        return max(int(self.tasks.plan_version), graph_version)

    def _requirements_version(self) -> int:
        return 0 if self.requirements is None else int(self.requirements.graph.version)

    def _architecture_version(self) -> int:
        return 0 if self.architecture is None else int(self.architecture.graph.version)

    def _frontier(self) -> tuple[tuple[str, str], ...]:
        return (
            ('master-plan', str(self._planning_version())),
            ('requirements', str(self._requirements_version())),
            ('architecture-graph', str(self._architecture_version())),
        )

    def _skill_frontier(self, agent_id: str, region: str) -> str:
        skill_ids = tuple(row.skill_id for row in self.evolution.skills_for(agent_id, region=region))
        return canonical_digest({'skill_ids': list(skill_ids)})

    def capture_continuity(
        self,
        agent_id: str,
        *,
        scheduler_checkpoint_event_id: str | None = None,
    ) -> ContinuityCheckpoint:
        identity = self.registry.get(agent_id)
        scheduler_anchor = scheduler_checkpoint_event_id or self.scheduler.checkpoint_for(identity.agent_id)
        if scheduler_anchor is None:
            raise ValueError('continuity checkpoint requires an existing scheduler checkpoint event')
        self.events.get(scheduler_anchor)
        visible = self.memory.visible_entries(
            agent_id=identity.agent_id,
            region=identity.region,
            task_id=identity.current_task,
            include_inactive=True,
        )
        latest_memory = max((row.sequence for row in visible), default=0)
        self._checkpoint_counter += 1
        checkpoint_id = f'continuity-{self._checkpoint_counter:08d}'
        payload = {
            'checkpoint_id': checkpoint_id,
            'agent_id': identity.agent_id,
            'scheduler_checkpoint_event_id': scheduler_anchor,
            'current_task_id': identity.current_task,
            'plan_version': self._planning_version(),
            'requirements_version': self._requirements_version(),
            'architecture_version': self._architecture_version(),
            'latest_visible_memory_sequence': latest_memory,
            'memory_state_digest': canonical_digest(self.memory.to_state()),
            'skill_frontier_digest': self._skill_frontier(identity.agent_id, identity.region),
            'authoritative_frontier': [[name, value] for name, value in self._frontier()],
            'compiler_version': self.COMPILER_VERSION,
        }
        row = ContinuityCheckpoint(
            checkpoint_id=checkpoint_id,
            agent_id=identity.agent_id,
            scheduler_checkpoint_event_id=scheduler_anchor,
            current_task_id=identity.current_task,
            plan_version=self._planning_version(),
            requirements_version=self._requirements_version(),
            architecture_version=self._architecture_version(),
            latest_visible_memory_sequence=latest_memory,
            memory_state_digest=payload['memory_state_digest'],
            skill_frontier_digest=payload['skill_frontier_digest'],
            authoritative_frontier=self._frontier(),
            compiler_version=self.COMPILER_VERSION,
            digest=canonical_digest(payload),
        )
        self._checkpoints[row.checkpoint_id] = row
        return row

    def checkpoint(self, checkpoint_id: str) -> ContinuityCheckpoint:
        try:
            return self._checkpoints[str(checkpoint_id)]
        except KeyError as exc:
            raise KeyError(f'unknown continuity checkpoint: {checkpoint_id}') from exc

    def _event_relevant(self, event: CognitiveEvent, *, agent_id: str, region: str, task_id: str | None) -> bool:
        if event.kind in _ADMIN_EVENT_KINDS:
            return False
        if event.target_agent_id == agent_id or event.source_agent_id == agent_id:
            return True
        if event.region == region:
            return True
        if task_id is not None:
            payload = event.payload
            if payload.get('task_id') == task_id:
                return True
            affected = payload.get('affected_tasks', ())
            if isinstance(affected, list) and task_id in affected:
                return True
        return False

    @staticmethod
    def _event_units(event: CognitiveEvent) -> int:
        return max(1, ceil((len(event.payload_json) + 32 + 8 * len(event.evidence_refs)) / 4))

    @staticmethod
    def _event_score(event: CognitiveEvent) -> int:
        score = int(event.priority)
        if event.kind in _CENTRAL_EVENT_KINDS:
            score += 1000
        elif event.kind in _PLAN_EVENT_KINDS:
            score += 800
        elif event.kind in _TASK_EVENT_KINDS:
            score += 700
        elif event.kind in _EVIDENCE_EVENT_KINDS:
            score += 500
        elif event.kind is EventKind.ARCHITECTURE_CONCERN:
            score += 650
        score += min(event.sequence, 100000)
        return score

    def _select_events(
        self,
        candidates: tuple[CognitiveEvent, ...],
        *,
        max_events: int,
        remaining_units: int,
    ) -> tuple[tuple[CognitiveEvent, ...], tuple[CognitiveEvent, ...], int]:
        ranked = sorted(candidates, key=lambda row: (-self._event_score(row), -row.sequence, row.event_id))
        selected: list[CognitiveEvent] = []
        dropped: list[CognitiveEvent] = []
        used = 0
        for event in ranked:
            units = self._event_units(event)
            if len(selected) >= max_events or used + units > remaining_units:
                dropped.append(event)
                continue
            selected.append(event)
            used += units
        selected.sort(key=lambda row: row.sequence)
        return tuple(selected), tuple(dropped), used

    @staticmethod
    def _delta_kind_for_event(event: CognitiveEvent) -> ContextDeltaKind | None:
        if event.kind in _CENTRAL_EVENT_KINDS:
            return ContextDeltaKind.CENTRAL_INTERVENTION
        if event.kind in _PLAN_EVENT_KINDS:
            return ContextDeltaKind.PLAN_CHANGED
        if event.kind in _TASK_EVENT_KINDS:
            return ContextDeltaKind.TASK_CHANGED
        if event.kind in _EVIDENCE_EVENT_KINDS:
            return ContextDeltaKind.EVIDENCE_CHANGED
        if event.kind is EventKind.ARCHITECTURE_CONCERN:
            return ContextDeltaKind.ARCHITECTURE_CHANGED
        if event.kind in {EventKind.SKILL_CANDIDATE, EventKind.SKILL_PROMOTED, EventKind.SKILL_REJECTED, EventKind.SKILL_QUARANTINED}:
            return ContextDeltaKind.SKILL_CHANGED
        return None

    def _fallback_capsule(
        self,
        *,
        agent_id: str,
        task_id: str | None,
        since_event_id: str | None,
    ) -> ContextCapsule:
        identity = self.registry.get(agent_id)
        skills = tuple(row.skill_id for row in self.evolution.skills_for(identity.agent_id, region=identity.region))
        return ContextCapsule(
            agent_id=identity.agent_id,
            task_id=task_id,
            plan_version=self._planning_version(),
            since_event_id=since_event_id,
            memories=(),
            event_delta=(),
            authoritative_artifacts=tuple((name, int(value)) for name, value in self._frontier()),
            tools=identity.tool_permissions,
            external_cores=identity.external_core_bindings,
            applicable_skill_ids=skills,
            identity_summary=(
                ('name', identity.name), ('role', identity.role), ('region', identity.region),
                ('rank', identity.rank.value), ('neural_version', identity.neural_version),
                ('self_model_version', identity.self_model_version),
            ),
            authority_boundary=identity.authority_scope,
        )

    @staticmethod
    def _capsule_digest(capsule: ContextCapsule) -> str:
        return canonical_digest({
            'agent_id': capsule.agent_id,
            'task_id': capsule.task_id,
            'plan_version': capsule.plan_version,
            'since_event_id': capsule.since_event_id,
            'memories': [row.memory_id for row in capsule.memories],
            'events': [row.event_id for row in capsule.event_delta],
            'authoritative_artifacts': [[name, value] for name, value in capsule.authoritative_artifacts],
            'tools': list(capsule.tools),
            'external_cores': list(capsule.external_cores),
            'applicable_skill_ids': list(capsule.applicable_skill_ids),
            'identity_summary': [[name, value] for name, value in capsule.identity_summary],
            'authority_boundary': list(capsule.authority_boundary),
            'semantic_delta_digest': capsule.semantic_delta_digest,
            'context_compilation_receipt_id': capsule.context_compilation_receipt_id,
            'context_budget_units': capsule.context_budget_units,
            'context_overload_ratio': capsule.context_overload_ratio,
            'stale_context_warnings': list(capsule.stale_context_warnings),
        })

    def compile(
        self,
        agent_id: str,
        *,
        task_id: str | None = None,
        continuity_checkpoint_id: str | None = None,
        budget: ContextBudget,
    ) -> ContextCompilationResult:
        identity = self.registry.get(agent_id)
        effective_task = identity.current_task if task_id is None else str(task_id)
        checkpoint: ContinuityCheckpoint | None = None
        since_event_id: str | None = None
        if continuity_checkpoint_id is not None:
            checkpoint = self.checkpoint(continuity_checkpoint_id)
            if checkpoint.agent_id != identity.agent_id:
                raise PermissionError('continuity checkpoint belongs to a different agent')
            since_event_id = checkpoint.scheduler_checkpoint_event_id

        memory_budget = MemoryRetrievalBudget(
            max_memories=budget.max_memories,
            max_estimated_units=max(1, budget.max_estimated_units // 2),
        )
        memory_selection = self.retrieval.select(
            agent_id=identity.agent_id,
            region=identity.region,
            task_id=effective_task,
            tags=(),
            budget=memory_budget,
        )
        selected_memories = self.retrieval.selected_entries(memory_selection)

        event_rows = tuple(
            event for event in self.events.events_since(since_event_id)
            if self._event_relevant(event, agent_id=identity.agent_id, region=identity.region, task_id=effective_task)
        )
        event_candidate_units = sum(self._event_units(event) for event in event_rows)
        remaining_units = max(0, budget.max_estimated_units - memory_selection.selected_units)
        selected_events, dropped_events, selected_event_units = self._select_events(
            event_rows, max_events=budget.max_events, remaining_units=remaining_units,
        )

        warnings: list[str] = []
        if checkpoint is not None:
            if checkpoint.current_task_id != identity.current_task:
                warnings.append('task_changed_since_checkpoint')
            if checkpoint.plan_version != self._planning_version():
                warnings.append('plan_changed_since_checkpoint')
            if checkpoint.requirements_version != self._requirements_version():
                warnings.append('requirements_changed_since_checkpoint')
            if checkpoint.architecture_version != self._architecture_version():
                warnings.append('architecture_changed_since_checkpoint')
            if checkpoint.authoritative_frontier != self._frontier():
                warnings.append('authoritative_frontier_changed_since_checkpoint')

        delta_items: list[SemanticContextDeltaItem] = []
        for event in selected_events:
            kind = self._delta_kind_for_event(event)
            if kind is None:
                continue
            delta_items.append(SemanticContextDeltaItem(
                kind=kind,
                object_refs=event.object_refs,
                evidence_refs=event.evidence_refs,
                source_ref=event.event_id,
                summary=f'{event.kind.value}:{event.event_id}',
            ))

        memory_frontier = 0 if checkpoint is None else checkpoint.latest_visible_memory_sequence
        for row in selected_memories:
            if row.sequence > memory_frontier:
                delta_items.append(SemanticContextDeltaItem(
                    kind=ContextDeltaKind.MEMORY_ADDED,
                    object_refs=(row.memory_id,),
                    evidence_refs=row.evidence_ids,
                    source_ref=row.memory_id,
                    summary=f'active memory added:{row.memory_id}',
                ))

        if checkpoint is not None:
            anchor_sequence = self.events.get(checkpoint.scheduler_checkpoint_event_id).sequence
            for lifecycle_receipt in self.lifecycle.receipts():
                if lifecycle_receipt.event_anchor_id is None:
                    continue
                if self.events.get(lifecycle_receipt.event_anchor_id).sequence <= anchor_sequence:
                    continue
                kind = {
                    MemoryStatus.SUPERSEDED: ContextDeltaKind.MEMORY_SUPERSEDED,
                    MemoryStatus.CONTRADICTED: ContextDeltaKind.MEMORY_CONTRADICTED,
                    MemoryStatus.QUARANTINED: ContextDeltaKind.MEMORY_QUARANTINED,
                }.get(lifecycle_receipt.new_status)
                if kind is not None:
                    delta_items.append(SemanticContextDeltaItem(
                        kind=kind,
                        object_refs=(lifecycle_receipt.memory_id,),
                        evidence_refs=lifecycle_receipt.evidence_refs,
                        source_ref=lifecycle_receipt.receipt_id,
                        summary=f'{lifecycle_receipt.new_status.value}:{lifecycle_receipt.memory_id}',
                    ))

        delta_payload = {
            'agent_id': identity.agent_id,
            'task_id': effective_task,
            'checkpoint_id': None if checkpoint is None else checkpoint.checkpoint_id,
            'items': [row.to_state() for row in delta_items],
        }
        delta_digest = canonical_digest(delta_payload)
        delta = SemanticContextDelta(
            delta_id='context-delta-' + delta_digest[:20],
            agent_id=identity.agent_id,
            task_id=effective_task,
            checkpoint_id=None if checkpoint is None else checkpoint.checkpoint_id,
            items=tuple(delta_items),
            digest=delta_digest,
        )
        self._deltas[delta.delta_id] = delta

        candidate_units = memory_selection.candidate_units + event_candidate_units
        selected_units = memory_selection.selected_units + selected_event_units
        overload_ratio = candidate_units / float(budget.max_estimated_units)
        if overload_ratio > 1.0:
            warnings.append('context_overload')
        warnings = list(dict.fromkeys(warnings))

        base = (
            self._base_context.compile(identity.agent_id, task_id=effective_task, since_event_id=since_event_id)
            if self._base_context is not None
            else self._fallback_capsule(agent_id=identity.agent_id, task_id=effective_task, since_event_id=since_event_id)
        )

        self._receipt_counter += 1
        receipt_id = f'context-compilation-{self._receipt_counter:08d}'
        provisional_capsule = replace(
            base,
            task_id=effective_task,
            plan_version=self._planning_version(),
            since_event_id=since_event_id,
            memories=tuple(selected_memories),
            event_delta=selected_events,
            semantic_delta_digest=delta.digest,
            context_compilation_receipt_id=receipt_id,
            context_budget_units=selected_units,
            context_overload_ratio=overload_ratio,
            stale_context_warnings=tuple(warnings),
        )
        capsule_digest = self._capsule_digest(provisional_capsule)
        dropped_ids = tuple(memory_selection.dropped_memory_ids) + tuple(event.event_id for event in dropped_events)
        receipt_payload = {
            'receipt_id': receipt_id,
            'agent_id': identity.agent_id,
            'task_id': effective_task,
            'continuity_checkpoint_id': None if checkpoint is None else checkpoint.checkpoint_id,
            'semantic_delta_digest': delta.digest,
            'memory_selection_receipt_id': memory_selection.receipt_id,
            'candidate_units': candidate_units,
            'selected_units': selected_units,
            'overload_ratio': overload_ratio,
            'memory_candidate_count': len(memory_selection.candidate_memory_ids),
            'event_candidate_count': len(event_rows),
            'selected_event_count': len(selected_events),
            'dropped_event_count': len(dropped_events),
            'dropped_object_ids': list(dropped_ids),
            'authoritative_frontier': [[name, value] for name, value in self._frontier()],
            'stale_context_warnings': list(warnings),
            'replayed_full_history': checkpoint is None,
            'compiler_version': self.COMPILER_VERSION,
            'capsule_digest': capsule_digest,
        }
        receipt = ContextCompilationReceipt(
            receipt_id=receipt_id,
            agent_id=identity.agent_id,
            task_id=effective_task,
            continuity_checkpoint_id=None if checkpoint is None else checkpoint.checkpoint_id,
            semantic_delta_digest=delta.digest,
            memory_selection_receipt_id=memory_selection.receipt_id,
            candidate_units=candidate_units,
            selected_units=selected_units,
            overload_ratio=overload_ratio,
            memory_candidate_count=len(memory_selection.candidate_memory_ids),
            event_candidate_count=len(event_rows),
            selected_event_count=len(selected_events),
            dropped_event_count=len(dropped_events),
            dropped_object_ids=dropped_ids,
            authoritative_frontier=self._frontier(),
            stale_context_warnings=tuple(warnings),
            replayed_full_history=checkpoint is None,
            compiler_version=self.COMPILER_VERSION,
            capsule_digest=capsule_digest,
            digest=canonical_digest(receipt_payload),
        )
        self._receipts[receipt.receipt_id] = receipt
        return ContextCompilationResult(capsule=provisional_capsule, delta=delta, receipt=receipt)

    def to_state(self) -> dict[str, Any]:
        return {
            'compiler_version': self.COMPILER_VERSION,
            'checkpoints': [self._checkpoints[key].to_state() for key in sorted(self._checkpoints)],
            'deltas': [self._deltas[key].to_state() for key in sorted(self._deltas)],
            'receipts': [self._receipts[key].to_state() for key in sorted(self._receipts)],
            'checkpoint_counter': self._checkpoint_counter,
            'receipt_counter': self._receipt_counter,
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        memory: MemoryFabric,
        events: EventLedger,
        tasks: TaskGraph,
        scheduler: WakeSleepScheduler,
        evolution: SkillEvolutionEngine,
        retrieval: MemoryRetrievalEngine,
        lifecycle: MemoryLifecycleLedger,
        requirements: Any,
        planning: Any,
        architecture: Any,
        state: Mapping[str, Any],
    ) -> 'ContextIntelligenceCompiler':
        version = str(state.get('compiler_version', cls.COMPILER_VERSION))
        if version != cls.COMPILER_VERSION:
            raise ValueError(f'unsupported Memory/Context compiler version: {version}')
        checkpoints = tuple(ContinuityCheckpoint.from_state(row) for row in state.get('checkpoints', ()))
        deltas = tuple(SemanticContextDelta.from_state(row) for row in state.get('deltas', ()))
        receipts = tuple(ContextCompilationReceipt.from_state(row) for row in state.get('receipts', ()))
        result = cls(
            registry=registry,
            memory=memory,
            events=events,
            tasks=tasks,
            scheduler=scheduler,
            evolution=evolution,
            retrieval=retrieval,
            lifecycle=lifecycle,
            requirements=requirements,
            planning=planning,
            architecture=architecture,
            checkpoints=checkpoints,
            deltas=deltas,
            receipts=receipts,
            checkpoint_counter=int(state.get('checkpoint_counter', len(checkpoints))),
            receipt_counter=int(state.get('receipt_counter', len(receipts))),
        )
        for checkpoint in checkpoints:
            registry.get(checkpoint.agent_id)
            events.get(checkpoint.scheduler_checkpoint_event_id)
        for receipt in receipts:
            registry.get(receipt.agent_id)
            retrieval.receipt(receipt.memory_selection_receipt_id)
            if receipt.continuity_checkpoint_id is not None:
                result.checkpoint(receipt.continuity_checkpoint_id)
            if not any(delta.digest == receipt.semantic_delta_digest for delta in deltas):
                raise ValueError('context compilation receipt references unknown semantic delta')
        return result
