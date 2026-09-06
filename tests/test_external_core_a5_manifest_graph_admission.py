from __future__ import annotations

import pytest

from nolane.external_core.audit import build_canonical_fabric_profile, build_canonical_registry
from nolane.external_core.authority_graph import ExternalAuthorityGraph
from nolane.external_core.integration_admission import (
    AdmissionDisposition,
    CanonicalAdmissionContext,
    admit_authority_graph_state,
    admit_manifest_state,
)


class _StringLaunderer:
    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value


def _context() -> CanonicalAdmissionContext:
    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    return CanonicalAdmissionContext.create(
        registry_digest=registry.registry_digest,
        authority_graph_digest=profile.authority_graph.digest,
        source_state_frontier_digest="source-frontier",
        evidence_frontier_digest="evidence-frontier",
        artifact_frontier_digest="artifact-frontier",
        freshness_fence_frontier_digest="freshness-frontier",
        handoff_frontier_digest="handoff-frontier",
        work_trace_frontier_digest="trace-frontier",
        observed_epoch=1,
    )


def test_canonical_manifest_state_is_admitted_against_exact_current_registry() -> None:
    registry = build_canonical_registry()
    manifest = registry.manifest_for("external.evidence")
    admitted = admit_manifest_state(manifest.to_state(), context=_context())
    assert admitted.receipt.disposition is AdmissionDisposition.ADMITTED
    admitted.validate_integrity()


def test_manifest_raw_type_laundering_is_rejected_before_legacy_restore() -> None:
    registry = build_canonical_registry()
    state = registry.manifest_for("external.evidence").to_state()
    state["component_id"] = _StringLaunderer("external.evidence")
    with pytest.raises(ValueError, match="component_id|explicit string"):
        admit_manifest_state(state, context=_context())


def test_self_consistent_noncanonical_authority_graph_is_blocked() -> None:
    profile = build_canonical_fabric_profile()
    alternate = ExternalAuthorityGraph(profile.manifests, ())
    alternate.validate()
    result = admit_authority_graph_state(alternate.to_state(), context=_context())
    assert result.receipt.disposition is AdmissionDisposition.BLOCKED
    assert "CANONICAL_AUTHORITY_GRAPH_MISMATCH" in result.receipt.reason_codes


def test_canonical_authority_graph_is_admitted_and_exact_restorable() -> None:
    profile = build_canonical_fabric_profile()
    admitted = admit_authority_graph_state(profile.authority_graph.to_state(), context=_context())
    assert admitted.receipt.disposition is AdmissionDisposition.ADMITTED
    admitted.validate_integrity()
