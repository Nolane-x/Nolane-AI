from __future__ import annotations

from dataclasses import replace

import pytest

from nolane.external_core.audit import build_canonical_fabric_profile, build_canonical_registry
from nolane.external_core.integration_admission import (
    AdmissionDisposition,
    CanonicalAdmissionContext,
    admit_authority_graph_state,
    admit_manifest_state,
    canonical_frontier_digest,
)
from nolane.external_core.integration_admission_bundle import (
    CanonicalAdmissionBundle,
    build_canonical_admission_bundle,
    build_canonical_admission_context,
)


def _context(*, epoch: int = 7, registry_digest: str | None = None) -> CanonicalAdmissionContext:
    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    return CanonicalAdmissionContext.create(
        registry_digest=registry.registry_digest if registry_digest is None else registry_digest,
        authority_graph_digest=profile.authority_graph.digest,
        source_state_frontier_digest=canonical_frontier_digest("source-state", {}),
        evidence_frontier_digest=canonical_frontier_digest("evidence", {}),
        artifact_frontier_digest=canonical_frontier_digest("artifact", {}),
        freshness_fence_frontier_digest=canonical_frontier_digest("freshness", {}),
        handoff_frontier_digest=canonical_frontier_digest("handoff", {}),
        work_trace_frontier_digest=canonical_frontier_digest("work-trace", {}),
        observed_epoch=epoch,
    )


def _children(context: CanonicalAdmissionContext):
    registry = build_canonical_registry()
    profile = build_canonical_fabric_profile()
    manifests = tuple(admit_manifest_state(row.to_state(), context=context) for row in registry.manifests)
    graph = admit_authority_graph_state(profile.authority_graph.to_state(), context=context)
    return manifests, graph


def test_canonical_bundle_builder_emits_exact_admitted_snapshot() -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=7)
    assert bundle.context.observed_epoch == 7
    assert bundle.manifests
    assert all(row.receipt.disposition is AdmissionDisposition.ADMITTED for row in bundle.manifests)
    assert bundle.authority_graph.receipt.disposition is AdmissionDisposition.ADMITTED
    assert bundle.handoffs == ()
    assert bundle.work_traces == ()
    bundle.validate_integrity()
    assert CanonicalAdmissionBundle.from_state(bundle.to_state()) == bundle


def test_bundle_rejects_duplicate_subject_identity() -> None:
    context = _context()
    manifests, graph = _children(context)
    with pytest.raises(ValueError, match="duplicate.*manifest|duplicate.*subject"):
        CanonicalAdmissionBundle.create(
            context=context,
            manifests=manifests + (manifests[0],),
            authority_graph=graph,
        )


def test_bundle_rejects_child_receipt_from_another_context() -> None:
    context = _context(epoch=7)
    manifests, graph = _children(context)
    other = _context(epoch=8)
    with pytest.raises(ValueError, match="context"):
        CanonicalAdmissionBundle.create(
            context=other,
            manifests=manifests,
            authority_graph=graph,
        )


def test_bundle_rejects_blocked_child_even_when_wrapper_integrity_is_valid() -> None:
    blocked_context = _context(registry_digest="not-the-current-registry")
    manifests, graph = _children(blocked_context)
    assert manifests[0].receipt.disposition is AdmissionDisposition.BLOCKED
    with pytest.raises(ValueError, match="ADMITTED|admitted|blocked"):
        CanonicalAdmissionBundle.create(
            context=blocked_context,
            manifests=manifests,
            authority_graph=graph,
        )


def test_bundle_integrity_rejects_direct_constructor_digest_forgery() -> None:
    bundle = build_canonical_admission_bundle(observed_epoch=7)
    forged = replace(bundle, digest="forged-bundle-digest")
    with pytest.raises(ValueError, match="integrity|digest|canonical"):
        forged.validate_integrity()


def test_context_builder_does_not_coerce_falsey_wrong_type_frontier_to_empty_mapping() -> None:
    with pytest.raises(ValueError, match="frontier.*object|object"):
        build_canonical_admission_context(
            current_evidence_digests=[],  # type: ignore[arg-type]
        )
