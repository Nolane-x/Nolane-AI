from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .facades import build_active_facade_bindings
from .manifests import build_component_manifests


class ImplementationStatus(str, Enum):
    CANONICAL_NATIVE = "canonical_native"
    COMPATIBILITY_FACADE = "compatibility_facade"
    LEGACY_INTERNAL = "legacy_internal"
    FROZEN_ASSET = "frozen_asset"
    HISTORICAL_ONLY = "historical_only"


@dataclass(frozen=True, slots=True)
class ComponentImplementationRecord:
    component_id: str
    component_version: str
    status: ImplementationStatus
    canonical_module: str | None
    legacy_sources: tuple[str, ...]
    canonical_write_authority: bool
    notes: str

    def __post_init__(self) -> None:
        if not self.component_id.strip() or not self.component_version.strip() or not self.notes.strip():
            raise ValueError("implementation record requires component/version/notes")
        if self.status is ImplementationStatus.CANONICAL_NATIVE and self.canonical_module is None:
            raise ValueError("canonical-native implementation requires canonical module")
        if self.status is ImplementationStatus.HISTORICAL_ONLY and self.canonical_write_authority:
            raise ValueError("historical-only component cannot hold canonical write authority")
        if self.canonical_write_authority and self.status is not ImplementationStatus.CANONICAL_NATIVE:
            raise ValueError("canonical write authority requires canonical-native implementation")

    def to_state(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_version": self.component_version,
            "status": self.status.value,
            "canonical_module": self.canonical_module,
            "legacy_sources": list(self.legacy_sources),
            "canonical_write_authority": self.canonical_write_authority,
            "notes": self.notes,
        }


