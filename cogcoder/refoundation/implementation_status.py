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


def _native(
    module: str,
    legacy_sources: tuple[str, ...],
    notes: str | None = None,
) -> tuple[str, tuple[str, ...], str]:
    return (
        module,
        legacy_sources,
        notes or f"Canonical native authority is owned by {module}; listed historical sources remain provenance or compatibility surfaces only.",
    )


_NATIVE: dict[str, tuple[str, tuple[str, ...], str]] = {
    "core.canonical_digest": _native("nolane.core.canonical_digest", ("cogcoder/organization/types.py",)),
    "schemas.identity": _native("nolane.schemas.identity", ("cogcoder/organization/types.py",)),
    "organization.identity": _native("nolane.organization.identity", ("cogcoder/organization/registry.py", "cogcoder/organization/blueprint.py", "cogcoder/organization/types.py")),
    "organization.authority": _native("nolane.organization.authority", ("cogcoder/organization/authority.py",)),
    "organization.events": _native("nolane.organization.events", ("cogcoder/organization/events.py",)),
    "organization.tasks": _native("nolane.organization.tasks", ("cogcoder/organization/tasks.py",)),
    "organization.lifecycle": _native("nolane.organization.lifecycle", ("cogcoder/organization/scheduler.py",)),
    "organization.coordination.leases": _native("nolane.organization.coordination_leases", ("cogcoder/organization/coordination_leases.py",)),
    "organization.coordination.delivery": _native("nolane.organization.coordination_delivery", ("cogcoder/organization/coordination_delivery.py",)),
    "organization.coordination.conflicts": _native("nolane.organization.coordination_conflicts", ("cogcoder/organization/coordination_conflicts.py",)),
    "organization.coordination": _native("nolane.organization.coordination", ("cogcoder/organization/coordination.py",)),
    "organization.central": _native("nolane.organization.central", ("cogcoder/organization/central.py", "cogcoder/organization/central_access.py", "cogcoder/organization/central_conflicts.py", "cogcoder/organization/central_resources.py", "cogcoder/organization/central_state.py")),
    "organization.runtime": _native("nolane.runtime", ("cogcoder/organization/runtime.py", "cogcoder/organization/runtime_core.py")),
    "organization.temporary_work_units": _native("nolane.work_units", ("cogcoder/organization/foundry.py", "cogcoder/organization/foundry_profiles.py", "cogcoder/organization/foundry_resources.py")),
    "external.assurance": _native("nolane.external_core.assurance", ("cogcoder/organization/assurance.py", "cogcoder/organization/assurance_evidence.py", "cogcoder/organization/assurance_profiles.py")),
    "external.individual_evolution": _native("nolane.external_core.individual_evolution", ("cogcoder/organization/individual_evolution.py", "cogcoder/organization/evolution_profiles.py")),
    "external.research": _native("nolane.external_core.research", ("cogcoder/organization/research.py", "cogcoder/organization/research_profiles.py", "cogcoder/organization/research_provenance.py")),
    "external.operations": _native("nolane.external_core.operations", ("cogcoder/organization/operations.py", "cogcoder/organization/operations_profiles.py", "cogcoder/organization/data_operations.py", "cogcoder/organization/infrastructure_operations.py", "cogcoder/organization/reliability_operations.py")),
    "external.cognitive_library": _native(
        "nolane.external_core.cognitive_library",
        ("cogcoder/r253_operator_catalog.py", "cogcoder/r256_operator_dsl.py", "cogcoder/r257_vocabulary.py"),
        "Native typed operator catalog, bounded expression DSL, learned abstraction vocabulary and deterministic cognitive-library snapshot authority; R2.53/R2.56/R2.57 remain historical parity and provenance oracles.",
    ),
    "external.artifacts": _native("nolane.external_core.artifacts", ("cogcoder/organization/artifacts.py",)),
    "external.evidence": _native("nolane.external_core.evidence", ("cogcoder/organization/types.py",)),
    "external.experience": _native("nolane.memory.experience", ("cogcoder/organization/experience.py",)),
    "external.self_model": _native("nolane.external_core.self_model", ("cogcoder/organization/self_model.py",)),
    "external.skills": _native("nolane.memory.skills", ("cogcoder/organization/evolution.py", "cogcoder/organization/types.py")),
    "external.memory.fabric": _native("nolane.memory.fabric", ("cogcoder/organization/memory.py", "cogcoder/organization/types.py")),
    "external.memory.lifecycle": _native("nolane.memory.lifecycle", ("cogcoder/organization/memory_lifecycle.py",)),
    "external.memory.retrieval": _native("nolane.memory.retrieval", ("cogcoder/organization/memory_retrieval.py",)),
    "external.knowledge": _native("nolane.memory.knowledge", ("cogcoder/knowledge_types.py", "cogcoder/knowledge_store.py", "cogcoder/knowledge_ledger.py", "cogcoder/knowledge_adapters.py")),
    "external.epistemic": _native("nolane.external_core.epistemic", ("cogcoder/epistemic_workspace.py",)),
    "external.requirements": _native("nolane.external_core.requirements", ("cogcoder/organization/requirements.py",)),
    "external.planning": _native("nolane.external_core.planning", ("cogcoder/organization/planning.py",)),
    "external.architecture": _native("nolane.external_core.architecture", ("cogcoder/organization/architecture.py",)),
    "external.integration": _native("nolane.external_core.integration", ("cogcoder/organization/integration.py",)),
    "external.invokable_cores": _native("nolane.external_core.invokable", ("cogcoder/organization/external_core.py",)),
    "external.context": _native("nolane.memory.context", ("cogcoder/organization/context.py", "cogcoder/organization/context_intelligence.py", "cogcoder/organization/memory_profiles.py", "cogcoder/organization/memory_context.py", "cogcoder/organization/memory_context_adapter.py")),
    "external.execution.workspace": _native("nolane.external_core.execution_workspace", ("cogcoder/organization/execution_workspace.py",)),
    "external.execution.executor": _native("nolane.external_core.execution_executor", ("cogcoder/organization/execution_tools.py",)),
    "external.execution.control": _native("nolane.external_core.execution", ("cogcoder/organization/execution.py",)),
    "external.coding.claims": _native("nolane.external_core.coding_claims", ("cogcoder/organization/code_claims.py",)),
    "external.coding.patches": _native("nolane.external_core.coding_patches", ("cogcoder/organization/coding_patches.py",)),
    "external.coding.control": _native("nolane.external_core.coding", ("cogcoder/organization/coding.py",)),
    "external.debugging": _native("nolane.external_core.debugging", ("cogcoder/organization/debugging.py", "cogcoder/organization/debug_evidence.py", "cogcoder/organization/debug_hypotheses.py", "cogcoder/organization/debug_profiles.py")),
    "external.ui_ux": _native("nolane.external_core.ui_ux", ("cogcoder/organization/ui.py", "cogcoder/organization/ui_coding.py", "cogcoder/organization/ui_design.py", "cogcoder/organization/ui_observations.py", "cogcoder/organization/ui_profiles.py")),
    "external.verification": _native("nolane.external_core.verification", ("cogcoder/organization/verification.py",)),
    "evaluation.regimes": _native("nolane.evaluation.regimes", ("cogcoder/organization/evaluation_regimes.py",)),
    "evaluation.evidence": _native("nolane.evaluation.evidence", ("cogcoder/organization/evaluation_evidence.py",)),
    "evaluation.stress": _native("nolane.evaluation.stress", ("cogcoder/organization/evaluation_stress.py",)),
    "evaluation.claims": _native("nolane.evaluation.claims", ("cogcoder/organization/evaluation_claims.py",)),
    "evaluation.parameters": _native("nolane.evaluation.parameters", ("cogcoder/organization/evaluation_parameters.py",)),
    "evaluation.release": _native("nolane.evaluation.release", ("cogcoder/organization/evaluation_release.py",)),
    "evaluation.scaling": _native("nolane.evaluation.scaling", ("cogcoder/organization/evaluation.py",)),
    "evaluation.campaign": _native("nolane.evaluation.campaign", ("cogcoder/organization/campaign.py", "cogcoder/organization/campaign_repository.py", "cogcoder/organization/campaign_tasks.py", "cogcoder/organization/campaign_contamination.py", "cogcoder/organization/campaign_runner.py", "cogcoder/organization/campaign_reproduction.py", "cogcoder/organization/campaign_ingest.py")),
    "neural.inference_bridge": _native("nolane.neural.inference_bridge", ("cogcoder/organization/execution_inference.py",)),
}

_HISTORICAL_ONLY: dict[str, tuple[str, ...]] = {
    "external.capability_acquisition": ("historical capability-acquisition mechanisms; extraction not yet accepted",),
    "external.causal": ("historical bounded causal programs; not a current dedicated organization component",),
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
