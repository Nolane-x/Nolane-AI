from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

COMPONENT_ID = "external.context"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.memory_context"

from nolane.core.canonical_digest import canonical_digest
from nolane.memory.context_intelligence import (
    ContextBudget,
    ContextCompilationResult,
    ContextIntelligenceCompiler,
    ContinuityCheckpoint,
)
from nolane.memory.context_profiles import MemoryIntelligenceProfileRegistry
from nolane.memory.fabric import MemoryFabric, MemoryStatus
from nolane.memory.lifecycle import MemoryLifecycleLedger, MemoryRelationGraph
from nolane.memory.retrieval import MemoryRetrievalEngine
from nolane.memory.skills import SkillEvolutionEngine, SkillRecord
from nolane.organization.events import EventLedger
from nolane.organization.identity import AgentRegistry
from nolane.organization.lifecycle import WakeSleepScheduler
from nolane.organization.tasks import TaskGraph


@dataclass(frozen=True, slots=True)
class MemoryRepairReceipt:
    repair_id: str
    chief_agent_id: str
    rejected_memory_ids: tuple[str, ...]
    corrected_memory_id: str
    affected_agent_id: str
    lifecycle_receipt_ids: tuple[str, ...]
    context_compilation_receipt_id: str
    selected_memory_ids: tuple[str, ...]
    reason: str
    evidence_refs: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'repair_id': self.repair_id,
            'chief_agent_id': self.chief_agent_id,
            'rejected_memory_ids': list(self.rejected_memory_ids),
            'corrected_memory_id': self.corrected_memory_id,
            'affected_agent_id': self.affected_agent_id,
            'lifecycle_receipt_ids': list(self.lifecycle_receipt_ids),
            'context_compilation_receipt_id': self.context_compilation_receipt_id,
            'selected_memory_ids': list(self.selected_memory_ids),
            'reason': self.reason,
            'evidence_refs': list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'MemoryRepairReceipt':
        row = cls(
            repair_id=str(state['repair_id']),
            chief_agent_id=str(state['chief_agent_id']),
            rejected_memory_ids=tuple(str(value) for value in state.get('rejected_memory_ids', ())),
            corrected_memory_id=str(state['corrected_memory_id']),
            affected_agent_id=str(state['affected_agent_id']),
            lifecycle_receipt_ids=tuple(str(value) for value in state.get('lifecycle_receipt_ids', ())),
            context_compilation_receipt_id=str(state['context_compilation_receipt_id']),
            selected_memory_ids=tuple(str(value) for value in state.get('selected_memory_ids', ())),
            reason=str(state['reason']),
            evidence_refs=tuple(str(value) for value in state.get('evidence_refs', ())),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('memory repair receipt digest mismatch')
        return row


class MemoryContextControlPlane:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        memory: MemoryFabric,
        events: EventLedger,
        tasks: TaskGraph,
        scheduler: WakeSleepScheduler,
        evolution: SkillEvolutionEngine,
        requirements: Any = None,
        planning: Any = None,
        architecture: Any = None,
        profiles: MemoryIntelligenceProfileRegistry | None = None,
        lifecycle: MemoryLifecycleLedger | None = None,
        relations: MemoryRelationGraph | None = None,
        retrieval: MemoryRetrievalEngine | None = None,
        context_intelligence: ContextIntelligenceCompiler | None = None,
        repairs: tuple[MemoryRepairReceipt, ...] = (),
        repair_counter: int = 0,
    ) -> None:
        self.registry = registry
        self.memory = memory
        self.events = events
        self.tasks = tasks
        self.scheduler = scheduler
        self.evolution = evolution
        self.requirements = requirements
        self.planning = planning
        self.architecture = architecture
        self.profiles = profiles or MemoryIntelligenceProfileRegistry(registry)
        self.lifecycle = lifecycle or MemoryLifecycleLedger(
            registry=registry, memory=memory, events=events,
        )
        self.relations = relations or MemoryRelationGraph(
            registry=registry, memory=memory, events=events,
        )
        self.retrieval = retrieval or MemoryRetrievalEngine(
            memory=memory, relations=self.relations,
        )
        self.context_intelligence = context_intelligence or ContextIntelligenceCompiler(
            registry=registry,
            memory=memory,
            events=events,
            tasks=tasks,
            scheduler=scheduler,
            evolution=evolution,
            retrieval=self.retrieval,
            lifecycle=self.lifecycle,
            requirements=requirements,
            planning=planning,
            architecture=architecture,
        )
        self._repairs = {row.repair_id: row for row in repairs}
        self._repair_counter = int(repair_counter)

    @property
    def digest(self) -> str:
        return canonical_digest(self.to_state())

    def bind_base_context(self, base_context: Any) -> None:
        self.context_intelligence.bind_base_context(base_context)

    def capture_continuity(
        self,
        agent_id: str,
        *,
        scheduler_checkpoint_event_id: str | None = None,
    ) -> ContinuityCheckpoint:
        return self.context_intelligence.capture_continuity(
            agent_id,
            scheduler_checkpoint_event_id=scheduler_checkpoint_event_id,
        )

    def compile_context(
        self,
        agent_id: str,
        *,
        task_id: str | None = None,
        continuity_checkpoint_id: str | None = None,
        budget: ContextBudget | None = None,
    ) -> ContextCompilationResult:
        effective_budget = budget or ContextBudget(
            max_memories=64,
            max_events=64,
            max_estimated_units=8192,
        )
        return self.context_intelligence.compile(
            agent_id,
            task_id=task_id,
            continuity_checkpoint_id=continuity_checkpoint_id,
            budget=effective_budget,
        )

    def repair_contradiction(
        self,
        *,
        chief_agent_id: str,
        rejected_memory_ids: tuple[str, ...],
        corrected_memory_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
        affected_agent_id: str,
        budget: ContextBudget,
    ) -> MemoryRepairReceipt:
        chief = self.registry.get(chief_agent_id)
        if chief.agent_id != 'memory.chief' or chief.region != 'memory-context-knowledge' or not chief.direct_work_capable:
            raise PermissionError('governed cross-memory repair requires direct Memory Chief authority')
        if not rejected_memory_ids:
            raise ValueError('memory contradiction repair requires rejected memories')
        if not str(reason).strip() or not evidence_refs:
            raise ValueError('memory contradiction repair requires reason and evidence')
        corrected = self.memory.get(corrected_memory_id)
        if corrected.status is not MemoryStatus.ACTIVE:
            raise PermissionError('corrected memory must be active before contradiction repair')
        self.registry.get(affected_agent_id)

        transition_ids: list[str] = []
        for memory_id in rejected_memory_ids:
            rejected = self.memory.get(memory_id)
            if rejected.memory_id == corrected.memory_id:
                raise ValueError('corrected memory cannot also be rejected')
            receipt = self.lifecycle.transition(
                rejected.memory_id,
                actor_agent_id=chief.agent_id,
                new_status=MemoryStatus.CONTRADICTED,
                reason=str(reason),
                evidence_refs=tuple(str(value) for value in evidence_refs),
                correction_ref=corrected.memory_id,
            )
            transition_ids.append(receipt.receipt_id)

        compiled = self.compile_context(
            affected_agent_id,
            budget=budget,
        )
        selected_ids = tuple(row.memory_id for row in compiled.capsule.memories)
        if corrected.memory_id not in selected_ids:
            raise ValueError('corrected memory is not visible in affected agent context after repair')
        if any(memory_id in selected_ids for memory_id in rejected_memory_ids):
            raise ValueError('rejected memory leaked into affected context after repair')

        self._repair_counter += 1
        repair_id = f'memory-repair-{self._repair_counter:08d}'
        payload = {
            'repair_id': repair_id,
            'chief_agent_id': chief.agent_id,
            'rejected_memory_ids': [str(value) for value in rejected_memory_ids],
            'corrected_memory_id': corrected.memory_id,
            'affected_agent_id': str(affected_agent_id),
            'lifecycle_receipt_ids': list(transition_ids),
            'context_compilation_receipt_id': compiled.receipt.receipt_id,
            'selected_memory_ids': list(selected_ids),
            'reason': str(reason),
            'evidence_refs': [str(value) for value in evidence_refs],
        }
        row = MemoryRepairReceipt(
            repair_id=repair_id,
            chief_agent_id=chief.agent_id,
            rejected_memory_ids=tuple(str(value) for value in rejected_memory_ids),
            corrected_memory_id=corrected.memory_id,
            affected_agent_id=str(affected_agent_id),
            lifecycle_receipt_ids=tuple(transition_ids),
            context_compilation_receipt_id=compiled.receipt.receipt_id,
            selected_memory_ids=selected_ids,
            reason=str(reason),
            evidence_refs=tuple(str(value) for value in evidence_refs),
            digest=canonical_digest(payload),
        )
        self._repairs[row.repair_id] = row
        return row

    def repair_receipt(self, repair_id: str) -> MemoryRepairReceipt:
        try:
            return self._repairs[str(repair_id)]
        except KeyError as exc:
            raise KeyError(f'unknown memory repair receipt: {repair_id}') from exc

    def propose_personal_skill(
        self,
        *,
        agent_id: str,
        name: str,
        body: str,
        object_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ) -> SkillRecord:
        profile = self.profiles.get(agent_id)
        if not object_refs or not evidence_refs:
            raise ValueError('Memory/Context skill candidate requires object and evidence refs')
        return self.evolution.propose(
            owner_agent_id=profile.agent_id,
            region=profile.region,
            name=name,
            body=body,
        )

    def to_state(self) -> dict[str, Any]:
        return {
            'profiles': self.profiles.to_state(),
            'lifecycle': self.lifecycle.to_state(),
            'relations': self.relations.to_state(),
            'retrieval': self.retrieval.to_state(),
            'context_intelligence': self.context_intelligence.to_state(),
            'repairs': [self._repairs[key].to_state() for key in sorted(self._repairs)],
            'repair_counter': self._repair_counter,
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
        requirements: Any,
        planning: Any,
        architecture: Any,
        state: Mapping[str, Any],
    ) -> 'MemoryContextControlPlane':
        profiles = MemoryIntelligenceProfileRegistry.from_state(registry, state.get('profiles', {}))
        lifecycle = MemoryLifecycleLedger.from_state(
            registry=registry, memory=memory, events=events, state=state.get('lifecycle', {}),
        )
        relations = MemoryRelationGraph.from_state(
            registry=registry, memory=memory, events=events, state=state.get('relations', {}),
        )
        retrieval = MemoryRetrievalEngine.from_state(
            memory=memory, relations=relations, state=state.get('retrieval', {}),
        )
        context_intelligence = ContextIntelligenceCompiler.from_state(
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
            state=state.get('context_intelligence', {}),
        )
        repairs = tuple(MemoryRepairReceipt.from_state(row) for row in state.get('repairs', ()))
        result = cls(
            registry=registry,
            memory=memory,
            events=events,
            tasks=tasks,
            scheduler=scheduler,
            evolution=evolution,
            requirements=requirements,
            planning=planning,
            architecture=architecture,
            profiles=profiles,
            lifecycle=lifecycle,
            relations=relations,
            retrieval=retrieval,
            context_intelligence=context_intelligence,
            repairs=repairs,
            repair_counter=int(state.get('repair_counter', len(repairs))),
        )
        for repair in repairs:
            registry.get(repair.chief_agent_id)
            registry.get(repair.affected_agent_id)
            memory.get(repair.corrected_memory_id)
            for memory_id in repair.rejected_memory_ids:
                memory.get(memory_id)
        return result


__all__ = (
    "ContextBudget",
    "ContextCompilationResult",
    "ContextIntelligenceCompiler",
    "ContinuityCheckpoint",
    "MemoryRepairReceipt",
    "MemoryContextControlPlane",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)
