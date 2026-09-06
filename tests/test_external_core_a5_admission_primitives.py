from __future__ import annotations

import pytest

from nolane.external_core.integration_admission import (
    ADMISSION_PROTOCOL,
    AdmissionDisposition,
    AdmissionSubjectKind,
    CanonicalAdmissionContext,
    ProtocolAdmissionReceipt,
)


def _context() -> CanonicalAdmissionContext:
    return CanonicalAdmissionContext.create(
        registry_digest="registry-v1-test",
        authority_graph_digest="graph-v1-test",
        source_state_frontier_digest="source-frontier-test",
        evidence_frontier_digest="evidence-frontier-test",
        artifact_frontier_digest="artifact-frontier-test",
        freshness_fence_frontier_digest="freshness-frontier-test",
        handoff_frontier_digest="handoff-frontier-test",
        work_trace_frontier_digest="trace-frontier-test",
        observed_epoch=7,
    )


def test_admission_context_is_content_addressed_and_exact_restorable() -> None:
    context = _context()
    assert context.protocol == ADMISSION_PROTOCOL
    restored = CanonicalAdmissionContext.from_state(context.to_state())
    assert restored == context
    context.validate_integrity()


def test_admission_receipt_binds_exact_context_and_owner() -> None:
    context = _context()
    receipt = ProtocolAdmissionReceipt.create(
        subject_kind=AdmissionSubjectKind.COMPONENT_MANIFEST,
        subject_protocol="component-manifest-v1",
        subject_id="external.evidence",
        subject_state_digest="state-digest",
        semantic_digest="manifest-digest",
        context_digest=context.digest,
        disposition=AdmissionDisposition.ADMITTED,
        reason_codes=(),
        limitations=("structural-only",),
    )
    assert receipt.context_digest == context.digest
    assert receipt.owner_component_id == "external.integration"
    assert receipt.owner_component_version == "0.0.4"
    assert ProtocolAdmissionReceipt.from_state(receipt.to_state()) == receipt
    receipt.validate_integrity()


def test_admission_context_rejects_unknown_serialized_keys() -> None:
    state = _context().to_state()
    state["unexpected"] = "launder-me"
    with pytest.raises(ValueError, match="non-canonical|unknown"):
        CanonicalAdmissionContext.from_state(state)
