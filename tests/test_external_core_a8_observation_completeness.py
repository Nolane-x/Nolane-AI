from __future__ import annotations

import pytest

from nolane.external_core.audit import build_canonical_registry
from nolane.external_core.integration_admission import canonical_frontier_digest
from nolane.external_core.observation import (
    CanonicalObservationEnvelope,
    CanonicalObservationSurfaceContract,
    REQUIRED_SURFACE_KINDS,
    SurfaceObservationReceipt,
    validate_observation_completeness,
)


def _component_ids() -> tuple[str, ...]:
    registry = build_canonical_registry()
    return tuple(row.component_id for row in registry.manifests)


def _surface_digests() -> dict[str, str]:
    return {
        "registry": "registry-state-1",
        "authority-graph": "authority-state-1",
        "source-state": canonical_frontier_digest("source-state", {}),
        "evidence": canonical_frontier_digest("evidence", {}),
        "artifact": canonical_frontier_digest("artifact", {}),
        "freshness": canonical_frontier_digest("freshness", {}),
        "handoff": canonical_frontier_digest("handoff", {}),
        "work-trace": canonical_frontier_digest("work-trace", {}),
    }


def _receipt(
    kind: str,
    state_digest: str,
    *,
    complete: bool = True,
    epoch: int = 7,
) -> SurfaceObservationReceipt:
    return SurfaceObservationReceipt.create(
        surface_kind=kind,
        provider_id=f"provider:{kind}",
        provider_version="1",
        source_locator=f"tests:{kind}",
        scope_digest=f"scope:{kind}:complete",
        observed_state_digest=state_digest,
        enumeration_complete=complete,
        observed_epoch=epoch,
    )


def _envelope(
    receipts: tuple[SurfaceObservationReceipt, ...],
    *,
    epoch: int = 7,
) -> CanonicalObservationEnvelope:
    digests = _surface_digests()
    return CanonicalObservationEnvelope.create(
        surface_contract=CanonicalObservationSurfaceContract.create(
            required_component_ids=_component_ids(),
        ),
        observed_epoch=epoch,
        registry_digest=digests["registry"],
        authority_graph_digest=digests["authority-graph"],
        source_state_frontier_digest=digests["source-state"],
        evidence_frontier_digest=digests["evidence"],
        artifact_frontier_digest=digests["artifact"],
        freshness_fence_frontier_digest=digests["freshness"],
        handoff_frontier_digest=digests["handoff"],
        work_trace_frontier_digest=digests["work-trace"],
        surface_receipts=receipts,
        chain_id="external-core:default",
        previous_observation_digest=None,
    )


def test_required_surface_kinds_are_exact_and_closed() -> None:
    assert REQUIRED_SURFACE_KINDS == (
        "artifact",
        "authority-graph",
        "evidence",
        "freshness",
        "handoff",
        "registry",
        "source-state",
        "work-trace",
    )


def test_contract_rejects_duplicate_component_identity() -> None:
    with pytest.raises(ValueError, match="duplicate required component identity"):
        CanonicalObservationSurfaceContract.create(
            required_component_ids=("external.a", "external.a"),
        )


def test_receipt_rejects_bool_epoch() -> None:
    with pytest.raises(ValueError, match="exact non-negative integer"):
        SurfaceObservationReceipt.create(
            surface_kind="source-state",
            provider_id="provider:source",
            provider_version="1",
            source_locator="tests:source",
            scope_digest="scope-1",
            observed_state_digest="state-1",
            enumeration_complete=True,
            observed_epoch=True,
        )


def test_missing_required_surface_is_reported() -> None:
    digests = _surface_digests()
    receipts = tuple(
        _receipt(kind, digest)
        for kind, digest in digests.items()
        if kind != "artifact"
    )
    findings = validate_observation_completeness(
        _envelope(receipts),
        expected_component_ids=_component_ids(),
        observed_surface_digests=digests,
    )
    assert "OBSERVATION_REQUIRED_SURFACE_MISSING" in {
        row.code for row in findings
    }


def test_incomplete_enumeration_is_reported() -> None:
    digests = _surface_digests()
    receipts = tuple(
        _receipt(kind, digest, complete=(kind != "source-state"))
        for kind, digest in digests.items()
    )
    findings = validate_observation_completeness(
        _envelope(receipts),
        expected_component_ids=_component_ids(),
        observed_surface_digests=digests,
    )
    assert "OBSERVATION_ENUMERATION_INCOMPLETE" in {
        row.code for row in findings
    }


def test_surface_epoch_mismatch_is_reported() -> None:
    digests = _surface_digests()
    receipts = tuple(
        _receipt(kind, digest, epoch=(6 if kind == "evidence" else 7))
        for kind, digest in digests.items()
    )
    findings = validate_observation_completeness(
        _envelope(receipts),
        expected_component_ids=_component_ids(),
        observed_surface_digests=digests,
    )
    assert "OBSERVATION_SURFACE_EPOCH_MISMATCH" in {
        row.code for row in findings
    }


def test_surface_state_digest_mismatch_is_reported() -> None:
    digests = _surface_digests()
    receipts = tuple(
        _receipt(kind, "wrong-state" if kind == "handoff" else digest)
        for kind, digest in digests.items()
    )
    findings = validate_observation_completeness(
        _envelope(receipts),
        expected_component_ids=_component_ids(),
        observed_surface_digests=digests,
    )
    assert "OBSERVATION_SURFACE_STATE_DIGEST_MISMATCH" in {
        row.code for row in findings
    }