_NATIVE: dict[str, tuple[str, tuple[str, ...], str]] = {
    "core.canonical_digest": (
        "nolane.core.canonical_digest",
        ("cogcoder/organization/types.py",),
        "Native canonical JSON serialization and SHA-256 content identity; mixed historical types module bridges the two helper identities while unrelated schemas remain explicit debt.",
    ),
    "schemas.identity": (
        "nolane.schemas.identity",
        ("cogcoder/organization/types.py",),
        "Native permanent identity rank/status/parameter/namespace schema unit; mixed historical types module bridges exact objects while event/context/skill schemas remain separate debt.",
    ),
    "organization.identity": (
        "nolane.organization.identity",
        ("cogcoder/organization/registry.py", "cogcoder/organization/blueprint.py", "cogcoder/organization/types.py"),
        "Canonical 67-identity manifest authority plus native AgentRegistry implementation; historical registry is a compatibility bridge and blueprint remains a parity oracle.",
    ),
    "organization.authority": (
        "nolane.organization.authority",
        ("cogcoder/organization/authority.py",),
        "Native ownership, block, override and fail-closed write authority; historical module bridges to canonical class identity.",
    ),
    "organization.events": (
        "nolane.organization.events",
        ("cogcoder/organization/events.py",),
        "Native EventKind/CognitiveEvent schema authority plus causal event ledger, subscriptions, delivery and state round-trip; historical events and mixed types surfaces bridge exact canonical identities.",
    ),
    "organization.tasks": (
        "nolane.organization.tasks",
        ("cogcoder/organization/tasks.py",),
        "Native task DAG and execution projection; plan revision is now a read-only projection of external.planning authority, while the historical tasks module remains a compatibility bridge.",
    ),
    "organization.lifecycle": (
        "nolane.organization.lifecycle",
        ("cogcoder/organization/scheduler.py",),
        "Native persistent wake/sleep/checkpoint lifecycle; historical scheduler module is a compatibility bridge.",
    ),
    "organization.coordination.leases": (
        "nolane.organization.coordination_leases",
        ("cogcoder/organization/coordination_leases.py",),
        "Native lease epoch, fencing, heartbeat and stale-agent authority.",
    ),
    "organization.coordination.delivery": (
        "nolane.organization.coordination_delivery",
        ("cogcoder/organization/coordination_delivery.py",),
        "Native causal delivery and acknowledgement authority.",
    ),
    "organization.coordination.conflicts": (
        "nolane.organization.coordination_conflicts",
        ("cogcoder/organization/coordination_conflicts.py",),
        "Native artifact-authority conflict packet, claim and resolution authority.",
    ),
    "organization.coordination": (
        "nolane.organization.coordination",
        ("cogcoder/organization/coordination.py",),
        "Native bounded coordination composition over canonical task, lifecycle, lease, delivery and conflict primitives.",
    ),
    "organization.central": (
        "nolane.organization.central",
        (
            "cogcoder/organization/central.py",
            "cogcoder/organization/central_access.py",
            "cogcoder/organization/central_conflicts.py",
            "cogcoder/organization/central_resources.py",
            "cogcoder/organization/central_state.py",
        ),
        "Native Nolane Central aggregate plus access, conflict, resource and world-state authority; historical Central modules are compatibility bridges preserving public class identity.",
    ),
    "organization.runtime": (
        "nolane.runtime",
        ("cogcoder/organization/runtime.py", "cogcoder/organization/runtime_core.py"),
        "Canonical authority wrapper over accepted implementation with manifest identity, MasterPlanGraph and LeaseCoordinator boundaries.",
    ),
    "organization.temporary_work_units": (
        "nolane.work_units",
        ("cogcoder/organization/foundry.py", "cogcoder/organization/foundry_profiles.py", "cogcoder/organization/foundry_resources.py"),
        "Canonical non-agent Work Unit API over accepted bounded Foundry lifecycle/resource/evidence implementation.",
    ),
    "external.assurance": (
        "nolane.external_core.assurance",
        (
            "cogcoder/organization/assurance.py",
            "cogcoder/organization/assurance_evidence.py",
            "cogcoder/organization/assurance_profiles.py",
        ),
        "Native three-module assurance policy, independent challenge/evidence, profile routing, blocking/override and promotion authority over canonical artifact, authority, event, skill, identity, digest and verification dependencies; historical assurance modules bridge exact semantic public identities.",
    ),
    "external.individual_evolution": (
        "nolane.external_core.individual_evolution",
        (
            "cogcoder/organization/individual_evolution.py",
            "cogcoder/organization/evolution_profiles.py",
        ),
        "Native individual-evolution lineage, profile, learning, self-model, neural challenger and longitudinal benchmark authority over canonical assurance, verification, identity, skill, experience, self-model, evidence and digest dependencies; historical individual-evolution/profile modules bridge exact semantic public identities.",
    ),
    "external.research": (
        "nolane.external_core.research",
        (
            "cogcoder/organization/research.py",
            "cogcoder/organization/research_profiles.py",
            "cogcoder/organization/research_provenance.py",
        ),
        "Native Research routing, source/provenance/freshness/contradiction authority, synthesis and assurance-gated engineering handoff over canonical artifacts, assurance, skills, identity and digest dependencies; historical Research modules bridge exact semantic public identities.",
    ),
    "external.operations": (
        "nolane.external_core.operations",
        (
            "cogcoder/organization/operations.py",
            "cogcoder/organization/operations_profiles.py",
            "cogcoder/organization/data_operations.py",
            "cogcoder/organization/infrastructure_operations.py",
            "cogcoder/organization/reliability_operations.py",
        ),
        "Native Operations readiness, twelve-profile routing, data migration/persistence/consistency, reproducible build/release/observability and reliability/performance authority over canonical artifacts, assurance, skills, identity and digest dependencies; historical Operations modules bridge exact semantic public identities.",
    ),
    "external.cognitive_library": (
        "nolane.external_core.cognitive_library",
        (
            "cogcoder/r253_operator_catalog.py",
            "cogcoder/r256_operator_dsl.py",
            "cogcoder/r257_vocabulary.py",
        ),
        "Native typed operator catalog, bounded expression DSL, learned abstraction vocabulary and deterministic cognitive-library snapshot authority; R2.53/R2.56/R2.57 remain historical parity and provenance oracles.",
    ),
    "external.causal": (
        "nolane.external_core.causal",
        (
            "cogcoder/r258_intervention_discovery.py",
            "cogcoder/r262_complementary_experiment_program.py",
        ),
        "Native bounded positional intervention identity, complementary causal-program structure discovery and evidence-bound deterministic causal-program ledger over canonical Cognitive Library and Evidence authority; R2.58/R2.62 remain historical parity and provenance oracles.",
    ),
    "external.artifacts": (
        "nolane.external_core.artifacts",
        ("cogcoder/organization/artifacts.py",),
        "Native content-addressed artifact records/store with deterministic evidence ordering, metadata encoding and state round-trip; historical artifact module is a compatibility bridge.",
    ),
    "external.evidence": (
        "nolane.external_core.evidence",
        ("cogcoder/organization/types.py",),
        "Native verification evidence primitive with preserved historical import identity and state semantics; mixed historical types module bridges to canonical class authority.",
    ),
    "external.experience": (
        "nolane.memory.experience",
        ("cogcoder/organization/experience.py",),
        "Native identity-owned experience and evidence-governed attribution ledger over canonical Identity, Events, Evidence and digest primitives; historical experience module bridges all public object identities.",
    ),
    "external.self_model": (
        "nolane.external_core.self_model",
        ("cogcoder/organization/self_model.py",),
        "Native evidence-gated permanent-agent self-model registry with preserved initialization, revision and state semantics; historical module bridges both public object identities.",
    ),
    "external.skills": (
        "nolane.memory.skills",
        ("cogcoder/organization/evolution.py", "cogcoder/organization/types.py"),
        "Native skill scope, deterministic skill records and evidence-governed promotion/quarantine/visibility engine; historical evolution and mixed types surfaces bridge exact canonical identities without whole-file types ownership.",
    ),
    "external.memory.fabric": (
        "nolane.memory.fabric",
        ("cogcoder/organization/memory.py", "cogcoder/organization/types.py"),
        "Native scoped memory schema and fabric with preserved visibility, promotion, lifecycle-status mutation and state round-trip; historical memory/types surfaces bridge to canonical authority.",
    ),
    "external.memory.lifecycle": (
        "nolane.memory.lifecycle",
        ("cogcoder/organization/memory_lifecycle.py",),
        "Native governed memory lifecycle receipts and semantic relation graph with canonical Memory/Identity/Event dependencies; historical lifecycle module bridges all public object identities.",
    ),
    "external.memory.retrieval": (
        "nolane.memory.retrieval",
        ("cogcoder/organization/memory_retrieval.py",),
        "Native bounded memory selection budget, receipt and retrieval engine over canonical Memory Fabric and Lifecycle relation graph; historical retrieval module bridges all public object identities.",
    ),
    "external.knowledge": (
        "nolane.memory.knowledge",
        ("cogcoder/knowledge_types.py", "cogcoder/knowledge_store.py", "cogcoder/knowledge_ledger.py", "cogcoder/knowledge_adapters.py"),
        "Native provenance-aware deterministic Knowledge fabric reconstructed from the dedicated R2 types/store/ledger/adapters lineage; historical modules bridge exact public identities while R2.54 Cognitive Retrieval remains outside this ownership boundary.",
    ),
    "external.epistemic": (
        "nolane.external_core.epistemic",
        ("cogcoder/epistemic_workspace.py",),
        "Native version-aware evidence workspace with fail-closed provenance, source/version supersession, corroboration, contested beliefs, conflicts and narrow missing-query generation; historical R2.2 module bridges exact public identities.",
    ),
    "external.requirements": (
        "nolane.external_core.requirements",
        ("cogcoder/organization/requirements.py",),
        "Native evidence-bearing requirement graph, revision and Requirements Chief authority with deterministic digest/state semantics; historical organization module bridges exact public object identities.",
    ),
    "external.planning": (
        "nolane.external_core.planning",
        ("cogcoder/organization/planning.py",),
        "Native evidence-bearing master plan graph and Planning authority with deterministic revision, rollback, gap, task-link and delta semantics; TaskGraph receives a read-only revision projection and historical Planning bridges exact public identities.",
    ),
    "external.architecture": (
        "nolane.external_core.architecture",
        ("cogcoder/organization/architecture.py",),
        "Native evidence-bearing Architecture graph and control plane with deterministic revisions, canonical digests, atomic dependency validation, exact state restoration and owner-gated writes; historical Architecture bridges exact public identities.",
    ),
    "external.integration": (
        "nolane.external_core.integration",
        ("cogcoder/organization/integration.py",),
        "Native evidence-gated Integration candidate graph and control plane with deterministic dependency ordering, stale-architecture protection, compatibility/dependency/conflict gates, canonical receipt digests and exact state restoration; historical Integration bridges exact public identities.",
    ),
    "external.invokable_cores": (
        "nolane.external_core.invokable",
        ("cogcoder/organization/external_core.py",),
        "Native invokable-core schema and registry over canonical AgentRegistry authority with deterministic state round-trip and fail-closed conflicting registration; historical External Core module bridges exact public identities.",
    ),
    "external.context": (
        "nolane.memory.context",
        (
            "cogcoder/organization/context.py",
            "cogcoder/organization/context_intelligence.py",
            "cogcoder/organization/memory_profiles.py",
            "cogcoder/organization/memory_context.py",
            "cogcoder/organization/memory_context_adapter.py",
        ),
        "Native bounded base context compiler, semantic delta/continuity intelligence, Memory/Context profile routing, contradiction-repair control plane and memory-aware adapter over canonical event, identity, memory, lifecycle, retrieval, skill, task and digest authorities; historical context modules bridge exact semantic public identities.",
    ),
    "external.execution.workspace": (
        "nolane.external_core.execution_workspace",
        ("cogcoder/organization/execution_workspace.py",),
        "Native isolated Git-worktree workspace authority over canonical digest identity with bounded command execution, path confinement and exact historical object bridge.",
    ),
    "external.execution.executor": (
        "nolane.external_core.execution_executor",
        ("cogcoder/organization/execution_tools.py",),
        "Native fail-closed external-core executor over canonical artifact, identity, invokable-core, execution-schema/workspace, coding-claim/patch and digest authorities; historical execution-tools module bridges exact public identities.",
    ),
    "external.execution.control": (
        "nolane.external_core.execution",
        ("cogcoder/organization/execution.py",),
        "Native bounded execution-session control plane over canonical inference, executor, workspace, artifact, identity, task and execution-schema authorities; historical execution module bridges exact semantic public identities.",
    ),
    "external.coding.claims": (
        "nolane.external_core.coding_claims",
        ("cogcoder/organization/code_claims.py",),
        "Native exclusive source-mutation claim scope, conflict detection, release/abort authority and fail-closed snapshot restoration; historical code-claims module bridges exact public identities.",
    ),
    "external.coding.patches": (
        "nolane.external_core.coding_patches",
        ("cogcoder/organization/coding_patches.py",),
        "Native patch candidates, claim-covered source scopes, content-addressed tool invocation receipts and fail-closed patch-ledger restoration over canonical coding-claim and digest authority; historical coding-patches module bridges exact public identities.",
    ),
    "external.coding.control": (
        "nolane.external_core.coding",
        ("cogcoder/organization/coding.py",),
        "Native coding assignment, source-claim, patch-readiness and personal-skill control plane over canonical profile, claim, patch, planning, architecture, skill, identity, task, event and digest authorities; historical coding module bridges exact semantic public identities.",
    ),
    "external.debugging": (
        "nolane.external_core.debugging",
        (
            "cogcoder/organization/debugging.py",
            "cogcoder/organization/debug_evidence.py",
            "cogcoder/organization/debug_hypotheses.py",
            "cogcoder/organization/debug_profiles.py",
        ),
        "Native failure-case, reproduction/evidence, root-cause hypothesis, profile routing, coding handoff, resolution and personal-skill debugging authority over canonical coding, skills, identity, task, event and digest authorities; historical debugging modules bridge exact semantic public identities.",
    ),
    "external.ui_ux": (
        "nolane.external_core.ui_ux",
        (
            "cogcoder/organization/ui.py",
            "cogcoder/organization/ui_coding.py",
            "cogcoder/organization/ui_design.py",
            "cogcoder/organization/ui_observations.py",
            "cogcoder/organization/ui_profiles.py",
        ),
        "Native UI/UX assignment, cross-region coding grant, render observation, authoritative UX flow, quality/readiness and personal-skill control authority over canonical coding, artifacts, skills, identity, authority, events and digest dependencies; historical UI modules bridge exact semantic public identities.",
    ),
    "evaluation.regimes": (
        "nolane.evaluation.regimes",
        ("cogcoder/organization/evaluation_regimes.py",),
        "Native benchmark regime, budget, freshness, provenance and evaluation-mode registry authority over canonical digest identity; historical evaluation-regimes module bridges exact public identities.",
    ),
    "evaluation.evidence": (
        "nolane.evaluation.evidence",
        ("cogcoder/organization/evaluation_evidence.py",),
        "Native evaluation observation, matched-budget comparison, organization-superiority, ablation and evidence-ledger authority over canonical regime, identity, verification-evidence and digest dependencies; historical evaluation-evidence module bridges exact semantic public identities.",
    ),
    "evaluation.stress": (
        "nolane.evaluation.stress",
        ("cogcoder/organization/evaluation_stress.py",),
        "Native long-horizon stress scenario, observation, suite-assessment and ledger authority over canonical identity, verification-evidence and digest dependencies; historical evaluation-stress module bridges exact semantic public identities.",
    ),
    "evaluation.claims": (
        "nolane.evaluation.claims",
        ("cogcoder/organization/evaluation_claims.py",),
        "Native claim-classification, claim assessment, readiness-gate and claim-boundary authority over canonical evaluation evidence, regimes, stress, identity and digest dependencies; historical evaluation-claims module bridges exact semantic public identities.",
    ),
    "evaluation.parameters": (
        "nolane.evaluation.parameters",
        ("cogcoder/organization/evaluation_parameters.py",),
        "Native physical/logical parameter-footprint accounting and evidence-governed scaling proposal/decision authority over canonical evaluation evidence, regimes, identity and digest dependencies; historical evaluation-parameters module bridges exact semantic public identities.",
    ),
    "evaluation.release": (
        "nolane.evaluation.release",
        ("cogcoder/organization/evaluation_release.py",),
        "Native evaluation-release, reproduction-receipt and external-reproducibility ledger authority over canonical artifacts, evidence, parameters, regimes, stress, identity and digest dependencies; historical evaluation-release module bridges exact semantic public identities.",
    ),
    "evaluation.scaling": (
        "nolane.evaluation.scaling",
        ("cogcoder/organization/evaluation.py",),
        "Native evaluation-scaling composition authority over canonical artifacts, claims, evidence, parameters, regimes, release, stress and organization identity dependencies; historical evaluation module bridges exact control-plane identity.",
    ),
    "evaluation.campaign": (
        "nolane.evaluation.campaign",
        (
            "cogcoder/organization/campaign.py",
            "cogcoder/organization/campaign_repository.py",
            "cogcoder/organization/campaign_tasks.py",
            "cogcoder/organization/campaign_contamination.py",
            "cogcoder/organization/campaign_runner.py",
            "cogcoder/organization/campaign_reproduction.py",
            "cogcoder/organization/campaign_ingest.py",
        ),
        "Native seven-module evaluation-campaign authority over frozen repository snapshots, task manifests/partitions, contamination checks, run receipts, reproduction evidence and canonical scaling ingestion; all historical campaign modules bridge exact semantic public identities.",
    ),
    "neural.inference_bridge": (
        "nolane.neural.inference_bridge",
        ("cogcoder/organization/execution_inference.py",),
        "Native versioned context-to-neural inference adapter over canonical execution schemas, context, identity and digest authority; historical execution-inference module bridges exact public identities while execution control is independently versioned.",
    ),
    "external.verification": (
        "nolane.external_core.verification",
        ("cogcoder/organization/verification.py",),
        "Native bounded candidate evaluation, promotion and rollback authority over canonical identity/event primitives; historical verification module is a compatibility bridge.",
    ),
}

