from __future__ import annotations

from dataclasses import replace

import nolane.external_core.integration_admission_bundle as admission_bundle
from nolane.external_core.observation import (
    CanonicalObservationEnvelope,
    SurfaceObservationReceipt,
)


def _empty_frontiers() -> dict[str, dict[str, str]]:
    return {
        "current_source_state_digests": {},
        "current_evidence_digests": {},
        "current_artifact_digests": {},
        "current_freshness_fences": {},
        "known_handoff_digests": {},
        "current_work_trace_digests": {},
    }


def _replace_receipt_provider(
    envelope: CanonicalObservationEnvelope,
    *,
    surface_kind: str,
    provider_id: str,
) -> CanonicalObservationEnvelope:
    target = envelope.surface_receipt(surface_kind)
    replacement = SurfaceObservationReceipt.create(
        surface_kind=target.surface_kind,
        provider_id=provider_id,
        provider_version=target.provider_version,
        source_locator=target.source_locator,
        scope_digest=target.scope_digest,
        observed_state_digest=target.observed_state_digest,
        enumeration_complete=target.enumeration_complete,
        observed_epoch=target.observed_epoch,
    )
    receipts = tuple(
        replacement if row.surface_kind == surface_kind else row
        for row in envelope.surface_receipts
    )
    return CanonicalObservationEnvelope.create(
        surface_contract=envelope.surface_contract,
        observed_epoch=envelope.observed_epoch,
        registry_digest=envelope.registry_digest,
        authority_graph_digest=envelope.authority_graph_digest,
        source_state_frontier_digest=envelope.source_state_frontier_digest,
        evidence_frontier_digest=envelope.evidence_frontier_digest,
        artifact_frontier_digest=envelope.artifact_frontier_digest,
        freshness_fence_frontier_digest=envelope.freshness_fence_frontier_digest,
        handoff_frontier_digest=envelope.handoff_frontier_digest,
        work_trace_frontier_digest=envelope.work_trace_frontier_digest,
        surface_receipts=receipts,
        chain_id=envelope.chain_id,
        previous_observation_digest=envelope.previous_observation_digest,
    )


def test_legacy_a7_audit_lane_remains_clean_for_historical_call_shape() -> None:
    bundle = admission_bundle.build_canonical_admission_bundle(observed_epoch=7)
    report = admission_bundle.run_canonical_admission_audit(
        bundle=bundle,
        current_observed_epoch=7,
    )
    assert report.findings == ()
    assert report.protocol == "external-integration-admission-audit-v3"


def test_current_observation_audit_requires_explicit_witness() -> None:
    bundle = admission_bundle.build_canonical_admission_bundle(observed_epoch=7)
    report = admission_bundle.run_canonical_admission_audit(
        bundle=bundle,
        current_observed_epoch=7,
        observation_genesis=False,
        **_empty_frontiers(),
    )
    assert "CURRENT_OBSERVATION_WITNESS_UNAVAILABLE" in {
        row.code for row in report.findings
    }


def test_fresh_current_audit_binds_observation_and_reads_current_objects_once(
    monkeypatch,
) -> None:
    reads = {"count": 0}
    original = admission_bundle._strict_current_objects

    def counted():
        reads["count"] += 1
        return original()

    monkeypatch.setattr(admission_bundle, "_strict_current_objects", counted)
    report = admission_bundle.run_canonical_admission_audit(
        observed_epoch=7,
        observation_genesis=True,
        **_empty_frontiers(),
    )

    assert report.findings == ()
    assert report.observation_digest is not None
    assert report.protocol == "external-integration-admission-audit-v4"
    assert reads == {"count": 1}


def test_current_audit_rejects_provider_substitution() -> None:
    predecessor = admission_bundle.build_canonical_observation(
        observed_epoch=6,
        chain_id="external-core:test",
        previous_observation_digest=None,
        **_empty_frontiers(),
    )
    current = admission_bundle.build_canonical_observation(
        observed_epoch=7,
        chain_id="external-core:test",
        previous_observation_digest=predecessor.digest,
        **_empty_frontiers(),
    )
    forged = _replace_receipt_provider(
        current,
        surface_kind="registry",
        provider_id="external-core:substituted-registry",
    )
    bundle = admission_bundle.build_canonical_admission_bundle(
        observed_epoch=7,
        **_empty_frontiers(),
    )

    report = admission_bundle.run_canonical_admission_audit(
        bundle=bundle,
        current_observed_epoch=7,
        current_observation=forged,
        predecessor_observation=predecessor,
        observation_genesis=False,
        **_empty_frontiers(),
    )

    assert "OBSERVATION_PROVIDER_ID_MISMATCH" in {
        row.code for row in report.findings
    }


def test_current_audit_rejects_wrong_predecessor_commitment() -> None:
    predecessor = admission_bundle.build_canonical_observation(
        observed_epoch=6,
        chain_id="external-core:test",
        previous_observation_digest=None,
        **_empty_frontiers(),
    )
    current = admission_bundle.build_canonical_observation(
        observed_epoch=7,
        chain_id="external-core:test",
        previous_observation_digest="canonical-observation-v1-wrong",
        **_empty_frontiers(),
    )
    bundle = admission_bundle.build_canonical_admission_bundle(
        observed_epoch=7,
        **_empty_frontiers(),
    )

    report = admission_bundle.run_canonical_admission_audit(
        bundle=bundle,
        current_observed_epoch=7,
        current_observation=current,
        predecessor_observation=predecessor,
        observation_genesis=False,
        **_empty_frontiers(),
    )

    assert "OBSERVATION_PREDECESSOR_DIGEST_MISMATCH" in {
        row.code for row in report.findings
    }


def test_current_audit_reports_supplied_sibling_fork() -> None:
    predecessor = admission_bundle.build_canonical_observation(
        observed_epoch=6,
        chain_id="external-core:test",
        previous_observation_digest=None,
        **_empty_frontiers(),
    )
    left_frontiers = _empty_frontiers()
    left_frontiers["current_source_state_digests"] = {"external.alpha": "left"}
    right_frontiers = _empty_frontiers()
    right_frontiers["current_source_state_digests"] = {"external.alpha": "right"}
    left = admission_bundle.build_canonical_observation(
        observed_epoch=7,
        chain_id="external-core:test",
        previous_observation_digest=predecessor.digest,
        **left_frontiers,
    )
    right = admission_bundle.build_canonical_observation(
        observed_epoch=7,
        chain_id="external-core:test",
        previous_observation_digest=predecessor.digest,
        **right_frontiers,
    )
    bundle = admission_bundle.build_canonical_admission_bundle(
        observed_epoch=7,
        **left_frontiers,
    )

    report = admission_bundle.run_canonical_admission_audit(
        bundle=bundle,
        current_observed_epoch=7,
        current_observation=left,
        predecessor_observation=predecessor,
        competing_successors=(right,),
        observation_genesis=False,
        **left_frontiers,
    )

    assert "OBSERVATION_FORK_DETECTED" in {row.code for row in report.findings}

def test_current_lane_identity_is_closed_at_v4() -> None:
    assert admission_bundle.COMPONENT_VERSION == "0.0.8"
    assert admission_bundle.ADMISSION_AUDIT_PROTOCOL == "external-integration-admission-audit-v4"
    assert admission_bundle.CURRENT_ADMISSION_AUDIT_PROTOCOL == admission_bundle.ADMISSION_AUDIT_PROTOCOL
