from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .events import EventLedger
from .memory import MemoryFabric
from .registry import AgentRegistry
from .tasks import TaskGraph
from .types import ContextCapsule, EventKind

if TYPE_CHECKING:
    from .evolution import SkillEvolutionEngine


_ADMIN_EVENT_KINDS = {EventKind.AGENT_CHECKPOINTED, EventKind.AGENT_SLEEP, EventKind.AGENT_WAKE}


class ContextCompiler:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        memory: MemoryFabric,
        ledger: EventLedger,
        tasks: TaskGraph,
        evolution: 'SkillEvolutionEngine | None' = None,
        requirements: Any = None,
        planning: Any = None,
        architecture: Any = None,
        integration: Any = None,
        coding: Any = None,
        debugging: Any = None,
        ui: Any = None,
        assurance: Any = None,
        operations: Any = None,
        research: Any = None,
        max_memories: int = 128,
        max_events: int = 256,
    ) -> None:
        if max_memories < 1 or max_events < 1:
            raise ValueError('context limits must be positive')
        self.registry = registry
        self.memory = memory
        self.ledger = ledger
        self.tasks = tasks
        self.evolution = evolution
        self.requirements = requirements
        self.planning = planning
        self.architecture = architecture
        self.integration = integration
        self.coding = coding
        self.debugging = debugging
        self.ui = ui
        self.assurance = assurance
        self.operations = operations
        self.research = research
        self.max_memories = int(max_memories)
        self.max_events = int(max_events)

    def _event_relevant(self, event, *, agent_id: str, region: str, task_id: str | None) -> bool:
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

    def compile(self, agent_id: str, *, task_id: str | None = None, since_event_id: str | None = None) -> ContextCapsule:
        identity = self.registry.get(agent_id)
        effective_task = task_id if task_id is not None else identity.current_task
        memories = self.memory.retrieve(
            agent_id=identity.agent_id,
            region=identity.region,
            task_id=effective_task,
            limit=self.max_memories,
        )
        events = [
            row for row in self.ledger.events_since(since_event_id)
            if self._event_relevant(row, agent_id=identity.agent_id, region=identity.region, task_id=effective_task)
        ]
        if len(events) > self.max_events:
            events = events[-self.max_events:]
        skill_ids: tuple[str, ...] = ()
        if self.evolution is not None:
            skill_ids = tuple(row.skill_id for row in self.evolution.skills_for(identity.agent_id, region=identity.region))

        planning_version = 0 if self.planning is None else int(self.planning.graph.version)
        plan_version = max(int(self.tasks.plan_version), planning_version)
        artifacts: list[tuple[str, Any]] = [('master-plan', plan_version)]
        if self.requirements is not None:
            artifacts.append(('requirements', int(self.requirements.graph.version)))
        if self.architecture is not None:
            artifacts.append(('architecture-graph', int(self.architecture.graph.version)))
        if self.integration is not None:
            artifacts.append(('integration-state', int(self.integration.graph.version)))
        if self.coding is not None:
            if identity.region == 'core-coding' or (
                identity.region == 'frontend-ui'
                and hasattr(self.coding, 'has_active_external_grant')
                and self.coding.has_active_external_grant(identity.agent_id, effective_task)
            ):
                artifacts.append(('coding-state', self.coding.digest))
        if self.debugging is not None and identity.region == 'debugging-failure':
            artifacts.append(('debugging-state', self.debugging.digest))
        if self.ui is not None and identity.region in {'frontend-ui', 'ux-product-design'}:
            artifacts.append(('ui-state', self.ui.digest))
        if self.assurance is not None and identity.region in {'verification-testing', 'security-adversarial'}:
            artifacts.append(('assurance-state', self.assurance.digest))
        if self.operations is not None:
            if identity.region == 'data-storage-migration':
                artifacts.append(('data-state', self.operations.data.digest))
            elif identity.region == 'infrastructure-release':
                artifacts.append(('infrastructure-state', self.operations.infrastructure.digest))
            elif identity.region == 'performance-reliability':
                artifacts.append(('reliability-state', self.operations.reliability.digest))
        if self.research is not None and identity.region == 'research-external':
            artifacts.append(('research-state', self.research.digest))

        return ContextCapsule(
            agent_id=identity.agent_id,
            task_id=effective_task,
            plan_version=plan_version,
            since_event_id=since_event_id,
            memories=tuple(memories),
            event_delta=tuple(events),
            authoritative_artifacts=tuple(artifacts),
            tools=identity.tool_permissions,
            external_cores=identity.external_core_bindings,
            applicable_skill_ids=skill_ids,
            identity_summary=(
                ('name', identity.name), ('role', identity.role), ('region', identity.region),
                ('rank', identity.rank.value), ('neural_version', identity.neural_version),
                ('self_model_version', identity.self_model_version),
            ),
            authority_boundary=identity.authority_scope,
        )
