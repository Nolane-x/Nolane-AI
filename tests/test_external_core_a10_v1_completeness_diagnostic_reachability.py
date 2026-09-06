from __future__ import annotations

from dataclasses import replace

import pytest

import nolane.external_core.integration_admission_bundle as admission_bundle
from nolane.external_core.observation import (
    SURFACE_RECEIPT_PROTOCOL,
    SurfaceObservationReceipt,
    validate_observation_completeness,
)


def _frontiers() -> dict[str, dict[str, str]]:
    return {
        "current_source_state_digests": {},
        "current_evidence_digests": {},
        "current_artifact_digests": {},
        "current_freshness_fences": {},
        "known_handoff_digests": {},
        "current_work_trace_digests": {},
    }


def _envelope():
    return admission_bundle.build_canonical_observation(
        observed_epoch=7,
        chain_id="external-core:test",
        previous_observation_digest=None,
        **_frontiers(),
    )


def _surface_digests(envelope) -> dict[str, str]:
    return {
        "registry": envelope.registry_digest,
        "authority-graph": envelope.authority_graph_digest,
        "source-state": envelope.source_state_frontier_digest,
        "evidence": envelope.evidence_frontier_digest,
        "artifact": envelope.artifact_frontier_digest,
        "freshness": envelope.freshness_fence_frontier_digest,
        "handoff": envelope.handoff_frontier_digest,
        "work-trace": envelope.work_trace_frontier_digest,
    }


def test_duplicate_surface_receipt_reaches_categorical_a8_finding() -> None:
    envelope = _envelope()
    duplicate = envelope.surface_receipt("registry")
    malformed = replace(
        envelope,
        surface_receipts=(*envelope.surface_receipts, duplicate),
    )

    findings = validate_observation_completeness(
        malformed,
        expected_component_ids=envelope.surface_contract.required_component_ids,
        observed_surface_digests=_surface_digests(envelope),
    )

    assert any(
        row.code == "OBSERVATION_SURFACE_DUPLICATE" and row.subject_id == "registry"
        for row in findings
    )


def test_unexpected_surface_receipt_reaches_categorical_a8_finding() -> None:
    envelope = _envelope()
    unexpected = SurfaceObservationReceipt(
        protocol=SURFACE_RECEIPT_PROTOCOL,
        surface_kind="unexpected-surface",
        provider_id="external-core:test-provider",
        provider_version="1",
        source_locator="tests:unexpected-surface",
        scope_digest="scope:unexpected",
        observed_state_digest="state:unexpected",
        enumeration_complete=True,
        observed_epoch=7,
        digest="surface-observation-receipt-v1-malformed",
    )
    malformed = replace(
        envelope,
        surface_receipts=(*envelope.surface_receipts, unexpected),
    )

    findings = validate_observation_completeness(
        malformed,
        expected_component_ids=envelope.surface_contract.required_component_ids,
        observed_surface_digests=_surface_digests(envelope),
    )

    assert any(
        row.code == "OBSERVATION_SURFACE_UNEXPECTED"
        and row.subject_id == "unexpected-surface"
        for row in findings
    )


def test_duplicate_surface_does_not_mask_unrelated_envelope_corruption() -> None:
    envelope = _envelope()
    duplicate = envelope.surface_receipt("registry")
    mixed_corruption = replace(
        envelope,
        registry_digest="registry-digest-unrelated-corruption",
        surface_receipts=(*envelope.surface_receipts, duplicate),
    )

    with pytest.raises(ValueError, match="integrity validation failed"):
        validate_observation_completeness(
            mixed_corruption,
            expected_component_ids=envelope.surface_contract.required_component_ids,
            observed_surface_digests=_surface_digests(envelope),
        )


def test_unexpected_surface_does_not_mask_unrelated_envelope_corruption() -> None:
    envelope = _envelope()
    unexpected = SurfaceObservationReceipt(
        protocol=SURFACE_RECEIPT_PROTOCOL,
        surface_kind="unexpected-surface",
        provider_id="external-core:test-provider",
        provider_version="1",
        source_locator="tests:unexpected-surface",
        scope_digest="scope:unexpected",
        observed_state_digest="state:unexpected",
        enumeration_complete=True,
        observed_epoch=7,
        digest="surface-observation-receipt-v1-malformed",
    )
    mixed_corruption = replace(
        envelope,
        registry_digest="registry-digest-unrelated-corruption",
        surface_receipts=(*envelope.surface_receipts, unexpected),
    )

    with pytest.raises(ValueError, match="integrity validation failed"):
        validate_observation_completeness(
            mixed_corruption,
            expected_component_ids=envelope.surface_contract.required_component_ids,
            observed_surface_digests=_surface_digests(envelope),
        )
