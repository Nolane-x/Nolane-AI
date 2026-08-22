from __future__ import annotations

from typing import Any, Mapping

from .adr import ADRDecisionLedger
from .architecture import ArchitectureControlPlane
from .artifacts import ArtifactStore
from .assurance import AssuranceControlPlane
from .authority import AuthorityGraph
from .blueprint import build_first_generation_blueprint
from .central import CentralControlPlane
from .context import ContextCompiler
from .debugging import DebugControlPlane
from .events import EventLedger
from .evolution import SkillEvolutionEngine
from .external_core import ExternalCoreRegistry, build_default_external_core_registry
from .integration import IntegrationControlPlane
from .memory import MemoryFabric
from .planning import PlanningControlPlane
from .registry import AgentRegistry
from .requirements import RequirementsControlPlane
from .scheduler import WakeSleepScheduler
from .self_model import SelfModelRegistry
from .tasks import TaskGraph
from .types import AgentRank, EventKind
from .ui import UIControlPlane
from .ui_coding import UICodingControlPlane
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
        central: CentralControlPlane | None = None,
        requirements: RequirementsControlPlane | None = None,
        planning: PlanningControlPlane | None = None,
        architecture: ArchitectureControlPlane | None = None,
        adr: ADRDecisionLedger | None = None,
        integration: IntegrationControlPlane | None = None,
        coding: UICodingControlPlane | None = None,
        debugging: DebugControlPlane | None = None,
        ui: UIControlPlane | None = None,
        assurance: AssuranceControlPlane | None = None,
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
        if self.authority.owner_of('frontend-ui-state') is None:
            self.authority.claim_owner('frontend-ui-state', 'frontend.chief')
        if self.authority.owner_of('ux-design-state') is None:
            self.authority.claim_owner('ux-design-state', 'ux.chief')
        self.requirements = requirements or RequirementsControlPlane(
            registry=self.registry, authority=self.authority, ledger=self.ledger,
        )
        self.planning = planning or PlanningControlPlane(
            registry=self.registry, authority=self.authority, ledger=self.ledger,
            tasks=self.tasks, requirements=self.requirements,
        )
        self.architecture = architecture or ArchitectureControlPlane(
            registry=self.registry, authority=self.authority, ledger=self.ledger,
        )
        self.adr = adr or ADRDecisionLedger(
            registry=self.registry, authority=self.authority, architecture=self.architecture,
        )
        self.integration = integration or IntegrationControlPlane(
            registry=self.registry, authority=self.authority, architecture=self.architecture,
        )
        self.coding = coding or UICodingControlPlane(
            registry=self.registry, ledger=self.ledger, tasks=self.tasks, evolution=self.evolution,
            planning=self.planning, architecture=self.architecture, integration=self.integration,
        )
        self.debugging = debugging or DebugControlPlane(
            registry=self.registry, ledger=self.ledger, tasks=self.tasks,
            evolution=self.evolution, coding=self.coding,
        )
        self.ui = ui or UIControlPlane(
            registry=self.registry, ledger=self.ledger, tasks=self.tasks, evolution=self.evolution,
            artifacts=self.artifacts, authority=self.authority, planning=self.planning,
            architecture=self.architecture, coding=self.coding,
        )
        self.assurance = assurance or AssuranceControlPlane(
            registry=self.registry, ledger=self.ledger, authority=self.authority,
            artifacts=self.artifacts, evolution=self.evolution, verification=self.verification,
        )
        self.context = ContextCompiler(
            registry=self.registry, memory=self.memory, ledger=self.ledger, tasks=self.tasks,
            evolution=self.evolution, requirements=self.requirements, planning=self.planning,
            architecture=self.architecture, integration=self.integration, coding=self.coding,
            debugging=self.debugging, ui=self.ui, assurance=self.assurance,
        )
        self.central = central or CentralControlPlane(
            registry=self.registry, ledger=self.ledger, authority=self.authority, tasks=self.tasks,
            scheduler=self.scheduler, artifacts=self.artifacts, external_cores=self.external_cores,
            self_models=self.self_models, evolution=self.evolution, verification=self.verification,
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
        authority.claim_owner('frontend-ui-state', 'frontend.chief')
        authority.claim_owner('ux-design-state', 'ux.chief')

        central_actions = (
            EventKind.CENTRAL_INTERVENTION, EventKind.CENTRAL_QUESTION, EventKind.CENTRAL_CORRECTION,
            EventKind.CENTRAL_REDIRECT, EventKind.CENTRAL_PAUSE, EventKind.CENTRAL_ABORT,
            EventKind.CENTRAL_REQUEST_EVIDENCE,
        )
        for identity in registry.identities():
            if identity.rank is AgentRank.CHIEF:
                for kind in central_actions:
                    ledger.subscribe(identity.agent_id, kind, region=identity.region)
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
            registry=registry, ledger=ledger, authority=authority, memory=memory, tasks=tasks,
            scheduler=scheduler, evolution=evolution, verification=verification, artifacts=artifacts,
            external_cores=external_cores, self_models=self_models,
        )

    def central_intervene(self, *, target_agent_id: str, directive: str, evidence_ids: tuple[str, ...]):
        target = self.registry.get(target_agent_id)
        if not str(directive).strip():
            raise ValueError('Central intervention directive must be explicit')
        if not evidence_ids:
            raise ValueError('Central intervention requires evidence ids')
        event = self.ledger.append(
            EventKind.CENTRAL_INTERVENTION, source_agent_id='nolane.central', target_agent_id=target.agent_id,
            region=target.region, evidence_refs=tuple(str(value) for value in evidence_ids), priority=100,
            requires_ack=True,
            payload={'directive': str(directive), 'evidence_ids': [str(value) for value in evidence_ids], 'region_chief_id': target.region_chief_id},
        )
        self.scheduler.notify_event(event)
        return event

    def central_action(self, kind: EventKind, *, target_agent_id: str, directive: str, evidence_ids: tuple[str, ...]):
        if kind not in {
            EventKind.CENTRAL_QUESTION, EventKind.CENTRAL_CORRECTION, EventKind.CENTRAL_REDIRECT,
            EventKind.CENTRAL_PAUSE, EventKind.CENTRAL_ABORT, EventKind.CENTRAL_REQUEST_EVIDENCE,
        }:
            raise ValueError('unsupported explicit Central action')
        evidence = tuple(str(value) for value in evidence_ids)
        if kind is EventKind.CENTRAL_QUESTION:
            return self.central.question(target_agent_id=target_agent_id, directive=directive, evidence_refs=evidence)
        if kind is EventKind.CENTRAL_CORRECTION:
            return self.central.correct(target_agent_id=target_agent_id, directive=directive, evidence_refs=evidence)
        if kind is EventKind.CENTRAL_REDIRECT:
            return self.central.redirect(target_agent_id=target_agent_id, directive=directive, evidence_refs=evidence)
        if kind is EventKind.CENTRAL_PAUSE:
            return self.central.pause(target_agent_id=target_agent_id, directive=directive, evidence_refs=evidence)
        if kind is EventKind.CENTRAL_ABORT:
            return self.central.abort(target_agent_id=target_agent_id, directive=directive, evidence_refs=evidence)
        return self.central.request_evidence(target_agent_id=target_agent_id, directive=directive, evidence_refs=evidence)

    def report_plan_gap(self, *, source_agent_id: str, task_id: str, reason: str, suggested_nodes: tuple[str, ...], evidence_ids: tuple[str, ...]):
        event = self.tasks.propose_plan_gap(
            source_agent_id=source_agent_id, task_id=task_id, reason=reason,
            suggested_nodes=suggested_nodes, evidence_ids=evidence_ids,
        )
        self.scheduler.notify_event(event)
        return event

    def chief_direct_work(self, chief_agent_id: str, task_id: str, *, output_artifact_ids: tuple[str, ...]) -> dict[str, Any]:
        chief = self.registry.get(chief_agent_id)
        if chief.rank is not AgentRank.CHIEF or not chief.direct_work_capable:
            raise PermissionError(f'{chief_agent_id} is not an authorized working Regional Chief')
        completed = self.tasks.complete(task_id, chief.agent_id, output_artifact_ids=output_artifact_ids)
        event = self.ledger.append(
            EventKind.CHIEF_DIRECT_WORK, source_agent_id=chief.agent_id, target_agent_id=chief.agent_id,
            region=chief.region, object_refs=tuple(output_artifact_ids),
            payload={'task_id': task_id, 'output_artifact_ids': list(output_artifact_ids), 'mode': 'direct_work'},
        )
        return {'chief_agent_id': chief.agent_id, 'task_id': completed.task_id, 'event_id': event.event_id, 'output_artifact_ids': completed.output_artifact_ids}

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
            'registry': self.registry.to_state(), 'ledger': self.ledger.to_state(),
            'authority': self.authority.to_state(), 'memory': self.memory.to_state(),
            'tasks': self.tasks.to_state(), 'scheduler': self.scheduler.to_state(),
            'evolution': self.evolution.to_state(), 'verification': self.verification.to_state(),
            'artifacts': self.artifacts.to_state(), 'external_cores': self.external_cores.to_state(),
            'self_models': self.self_models.to_state(), 'requirements': self.requirements.to_state(),
            'planning': self.planning.to_state(), 'architecture': self.architecture.to_state(),
            'adr': self.adr.to_state(), 'integration': self.integration.to_state(),
            'coding': self.coding.to_state(), 'debugging': self.debugging.to_state(),
            'ui': self.ui.to_state(), 'assurance': self.assurance.to_state(),
            'central': self.central.to_state(),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'OrganizationRuntime':
        registry = AgentRegistry.from_state(state['registry'])
        ledger = EventLedger.from_state(state['ledger'])
        authority = AuthorityGraph.from_state(registry, state['authority'])
        if authority.owner_of('frontend-ui-state') is None:
            authority.claim_owner('frontend-ui-state', 'frontend.chief')
        if authority.owner_of('ux-design-state') is None:
            authority.claim_owner('ux-design-state', 'ux.chief')
        memory = MemoryFabric.from_state(state['memory'])
        tasks = TaskGraph.from_state(state['tasks'], ledger=ledger, registry=registry, authority=authority)
        scheduler = WakeSleepScheduler.from_state(registry=registry, ledger=ledger, state=state['scheduler'])
        evolution = SkillEvolutionEngine.from_state(state['evolution'])
        verification = VerificationAuthority.from_state(registry=registry, ledger=ledger, state=state['verification'])
        artifacts = ArtifactStore.from_state(state.get('artifacts', {}))
        external_cores = ExternalCoreRegistry.from_state(state.get('external_cores', {}))
        self_models = SelfModelRegistry.from_state(registry, state.get('self_models', {}))
        requirements = RequirementsControlPlane.from_state(
            registry=registry, authority=authority, ledger=ledger, state=state.get('requirements', {}),
        )
        planning = PlanningControlPlane.from_state(
            registry=registry, authority=authority, ledger=ledger, tasks=tasks,
            requirements=requirements, state=state.get('planning', {}),
        )
        architecture = ArchitectureControlPlane.from_state(
            registry=registry, authority=authority, ledger=ledger, state=state.get('architecture', {}),
        )
        adr = ADRDecisionLedger.from_state(
            registry=registry, authority=authority, architecture=architecture, state=state.get('adr', {}),
        )
        integration = IntegrationControlPlane.from_state(
            registry=registry, authority=authority, architecture=architecture, state=state.get('integration', {}),
        )
        coding = UICodingControlPlane.from_state(
            registry=registry, ledger=ledger, tasks=tasks, evolution=evolution, planning=planning,
            architecture=architecture, integration=integration, state=state.get('coding', {}),
        )
        debugging = DebugControlPlane.from_state(
            registry=registry, ledger=ledger, tasks=tasks, evolution=evolution,
            coding=coding, state=state.get('debugging', {}),
        )
        ui = UIControlPlane.from_state(
            registry=registry, ledger=ledger, tasks=tasks, evolution=evolution, artifacts=artifacts,
            authority=authority, planning=planning, architecture=architecture, coding=coding,
            state=state.get('ui', {}),
        )
        assurance = AssuranceControlPlane.from_state(
            registry=registry, ledger=ledger, authority=authority, artifacts=artifacts,
            evolution=evolution, verification=verification, state=state.get('assurance', {}),
        )
        central = None
        if 'central' in state:
            central = CentralControlPlane.from_state(
                registry=registry, ledger=ledger, authority=authority, tasks=tasks,
                scheduler=scheduler, artifacts=artifacts, external_cores=external_cores,
                self_models=self_models, evolution=evolution, verification=verification,
                state=state['central'],
            )
        return cls(
            registry=registry, ledger=ledger, authority=authority, memory=memory, tasks=tasks,
            scheduler=scheduler, evolution=evolution, verification=verification, artifacts=artifacts,
            external_cores=external_cores, self_models=self_models, central=central,
            requirements=requirements, planning=planning, architecture=architecture, adr=adr,
            integration=integration, coding=coding, debugging=debugging, ui=ui, assurance=assurance,
        )
