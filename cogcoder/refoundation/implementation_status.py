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
        (
            "cogcoder/organization/registry.py",
            "cogcoder/organization/blueprint.py",
            "cogcoder/organization/types.py",
        ),
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
        "Native causal event ledger, subscriptions, delivery and state round-trip; historical module bridges to canonical class identity.",
    ),
    "organization.tasks": (
        "nolane.organization.tasks",
        ("cogcoder/organization/tasks.py",),
        "Native task DAG, task mutation and execution projection; historical tasks module is a compatibility bridge.",
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
        (
            "cogcoder/knowledge_types.py",
            "cogcoder/knowledge_store.py",
            "cogcoder/knowledge_ledger.py",
            "cogcoder/knowledge_adapters.py",
        ),
        "Native provenance-aware deterministic Knowledge fabric reconstructed from the dedicated R2 types/store/ledger/adapters lineage; historical modules bridge exact public identities while R2.54 Cognitive Retrieval remains outside this ownership boundary.",
    ),
    "external.epistemic": (
        "nolane.external_core.epistemic",
        ("cogcoder/epistemic_workspace.py",),
        "Native version-aware evidence workspace with fail-closed provenance, source/version supersession, corroboration, contested beliefs, conflicts and narrow missing-query generation; historical R2.2 module bridges exact public identities.",
    ),
    "external.verification": (
        "nolane.external_core.verification",
        ("cogcoder/organization/verification.py",),
        "Native bounded candidate evaluation, promotion and rollback authority over canonical identity/event primitives; historical verification module is a compatibility bridge.",
    ),
}

_HISTORICAL_ONLY: dict[str, tuple[str, ...]] = {
    "external.cognitive_library": ("historical reusable cognitive mechanisms; extraction not yet accepted",),
    "external.capability_acquisition": ("historical capability-acquisition mechanisms; extraction not yet accepted",),
    "external.causal": ("historical bounded causal programs; not a current dedicated organization component",),
    "external.experimentation": ("historical active experimentation mechanisms; extraction not yet accepted",),
    "external.transfer_meta": ("historical transfer/meta-learning mechanisms; extraction not yet accepted",),
}

_FROZEN_ASSET: dict[str, tuple[str, ...]] = {
    "neural.shared": ("model/neural-r2.3",),
}

_LEGACY_SOURCE_HINTS: dict[str, tuple[str, ...]] = {
    "external.coding.claims": ("cogcoder/organization/coding_claims.py",),
    "external.coding.patches": ("cogcoder/organization/coding.py",),
}


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
