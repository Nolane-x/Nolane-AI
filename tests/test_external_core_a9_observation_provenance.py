from __future__ import annotations

from dataclasses import replace

from nolane.external_core.observation import (
    CanonicalObservationEnvelope,
    CanonicalObservationSurfaceContract,
    CanonicalSurfaceProviderExpectation,
    REQUIRED_SURFACE_KINDS,
    SurfaceObservationReceipt,
    validate_observation_provenance,
)


def _surface_digests() -> dict[str, str]:
    return {kind: f"state:{kind}:7" for kind in REQUIRED_SURFACE_KINDS}


def _receipt(kind: str, *, epoch: int = 7) -> SurfaceObservationReceipt:
    return SurfaceObservationReceipt.create(
        surface_kind=kind,
        provider_id=f"provider:{kind}",
        provider_version="1",
        source_locator=f"source:{kind}",
        scope_digest=f"scope:{kind}:complete",
        observed_state_digest=_surface_digests()[kind],
        enumeration_complete=True,
        observed_epoch=epoch,
    )


def _clean_envelope() -> CanonicalObservationEnvelope:
    digests = _surface_digests()
    return CanonicalObservationEnvelope.create(
        surface_contract=CanonicalObservationSurfaceContract.create(
            required_component_ids=("external.alpha", "external.beta"),
        ),
        observed_epoch=7,
        registry_digest=digests["registry"],
        authority_graph_digest=digests["authority-graph"],
        source_state_frontier_digest=digests["source-state"],
        evidence_frontier_digest=digests["evidence"],
        artifact_frontier_digest=digests["artifact"],
        freshness_fence_frontier_digest=digests["freshness"],
        handoff_frontier_digest=digests["handoff"],
        work_trace_frontier_digest=digests["work-trace"],
        surface_receipts=tuple(_receipt(kind) for kind in REQUIRED_SURFACE_KINDS),
        chain_id="external-core:default",
        previous_observation_digest=None,
    )


def _expectations() -> dict[str, CanonicalSurfaceProviderExpectation]:
    return {
        kind: CanonicalSurfaceProviderExpectation(
            surface_kind=kind,
            provider_id=f"provider:{kind}",
            provider_version="1",
            source_locator=f"source:{kind}",
        )
        for kind in REQUIRED_SURFACE_KINDS
    }


def _replace_receipt(
    envelope: CanonicalObservationEnvelope,
    replacement: SurfaceObservationReceipt,
) -> CanonicalObservationEnvelope:
    receipts = tuple(
        replacement if row.surface_kind == replacement.surface_kind else row
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


def _receipt_with(
    receipt: SurfaceObservationReceipt,
    **changes: object,
) -> SurfaceObservationReceipt:
    values = {
        "surface_kind": receipt.surface_kind,
        "provider_id": receipt.provider_id,
        "provider_version": receipt.provider_version,
        "source_locator": receipt.source_locator,
        "scope_digest": receipt.scope_digest,
        "observed_state_digest": receipt.observed_state_digest,
        "enumeration_complete": receipt.enumeration_complete,
        "observed_epoch": receipt.observed_epoch,
    }
    values.update(changes)
    return SurfaceObservationReceipt.create(**values)


def test_clean_observation_has_no_provenance_findings() -> None:
    assert not validate_observation_provenance(
        _clean_envelope(),
        provider_expectations=_expectations(),
    )


def test_provider_identity_substitution_is_rejected() -> None:
    envelope = _clean_envelope()
    receipt = envelope.surface_receipt("registry")
    candidate = _replace_receipt(
        envelope,
        _receipt_with(receipt, provider_id="provider:substitute"),
    )
    findings = validate_observation_provenance(
        candidate,
        provider_expectations=_expectations(),
    )
    assert "OBSERVATION_PROVIDER_ID_MISMATCH" in {row.code for row in findings}


def test_provider_version_substitution_is_rejected() -> None:
    envelope = _clean_envelope()
    receipt = envelope.surface_receipt("authority-graph")
    candidate = _replace_receipt(
        envelope,
        _receipt_with(receipt, provider_version="999"),
    )
    findings = validate_observation_provenance(
        candidate,
        provider_expectations=_expectations(),
    )
    assert "OBSERVATION_PROVIDER_VERSION_MISMATCH" in {
        row.code for row in findings
    }


def test_source_locator_substitution_is_rejected() -> None:
    envelope = _clean_envelope()
    receipt = envelope.surface_receipt("registry")
    candidate = _replace_receipt(
        envelope,
        _receipt_with(receipt, source_locator="source:wrong"),
    )
    findings = validate_observation_provenance(
        candidate,
        provider_expectations=_expectations(),
    )
    assert "OBSERVATION_SOURCE_LOCATOR_MISMATCH" in {
        row.code for row in findings
    }


def test_cross_epoch_receipt_reuse_is_rejected() -> None:
    envelope = _clean_envelope()
    receipt = envelope.surface_receipt("evidence")
    candidate = _replace_receipt(
        envelope,
        _receipt_with(receipt, observed_epoch=6),
    )
    findings = validate_observation_provenance(
        candidate,
        provider_expectations=_expectations(),
    )
    assert "OBSERVATION_PROVENANCE_EPOCH_MISMATCH" in {
        row.code for row in findings
    }


def test_content_substitution_is_rejected() -> None:
    envelope = _clean_envelope()
    receipt = envelope.surface_receipt("source-state")
    candidate = _replace_receipt(
        envelope,
        _receipt_with(receipt, observed_state_digest="state:source-state:forged"),
    )
    findings = validate_observation_provenance(
        candidate,
        provider_expectations=_expectations(),
    )
    assert "OBSERVATION_PROVENANCE_CONTENT_MISMATCH" in {
        row.code for row in findings
    }
