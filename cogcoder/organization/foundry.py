from __future__ import annotations

from typing import Any, Mapping

from .artifacts import ArtifactStore
from .assurance import AssuranceControlPlane
from .coordination import CoordinationControlPlane
from .evolution import SkillEvolutionEngine, SkillRecord
from .foundry_evidence import (
    BenefitMode,
    FoundryBenefitAssessment,
    FoundryBenefitObservation,
    FoundryEvidenceLedger,
    FoundryHandoffReceipt,
    FoundryOutputReceipt,
    FoundryVerificationReceipt,
)
from .foundry_lifecycle import FoundryLifecycleLedger, FoundryLifecycleReceipt, FoundryStatus
from .foundry_memory import EphemeralScratchVault, ScratchDisposition, ScratchEntry
from .foundry_profiles import EphemeralIdentityManifest, FoundryProfileRegistry, SpawnRequest
from .foundry_resources import FoundryBudget, FoundryResourceGovernor, FoundryResourceKind, ResourceUsageReceipt
from .individual_evolution import IndividualEvolutionControlPlane
from .registry import AgentRegistry
from .tasks import TaskGraph
from .types import EvidenceRecord


_TERMINAL = {
    FoundryStatus.RETIRED,
    FoundryStatus.REJECTED,
    FoundryStatus.EXHAUSTED,
    FoundryStatus.QUARANTINED,
    FoundryStatus.ABORTED,
}


