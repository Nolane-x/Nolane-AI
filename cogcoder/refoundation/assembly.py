from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nolane.core.canonical_digest import canonical_digest

from .accepted_runtime import AcceptedOrganizationRuntime
from .compatibility import BootstrapParityReport, build_bootstrap_parity_report
from .composition import CompositionLock, build_wave1_composition_lock
from .facades import FacadeParityReport, validate_active_facades
from .manifests import FIRST_GENERATION_SNAPSHOT, AgentManifest, build_bootstrap_agent_manifests
from .reconciliation import AuthorityReconciliationReport, RefoundationAuthorityAuditor
from .regions import RegionManifest, build_region_manifests
from .runtime_state_map import CanonicalStateBundle, RuntimeStateEnvelope, RuntimeStateMapper


@dataclass(frozen=True, slots=True)
class CanonicalRuntimeAssembly:
    """Read-only, digest-bound evidence composition over the accepted runtime.

    It binds exact permanent identities, 15 regions, component composition,
    compatibility parity, reversible state ownership and plan/lease authority
    reconciliation before any destructive migration is allowed. Access to the
    accepted historical runtime crosses only the Refoundation compatibility
    membrane; this evidence view never becomes a second runtime authority.
    """

    legacy_runtime: AcceptedOrganizationRuntime
    source_snapshot_sha: str
    agent_manifests: tuple[AgentManifest, ...]
    region_manifests: tuple[RegionManifest, ...]
    composition_lock: CompositionLock
    bootstrap_parity: BootstrapParityReport
    facade_parity: FacadeParityReport
    state_envelope: RuntimeStateEnvelope
    state_bundle: CanonicalStateBundle
    authority_reconciliation: AuthorityReconciliationReport
    destructive_cutover_allowed: bool
    digest: str

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "source_snapshot_sha": self.source_snapshot_sha,
            "agent_manifest_ids": [row.agent_id for row in self.agent_manifests],
            "region_manifest_digests": [row.digest for row in self.region_manifests],
            "composition_digest": self.composition_lock.digest,
            "bootstrap_parity_digest": self.bootstrap_parity.digest,
            "facade_parity_digest": self.facade_parity.digest,
            "legacy_state_digest": self.state_envelope.legacy_state_digest,
            "state_envelope_digest": self.state_envelope.digest,
            "state_bundle_digest": self.state_bundle.digest,
            "authority_reconciliation_digest": self.authority_reconciliation.digest,
            "destructive_cutover_allowed": self.destructive_cutover_allowed,
        }

    def __post_init__(self) -> None:
        if self.destructive_cutover_allowed:
            raise ValueError("Epoch-0 bootstrap assembly cannot authorize destructive cutover")
        if self.source_snapshot_sha != FIRST_GENERATION_SNAPSHOT:
            raise ValueError("canonical assembly is bound to the pinned first-generation source snapshot")
        if len(self.agent_manifests) != 67 or len(self.region_manifests) != 15:
            raise ValueError("canonical assembly requires exactly 67 permanent agents and 15 regions")
        if not self.bootstrap_parity.clean or not self.facade_parity.clean:
            raise ValueError("canonical assembly requires clean bootstrap and facade parity")
        if not self.state_envelope.lossless or not self.state_bundle.lossless:
            raise ValueError("canonical assembly requires lossless and reversible state ownership")
        if self.state_envelope.legacy_state_digest != self.state_bundle.legacy_state_digest:
            raise ValueError("canonical state envelope and bundle disagree on legacy state identity")
        if canonical_digest(self.evidence_payload()) != self.digest:
            raise ValueError("canonical runtime assembly digest mismatch")

    @classmethod
    def from_accepted_runtime(cls, runtime: AcceptedOrganizationRuntime) -> "CanonicalRuntimeAssembly":
        agents = build_bootstrap_agent_manifests()
        regions = build_region_manifests()
        lock = build_wave1_composition_lock()
        bootstrap = build_bootstrap_parity_report()
        facade = validate_active_facades()
        mapper = RuntimeStateMapper()
        legacy_state = runtime.to_state()
        envelope = mapper.map_state(legacy_state)
        bundle = mapper.bundle_state(legacy_state)
        authority = RefoundationAuthorityAuditor(
            tasks=runtime.tasks,
            planning=runtime.planning,
            leases=runtime.coordination.leases,
        ).audit()
        payload = {
            "source_snapshot_sha": FIRST_GENERATION_SNAPSHOT,
            "agent_manifest_ids": [row.agent_id for row in agents],
            "region_manifest_digests": [row.digest for row in regions],
            "composition_digest": lock.digest,
            "bootstrap_parity_digest": bootstrap.digest,
            "facade_parity_digest": facade.digest,
            "legacy_state_digest": envelope.legacy_state_digest,
            "state_envelope_digest": envelope.digest,
            "state_bundle_digest": bundle.digest,
            "authority_reconciliation_digest": authority.digest,
            "destructive_cutover_allowed": False,
        }
        return cls(
            legacy_runtime=runtime,
            source_snapshot_sha=FIRST_GENERATION_SNAPSHOT,
            agent_manifests=agents,
            region_manifests=regions,
            composition_lock=lock,
            bootstrap_parity=bootstrap,
            facade_parity=facade,
            state_envelope=envelope,
            state_bundle=bundle,
            authority_reconciliation=authority,
            destructive_cutover_allowed=False,
            digest=canonical_digest(payload),
        )
