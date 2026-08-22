from __future__ import annotations

from typing import Any, Mapping

from .artifacts import ArtifactStore
from .authority import AuthorityGraph
from .blueprint import build_first_generation_blueprint
from .context import ContextCompiler
from .events import EventLedger
from .evolution import SkillEvolutionEngine
from .external_core import ExternalCoreRegistry, build_default_external_core_registry
from .memory import MemoryFabric
from .registry import AgentRegistry
from .scheduler import WakeSleepScheduler
from .self_model import SelfModelRegistry
from .tasks import TaskGraph
from .types import AgentRank, EventKind
from .verification import VerificationAuthority


class OrganizationRuntime:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        ledger: EventLedger,
        authority: AuthorityGraph,
        memory: MemoryFabric,
        tasks: TaskGraph,
        scheduler: WakeSleepScheduler,
        evolution: SkillEvolutionEngine,
        verification: VerificationAuthority,
        artifacts: ArtifactStore,
        external_cores: ExternalCoreRegistry,
        self_models: SelfModelRegistry,
    ) -> None:
        self.registry = registry
        self.ledger = ledger
        self.authority = authority
        self.memory = memory
        self.tasks = tasks
        self.scheduler = scheduler
        self.evolution = evolution
        self.verification = verification
        self.artifacts = artifacts
        self.external_cores = external_cores
        self.self_models = self_models
        self.context = ContextCompiler(
            registry=self.registry,
            memory=self.memory,
            ledger=self.ledger,
            tasks=self.tasks,
            evolution=self.evolution,
        )

    @classmethod
    def first_generation(cls) -> 'OrganizationRuntime':
        registry = AgentRegistry(build_first_generation_blueprint())
        ledger = EventLedger()
        authority = AuthorityGraph(registry)
        authority.claim_owner('master-plan', 'planning.chief')
        authority.claim_owner('requirements', 'requirements.chief')
        authority.claim_owner('architecture-graph', 'architecture.chief')
        authority.claim_owner('integration-state', 'integration.chief')
        authority.claim_owner('verification-state', 'verification.chief')

        for identity in registry.identities():
            if identity.rank is AgentRank.CHIEF:
                ledger.subscribe(identity.agent_id, EventKind.CENTRAL_INTERVENTION, region=identity.region)
                ledger.subscribe(identity.agent_id, EventKind.CENTRAL_CORRECTION, region=identity.region)
                ledger.subscribe(identity.agent_id, EventKind.CENTRAL_REDIRECT, region=identity.region)
        ledger.subscribe('planning.chief', EventKind.PLAN_GAP_DETECTED)

        memory = MemoryFabric()
        tasks = TaskGraph(ledger=ledger, registry=registry, authority=authority)
        scheduler = WakeSleepScheduler(registry=registry, ledger=ledger)
        evolution = SkillEvolutionEngine()
        verification = VerificationAuthority(registry=registry, ledger=ledger)
        artifacts = ArtifactStore()
        external_cores = build_default_external_core_registry(registry)
        self_models = SelfModelRegistry(registry)
        return cls(
            registry=registry,
            ledger=ledger,
            authority=authority,
            memory=memory,
            tasks=tasks,
            scheduler=scheduler,
            evolution=evolution,
            verification=verification,
            artifacts=artifacts,
            external_cores=external_cores,
            self_models=self_models,
        )

    def central_intervene(
        self,
        *,
        target_agent_id: str,
        directive: str,
        evidence_ids: tuple[str, ...],
    ):
        target = self.registry.get(target_agent_id)
        if not str(directive).strip():
            raise ValueError('Central intervention directive must be explicit')
        if not evidence_ids:
            raise ValueError('Central intervention requires evidence ids')
        event = self.ledger.append(
            EventKind.CENTRAL_INTERVENTION,
            source_agent_id='nolane.central',
            target_agent_id=target.agent_id,
            region=target.region,
            evidence_refs=tuple(str(value) for value in evidence_ids),
            priority=100,
            requires_ack=True,
            payload={
                'directive': str(directive),
                'evidence_ids': [str(value) for value in evidence_ids],
                'region_chief_id': target.region_chief_id,
            },
        )
        self.scheduler.notify_event(event)
        return event

    def central_action(
        self,
        kind: EventKind,
        *,
        target_agent_id: str,
        directive: str,
        evidence_ids: tuple[str, ...],
    ):
        if kind not in {
            EventKind.CENTRAL_QUESTION,
            EventKind.CENTRAL_CORRECTION,
            EventKind.CENTRAL_REDIRECT,
            EventKind.CENTRAL_PAUSE,
            EventKind.CENTRAL_ABORT,
            EventKind.CENTRAL_REQUEST_EVIDENCE,
        }:
            raise ValueError('unsupported explicit Central action')
        target = self.registry.get(target_agent_id)
        event = self.ledger.append(
            kind,
            source_agent_id='nolane.central',
            target_agent_id=target.agent_id,
            region=target.region,
            evidence_refs=tuple(str(value) for value in evidence_ids),
            priority=100,
            requires_ack=True,
            payload={'directive': str(directive), 'region_chief_id': target.region_chief_id},
        )
        self.scheduler.notify_event(event)
        return event

    def report_plan_gap(
        self,
        *,
        source_agent_id: str,
        task_id: str,
        reason: str,
        suggested_nodes: tuple[str, ...],
        evidence_ids: tuple[str, ...],
    ):
        event = self.tasks.propose_plan_gap(
            source_agent_id=source_agent_id,
            task_id=task_id,
            reason=reason,
            suggested_nodes=suggested_nodes,
            evidence_ids=evidence_ids,
        )
        self.scheduler.notify_event(event)
        return event

    def chief_direct_work(
        self,
        chief_agent_id: str,
        task_id: str,
        *,
        output_artifact_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        chief = self.registry.get(chief_agent_id)
        if chief.rank is not AgentRank.CHIEF or not chief.direct_work_capable:
            raise PermissionError(f'{chief_agent_id} is not an authorized working Regional Chief')
        completed = self.tasks.complete(task_id, chief.agent_id, output_artifact_ids=output_artifact_ids)
        event = self.ledger.append(
            EventKind.CHIEF_DIRECT_WORK,
            source_agent_id=chief.agent_id,
            target_agent_id=chief.agent_id,
            region=chief.region,
            object_refs=tuple(output_artifact_ids),
            payload={
                'task_id': task_id,
                'output_artifact_ids': list(output_artifact_ids),
                'mode': 'direct_work',
            },
        )
        return {
            'chief_agent_id': chief.agent_id,
            'task_id': completed.task_id,
            'event_id': event.event_id,
            'output_artifact_ids': completed.output_artifact_ids,
        }

    def checkpoint_agent(self, agent_id: str) -> str | None:
        anchor = self.ledger.latest_event_id()
        self.scheduler.sleep(agent_id, checkpoint_event_id=anchor)
        return self.scheduler.checkpoint_for(agent_id)

    def wake_agent(self, agent_id: str, *, reason: str):
        checkpoint = self.scheduler.checkpoint_for(agent_id)
        self.scheduler.wake(agent_id, reason=reason)
        return self.context.compile(agent_id, since_event_id=checkpoint)

    def to_state(self) -> dict[str, Any]:
        return {
            'registry': self.registry.to_state(),
            'ledger': self.ledger.to_state(),
            'authority': self.authority.to_state(),
            'memory': self.memory.to_state(),
            'tasks': self.tasks.to_state(),
            'scheduler': self.scheduler.to_state(),
            'evolution': self.evolution.to_state(),
            'verification': self.verification.to_state(),
            'artifacts': self.artifacts.to_state(),
            'external_cores': self.external_cores.to_state(),
            'self_models': self.self_models.to_state(),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'OrganizationRuntime':
        registry = AgentRegistry.from_state(state['registry'])
        ledger = EventLedger.from_state(state['ledger'])
        authority = AuthorityGraph.from_state(registry, state['authority'])
        memory = MemoryFabric.from_state(state['memory'])
        tasks = TaskGraph.from_state(
            state['tasks'],
            ledger=ledger,
            registry=registry,
            authority=authority,
        )
        scheduler = WakeSleepScheduler.from_state(
            registry=registry,
            ledger=ledger,
            state=state['scheduler'],
        )
        evolution = SkillEvolutionEngine.from_state(state['evolution'])
        verification = VerificationAuthority.from_state(
            registry=registry,
            ledger=ledger,
            state=state['verification'],
        )
        artifacts = ArtifactStore.from_state(state.get('artifacts', {}))
        external_cores = ExternalCoreRegistry.from_state(state.get('external_cores', {}))
        self_models = SelfModelRegistry.from_state(registry, state.get('self_models', {}))
        return cls(
            registry=registry,
            ledger=ledger,
            authority=authority,
            memory=memory,
            tasks=tasks,
            scheduler=scheduler,
            evolution=evolution,
            verification=verification,
            artifacts=artifacts,
            external_cores=external_cores,
            self_models=self_models,
        )