class FoundryControlPlane:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        tasks: TaskGraph,
        coordination: CoordinationControlPlane,
        artifacts: ArtifactStore,
        assurance: AssuranceControlPlane,
        evolution: SkillEvolutionEngine,
        individual_evolution: IndividualEvolutionControlPlane,
        profiles: FoundryProfileRegistry | None = None,
        resources: FoundryResourceGovernor | None = None,
        lifecycle: FoundryLifecycleLedger | None = None,
        scratch: EphemeralScratchVault | None = None,
        evidence: FoundryEvidenceLedger | None = None,
    ) -> None:
        self.registry = registry
        self.tasks = tasks
        self.coordination = coordination
        self.artifacts = artifacts
        self.assurance = assurance
        self.evolution = evolution
        self.individual_evolution = individual_evolution
        self.profiles = profiles or FoundryProfileRegistry(
            registry=registry, tasks=tasks, coordination=coordination,
        )
        self.resources = resources or FoundryResourceGovernor()
        self.lifecycle = lifecycle or FoundryLifecycleLedger(
            registry=registry, manifests=self.profiles.manifests(),
        )
        self.scratch = scratch or EphemeralScratchVault()
        self.evidence = evidence or FoundryEvidenceLedger(
            registry=registry, artifacts=artifacts, assurance=assurance,
        )
        self._validate_component_alignment()

    def _validate_component_alignment(self) -> None:
        manifests = self.profiles.manifests()
        manifest_ids = {row.ephemeral_id for row in manifests}
        for manifest in manifests:
            self.registry.get(manifest.sponsor_agent_id)
            try:
                self.resources.budget_for(manifest.ephemeral_id)
            except KeyError:
                raise ValueError('Foundry manifest is missing resource registration')
            self.lifecycle.manifest(manifest.ephemeral_id)
        active = set(self.resources.active_ephemeral_ids())
        if not active.issubset(manifest_ids):
            raise ValueError('Foundry active resource registration references unknown manifest')
        for ephemeral_id in active:
            if self.lifecycle.status(ephemeral_id) not in {
                FoundryStatus.ACTIVE, FoundryStatus.VERIFYING, FoundryStatus.HANDOFF,
            }:
                raise ValueError('Foundry active resource reservation disagrees with lifecycle status')

    def request_spawn(
        self,
        *,
        sponsor_agent_id: str,
        parent_task_id: str | None,
        template_id: str,
        mission: str,
        team_id: str,
        budget: FoundryBudget,
        requested_tools: tuple[str, ...] = (),
        requested_external_cores: tuple[str, ...] = (),
        allowed_artifact_kinds: tuple[str, ...] = (),
        current_token: int = 0,
    ) -> SpawnRequest:
        return self.profiles.request(
            sponsor_agent_id=sponsor_agent_id, parent_task_id=parent_task_id,
            template_id=template_id, mission=mission, team_id=team_id, budget=budget,
            requested_tools=requested_tools,
            requested_external_cores=requested_external_cores,
            allowed_artifact_kinds=allowed_artifact_kinds,
            current_token=current_token,
        )

    def approve_spawn(self, request_id: str, *, actor_agent_id: str) -> SpawnRequest:
        return self.profiles.approve(request_id, actor_agent_id)

    def instantiate(self, request_id: str, *, current_token: int) -> EphemeralIdentityManifest:
        request = self.profiles.get_request(request_id)
        manifest = self.profiles.instantiate(request_id, current_token=current_token)
        self.resources.register_manifest(
            manifest.ephemeral_id, team_id=manifest.team_id,
            sponsor_agent_id=manifest.sponsor_agent_id, budget=request.budget,
        )
        self.lifecycle.register_manifest(manifest)
        self.scratch.register(manifest.ephemeral_id, team_id=manifest.team_id)
        return manifest

    def manifests(self) -> tuple[EphemeralIdentityManifest, ...]:
        return self.profiles.manifests()

    def spawn_requests(self) -> tuple[SpawnRequest, ...]:
        return self.profiles.requests()

    def outputs(self) -> tuple[FoundryOutputReceipt, ...]:
        return self.evidence.outputs()

    def status(self, ephemeral_id: str) -> FoundryStatus:
        return self.lifecycle.status(ephemeral_id)

    def _manifest(self, ephemeral_id: str) -> EphemeralIdentityManifest:
        return self.profiles.get_manifest(ephemeral_id)

    def _operational(self, ephemeral_id: str, *, allow_verifying: bool = True) -> EphemeralIdentityManifest:
        manifest = self._manifest(ephemeral_id)
        status = self.status(ephemeral_id)
        allowed = {FoundryStatus.ACTIVE}
        if allow_verifying:
            allowed.add(FoundryStatus.VERIFYING)
        if status not in allowed:
            raise PermissionError(f'Foundry worker is not operational: {status.value}')
        if self.resources.remaining(ephemeral_id, FoundryResourceKind.LIFETIME_TOKEN) <= 0:
            raise PermissionError('Foundry worker lifetime budget is exhausted')
        return manifest

    def activate(self, ephemeral_id: str, *, actor_agent_id: str) -> FoundryLifecycleReceipt:
        manifest = self._manifest(ephemeral_id)
        if self.status(ephemeral_id) is not FoundryStatus.INSTANTIATED:
            raise PermissionError('only instantiated Foundry worker can activate')
        self.resources.reserve_active(ephemeral_id)
        try:
            return self.lifecycle.transition(
                ephemeral_id, FoundryStatus.ACTIVE, actor_agent_id=actor_agent_id,
                reason='temporary specialist activated',
            )
        except Exception:
            self.resources.release_active(ephemeral_id)
            raise

    def begin_verification(self, ephemeral_id: str, *, actor_agent_id: str) -> FoundryLifecycleReceipt:
        return self.lifecycle.transition(
            ephemeral_id, FoundryStatus.VERIFYING, actor_agent_id=actor_agent_id,
            reason='temporary specialist output entered verification',
        )

    def mark_handoff(self, ephemeral_id: str, *, actor_agent_id: str) -> FoundryLifecycleReceipt:
        return self.lifecycle.transition(
            ephemeral_id, FoundryStatus.HANDOFF, actor_agent_id=actor_agent_id,
            reason='temporary specialist output entered permanent handoff',
        )

    def quarantine(self, ephemeral_id: str, *, actor_agent_id: str, reason: str) -> FoundryLifecycleReceipt:
        row = self.lifecycle.transition(
            ephemeral_id, FoundryStatus.QUARANTINED,
            actor_agent_id=actor_agent_id, reason=str(reason),
        )
        self.resources.release_active(ephemeral_id)
        self.scratch.retire(ephemeral_id, ScratchDisposition.ARCHIVE_QUARANTINE)
        return row

    def retire(
        self,
        ephemeral_id: str,
        *,
        actor_agent_id: str,
        scratch_policy: ScratchDisposition,
    ) -> FoundryLifecycleReceipt:
        row = self.lifecycle.transition(
            ephemeral_id, FoundryStatus.RETIRED,
            actor_agent_id=actor_agent_id, reason='temporary specialist retired',
        )
        self.resources.release_active(ephemeral_id)
        self.scratch.retire(ephemeral_id, ScratchDisposition(scratch_policy))
        return row

    def retired_ephemeral_ids(self) -> tuple[str, ...]:
        return tuple(sorted(
            row.ephemeral_id for row in self.manifests()
            if self.status(row.ephemeral_id) is FoundryStatus.RETIRED
        ))

    def authorize_tool(self, ephemeral_id: str, tool: str) -> bool:
        manifest = self._operational(ephemeral_id)
        if str(tool) not in manifest.allowed_tools:
            raise PermissionError('Foundry tool is outside manifest capability envelope')
        return True

    def authorize_external_core(self, ephemeral_id: str, core: str) -> bool:
        manifest = self._operational(ephemeral_id)
        if str(core) not in manifest.allowed_external_cores:
            raise PermissionError('Foundry external core is outside manifest capability envelope')
        return True

    def consume(
        self,
        ephemeral_id: str,
        resource_kind: FoundryResourceKind,
        units: int,
        *,
        actor_ephemeral_id: str,
    ) -> ResourceUsageReceipt:
        self._operational(ephemeral_id)
        receipt = self.resources.consume(
            ephemeral_id, resource_kind, units,
            actor_ephemeral_id=actor_ephemeral_id,
        )
        if (
            FoundryResourceKind(resource_kind) is FoundryResourceKind.LIFETIME_TOKEN
            and receipt.remaining == 0
            and self.status(ephemeral_id) not in _TERMINAL
        ):
            manifest = self._manifest(ephemeral_id)
            self.lifecycle.transition(
                ephemeral_id, FoundryStatus.EXHAUSTED,
                actor_agent_id=manifest.sponsor_agent_id,
                reason='Foundry lifetime budget exhausted',
            )
            self.resources.release_active(ephemeral_id)
            self.scratch.retire(ephemeral_id, ScratchDisposition.ARCHIVE_QUARANTINE)
        return receipt

    def write_scratch(self, ephemeral_id: str, text: str, *, actor_ephemeral_id: str) -> ScratchEntry:
        self._operational(ephemeral_id)
        return self.scratch.write(ephemeral_id, text, actor_ephemeral_id=actor_ephemeral_id)

    def emit_output(
        self,
        ephemeral_id: str,
        *,
        kind: str,
        content: str,
        evidence_refs: tuple[str, ...],
    ) -> FoundryOutputReceipt:
        manifest = self._operational(ephemeral_id)
        return self.evidence.emit_output(
            manifest, kind=kind, content=content, evidence_refs=evidence_refs,
        )

    def record_verification(self, output_id: str, evidence: EvidenceRecord) -> FoundryVerificationReceipt:
        return self.evidence.record_verification(output_id, evidence)

    def _assert_current_lineage(
        self,
        *,
        parent_task_id: str | None,
        parent_lease_id: str | None,
        parent_lease_epoch: int | None,
    ) -> None:
        if parent_task_id is None:
            if parent_lease_id is not None or parent_lease_epoch is not None:
                raise ValueError('Foundry global scope cannot carry parent lease lineage')
            return
        try:
            current = self.coordination.current_lease(parent_task_id)
        except KeyError as exc:
            raise PermissionError('Foundry parent task no longer has active lease') from exc
        if current.lease_id != parent_lease_id or current.epoch != parent_lease_epoch:
            raise PermissionError('Foundry parent lease lineage is stale')

    def prepare_handoff(self, output_id: str, *, target_agent_id: str) -> FoundryHandoffReceipt:
        output = self.evidence.get_output(output_id)
        self._operational(output.ephemeral_id)
        self._assert_current_lineage(
            parent_task_id=output.parent_task_id,
            parent_lease_id=output.parent_lease_id,
            parent_lease_epoch=output.parent_lease_epoch,
        )
        return self.evidence.prepare_handoff(output_id, target_agent_id=target_agent_id)

    def authorize_handoff(self, handoff_id: str, *, assurance_decision_id: str) -> FoundryHandoffReceipt:
        handoff = self.evidence.get_handoff(handoff_id)
        self._operational(handoff.ephemeral_id)
        self._assert_current_lineage(
            parent_task_id=handoff.parent_task_id,
            parent_lease_id=handoff.parent_lease_id,
            parent_lease_epoch=handoff.parent_lease_epoch,
        )
        return self.evidence.authorize_handoff(
            handoff_id, assurance_decision_id=assurance_decision_id,
        )

    def distill_skill(
        self,
        handoff_id: str,
        *,
        target_agent_id: str,
        name: str,
        body: str,
    ) -> SkillRecord:
        handoff = self.evidence.get_handoff(handoff_id)
        if not handoff.authorized:
            raise PermissionError('Foundry skill distillation requires authorized handoff')
        if handoff.target_agent_id != str(target_agent_id):
            raise PermissionError('Foundry handoff target does not match skill owner')
        self._operational(handoff.ephemeral_id)
        self._assert_current_lineage(
            parent_task_id=handoff.parent_task_id,
            parent_lease_id=handoff.parent_lease_id,
            parent_lease_epoch=handoff.parent_lease_epoch,
        )
        clean = tuple(
            row for row in self.evidence.verifications_for(handoff.output_id)
            if row.clean and row.independent
        )
        if not clean:
            raise PermissionError('Foundry distillation requires clean independent verification')
        target = self.registry.get(target_agent_id)
        return self.evolution.propose(
            owner_agent_id=target.agent_id, region=target.region,
            name=str(name), body=str(body),
        )

    def distill_unverified_text(self, *args: Any, **kwargs: Any) -> SkillRecord:
        raise PermissionError('Foundry raw/unverified text cannot bypass evidence-gated skill distillation')

    def record_benefit_observation(self, **kwargs: Any) -> FoundryBenefitObservation:
        return self.evidence.record_benefit_observation(**kwargs)

    def assess_benefit(self, baseline_observation_id: str, team_observation_id: str) -> FoundryBenefitAssessment:
        return self.evidence.assess_benefit(baseline_observation_id, team_observation_id)

    def to_state(self) -> dict[str, Any]:
        return {
            'profiles': self.profiles.to_state(),
            'resources': self.resources.to_state(),
            'lifecycle': self.lifecycle.to_state(),
            'scratch': self.scratch.to_state(),
            'evidence': self.evidence.to_state(),
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: AgentRegistry,
        tasks: TaskGraph,
        coordination: CoordinationControlPlane,
        artifacts: ArtifactStore,
        assurance: AssuranceControlPlane,
        evolution: SkillEvolutionEngine,
        individual_evolution: IndividualEvolutionControlPlane,
        state: Mapping[str, Any],
    ) -> 'FoundryControlPlane':
        profiles = FoundryProfileRegistry.from_state(
            registry=registry, tasks=tasks, coordination=coordination,
            state=state.get('profiles', {}),
        )
        resources = FoundryResourceGovernor.from_state(state.get('resources', {}))
        lifecycle = FoundryLifecycleLedger.from_state(
            registry=registry, manifests=profiles.manifests(), state=state.get('lifecycle', {}),
        )
        scratch = EphemeralScratchVault.from_state(state.get('scratch', {}))
        evidence = FoundryEvidenceLedger.from_state(
            registry=registry, artifacts=artifacts, assurance=assurance,
            state=state.get('evidence', {}),
        )
        if not state:
            return cls(
                registry=registry, tasks=tasks, coordination=coordination,
                artifacts=artifacts, assurance=assurance, evolution=evolution,
                individual_evolution=individual_evolution,
            )
        return cls(
            registry=registry, tasks=tasks, coordination=coordination,
            artifacts=artifacts, assurance=assurance, evolution=evolution,
            individual_evolution=individual_evolution, profiles=profiles, resources=resources,
            lifecycle=lifecycle, scratch=scratch, evidence=evidence,
        )