_HISTORICAL_ONLY: dict[str, tuple[str, ...]] = {
    "external.capability_acquisition": ("historical capability-acquisition mechanisms; extraction not yet accepted",),
    "external.experimentation": ("historical active experimentation mechanisms; extraction not yet accepted",),
    "external.transfer_meta": ("historical transfer/meta-learning mechanisms; extraction not yet accepted",),
}

_FROZEN_ASSET: dict[str, tuple[str, ...]] = {
    "neural.shared": ("model/neural-r2.3",),
}

_LEGACY_SOURCE_HINTS: dict[str, tuple[str, ...]] = {}


def build_component_implementation_ledger() -> dict[str, ComponentImplementationRecord]:
    components = {row.component_id: row for row in build_component_manifests()}
    facades = {row.component_id: row for row in build_active_facade_bindings()}
    unknown_facades = sorted(set(facades) - set(components))
    if unknown_facades:
        raise ValueError(f"active facade references undeclared components: {unknown_facades!r}")

    ledger: dict[str, ComponentImplementationRecord] = {}
    for component_id, manifest in components.items():
        if component_id in _NATIVE:
            module, legacy_sources, notes = _NATIVE[component_id]
            row = ComponentImplementationRecord(
                component_id,
                str(manifest.version),
                ImplementationStatus.CANONICAL_NATIVE,
                module,
                legacy_sources,
                True,
                notes,
            )
        elif component_id in _HISTORICAL_ONLY:
            row = ComponentImplementationRecord(
                component_id,
                str(manifest.version),
                ImplementationStatus.HISTORICAL_ONLY,
                None,
                _HISTORICAL_ONLY[component_id],
                False,
                "Manifest reserves the semantic boundary; no dedicated active implementation is claimed yet.",
            )
        elif component_id in _FROZEN_ASSET:
            row = ComponentImplementationRecord(
                component_id,
                str(manifest.version),
                ImplementationStatus.FROZEN_ASSET,
                None,
                _FROZEN_ASSET[component_id],
                False,
                "Accepted frozen neural asset with separate runtime adapter and checkpoint authority.",
            )
        elif component_id in facades:
            facade = facades[component_id]
            row = ComponentImplementationRecord(
                component_id,
                str(manifest.version),
                ImplementationStatus.COMPATIBILITY_FACADE,
                facade.canonical_module,
                (facade.legacy_module.replace(".", "/") + ".py",),
                False,
                "Public canonical import exists but executable source remains accepted legacy implementation pending cutover receipt.",
            )
        else:
            row = ComponentImplementationRecord(
                component_id,
                str(manifest.version),
                ImplementationStatus.LEGACY_INTERNAL,
                None,
                _LEGACY_SOURCE_HINTS.get(component_id, ()),
                False,
                "Semantic component is active/internal or composition-only, but no dedicated canonical source module is accepted yet.",
            )
        ledger[component_id] = row

    if set(ledger) != set(components):
        raise ValueError("implementation ledger must cover every canonical component exactly once")
    return ledger
