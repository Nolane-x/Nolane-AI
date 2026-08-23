from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import canonical_digest

from .compatibility import BootstrapParityReport, build_bootstrap_parity_report
from .composition import CompositionLock, build_wave1_composition_lock
from .facades import FacadeParityReport, validate_active_facades
from .manifests import FIRST_GENERATION_SNAPSHOT, AgentManifest, build_bootstrap_agent_manifests
from .reconciliation import AuthorityReconciliationReport, RefoundationAuthorityAuditor
from .runtime_state_map import RuntimeStateEnvelope, RuntimeStateMapper


@dataclass(frozen=True, slots=True)
class CanonicalRuntimeAssembly:
    """Read-only Epoch-0 evidence composition over the accepted runtime.

    This class is deliberately not a replacement runtime yet.  It binds the
    old runtime instance to the canonical component graph, 67 manifest view,
    state ownership envelope, facade parity and dual-authority audit.  That
    makes later write cutovers observable and reversible instead of a big-bang
    rewrite.
    """

    legacy_runtime: OrganizationRuntime
    source_snapshot_sha: str
    agent_manifests: tuple[AgentManifest, ...]
    composition_lock: CompositionLock
    bootstrap_parity: BootstrapParityReport
    facade_parity: FacadeParityReport
    state_envelope: RuntimeStateEnvelope
    authority_reconciliation: AuthorityReconciliationReport
    destructive_cutover_allowed: bool
    digest: str

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "source_snapshot_sha": self.source_snapshot_sha,
            "agent_manifest_ids": [row.agent_id for row in self.agent_manifests],
            "composition_digest": self.composition_lock.digest,
            "bootstrap_parity_digest": self.bootstrap_parity.digest,
            "facade_parity_digest": self.facade_parity.digest,
            "legacy_state_digest": self.state_envelope.legacy_state_digest,
            "state_envelope_digest": self.state_envelope.digest,
            "authority_reconciliation_digest": self.authority_reconciliation.digest,
            "destructive_cutover_allowed": self.destructive_cutover_allowed,
        }

    def __post_init__(self) -> None:
        if self.destructive_cutover_allowed:
            raise ValueError("Epoch-0 bootstrap assembly cannot authorize destructive cutover")
        if self.source_snapshot_sha != FIRST_GENERATION_SNAPSHOT:
            raise ValueError("canonical assembly is bound to the pinned first-generation source snapshot")
        if len(self.agent_manifests) != 67:
            raise ValueError("canonical assembly requires exactly 67 permanent agent manifests")
        if not self.bootstrap_parity.clean or not self.facade_parity.clean or not self.state_envelope.lossless:
            raise ValueError("canonical assembly requires clean bootstrap/facade parity and lossless state mapping")
        if canonical_digest(self.evidence_payload()) != self.digest:
            raise ValueError("canonical runtime assembly digest mismatch")

    @classmethod
    def from_accepted_runtime(cls, runtime: OrganizationRuntime) -> "CanonicalRuntimeAssembly":
        agents = build_bootstrap_agent_manifests()
        lock = build_wave1_composition_lock()
        bootstrap = build_bootstrap_parity_report()
        facade = validate_active_facades()
        envelope = RuntimeStateMapper().map_state(runtime.to_state())
        authority = RefoundationAuthorityAuditor(
            tasks=runtime.tasks,
            planning=runtime.planning,
            leases=runtime.coordination.leases,
        ).audit()
        payload = {
            "source_snapshot_sha": FIRST_GENERATION_SNAPSHOT,
            "agent_manifest_ids": [row.agent_id for row in agents],
            "composition_digest": lock.digest,
            "bootstrap_parity_digest": bootstrap.digest,
            "facade_parity_digest": facade.digest,
            "legacy_state_digest": envelope.legacy_state_digest,
            "state_envelope_digest": envelope.digest,
            "authority_reconciliation_digest": authority.digest,
            "destructive_cutover_allowed": False,
        }
        return cls(
            legacy_runtime=runtime,
            source_snapshot_sha=FIRST_GENERATION_SNAPSHOT,
            agent_manifests=agents,
            composition_lock=lock,
            bootstrap_parity=bootstrap,
            facade_parity=facade,
            state_envelope=envelope,
            authority_reconciliation=authority,
            destructive_cutover_allowed=False,
            digest=canonical_digest(payload),
        )
