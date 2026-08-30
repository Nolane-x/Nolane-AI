from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.verification_truth import (
    RELATION_SCOPED_BINDING_MODE,
    SCOPED_BINDING_MODE,
    TruthVerificationLedger,
    TruthVerificationReceipt,
)


def evidence() -> EvidenceLedger:
    ledger = EvidenceLedger()
    ledger.record(TruthEvidence.create(
        evidence_id="e1",
        subject_id="claim.alpha",
        source_id="runner-a",
        source_family="family-a",
        channel=EvidenceChannel.TEST,
        polarity=EvidencePolarity.SUPPORT,
        payload_digest="payload:e1",
    ))
    return ledger


def test_a10_v3_receipt_roundtrip_uses_exact_relation_aware_binding_mode():
    row = TruthVerificationReceipt.create(
        receipt_id="v3",
        claim_id="claim.alpha",
        verifier_id="runner-a",
        source_family="family-a",
        channel=EvidenceChannel.TEST,
        passed=True,
        binding_mode=RELATION_SCOPED_BINDING_MODE,
        scope_digest="scope-v3",
        evidence_ids=("e1",),
    )
    state = row.to_state()
    assert row.binding_mode == RELATION_SCOPED_BINDING_MODE
    assert row.is_relation_scoped
    assert row.is_scoped
    assert state["binding_mode"] == RELATION_SCOPED_BINDING_MODE
    assert state["scope_digest"] == "scope-v3"
    assert "knowledge_digest" not in state
    assert "epistemic_digest" not in state
    assert TruthVerificationReceipt.from_state(deepcopy(state)) == row


def test_a10_v2_and_v3_receipt_selectors_are_mode_exact():
    ledger = TruthVerificationLedger()
    v2 = ledger.record(TruthVerificationReceipt.create(
        receipt_id="v2",
        claim_id="claim.alpha",
        verifier_id="runner-a",
        source_family="family-a",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest="same-scope-string",
        evidence_ids=("e1",),
    ))
    v3 = ledger.record(TruthVerificationReceipt.create(
        receipt_id="v3",
        claim_id="claim.alpha",
        verifier_id="runner-a",
        source_family="family-a",
        channel=EvidenceChannel.TEST,
        passed=True,
        binding_mode=RELATION_SCOPED_BINDING_MODE,
        scope_digest="same-scope-string",
        evidence_ids=("e1",),
    ))

    assert v2.binding_mode == SCOPED_BINDING_MODE
    assert ledger.scoped_receipts("claim.alpha", scope_digest="same-scope-string") == (v2,)
    assert ledger.relation_scoped_receipts("claim.alpha", scope_digest="same-scope-string") == (v3,)


def test_a10_v3_coverage_reuses_live_provenance_validation_without_counting_v2():
    ev = evidence()
    ledger = TruthVerificationLedger()
    ledger.record(TruthVerificationReceipt.create(
        receipt_id="v2",
        claim_id="claim.alpha",
        verifier_id="runner-a",
        source_family="family-a",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest="scope",
        evidence_ids=("e1",),
    ))
    ledger.record(TruthVerificationReceipt.create(
        receipt_id="v3",
        claim_id="claim.alpha",
        verifier_id="runner-a",
        source_family="family-a",
        channel=EvidenceChannel.TEST,
        passed=True,
        binding_mode=RELATION_SCOPED_BINDING_MODE,
        scope_digest="scope",
        evidence_ids=("e1",),
    ))

    coverage = ledger.coverage_relation_scoped(
        "claim.alpha", scope_digest="scope", evidence=ev,
    )
    assert coverage.valid_receipt_ids == ("v3",)
    assert coverage.independent_source_count == 1
    assert coverage.channel_count == 1


def test_a10_v3_projection_digest_ignores_v1_v2_and_other_claim_receipts():
    ledger = TruthVerificationLedger()
    v3 = ledger.record(TruthVerificationReceipt.create(
        receipt_id="v3",
        claim_id="claim.alpha",
        verifier_id="runner-a",
        source_family="family-a",
        channel=EvidenceChannel.TEST,
        passed=True,
        binding_mode=RELATION_SCOPED_BINDING_MODE,
        scope_digest="scope-v3",
        evidence_ids=("e1",),
    ))
    initial = ledger.relation_scoped_digest("claim.alpha", scope_digest="scope-v3")

    ledger.record(TruthVerificationReceipt.create(
        receipt_id="v2",
        claim_id="claim.alpha",
        verifier_id="runner-a",
        source_family="family-a",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest="scope-v3",
        evidence_ids=("e1",),
    ))
    ledger.record(TruthVerificationReceipt.create(
        receipt_id="other-v3",
        claim_id="claim.other",
        verifier_id="runner-b",
        source_family="family-b",
        channel=EvidenceChannel.AUDIT,
        passed=True,
        binding_mode=RELATION_SCOPED_BINDING_MODE,
        scope_digest="scope-v3",
        evidence_ids=("other-e",),
    ))
    assert ledger.relation_scoped_digest("claim.alpha", scope_digest="scope-v3") == initial
    assert ledger.relation_scoped_receipts("claim.alpha", scope_digest="scope-v3") == (v3,)


def test_a10_mixed_or_unknown_v3_serialized_binding_state_fails_closed():
    row = TruthVerificationReceipt.create(
        receipt_id="v3",
        claim_id="claim.alpha",
        verifier_id="runner-a",
        source_family="family-a",
        channel=EvidenceChannel.TEST,
        passed=True,
        binding_mode=RELATION_SCOPED_BINDING_MODE,
        scope_digest="scope-v3",
        evidence_ids=("e1",),
    )
    mixed = deepcopy(row.to_state())
    mixed["knowledge_digest"] = "forged-global"
    with pytest.raises(ValueError, match="global bindings"):
        TruthVerificationReceipt.from_state(mixed)

    unknown = deepcopy(row.to_state())
    unknown["binding_mode"] = "future-untrusted-mode"
    with pytest.raises(ValueError, match="unsupported verification binding mode"):
        TruthVerificationReceipt.from_state(unknown)


def test_a10_existing_v1_and_v2_payload_shapes_do_not_gain_v3_fields():
    v1 = TruthVerificationReceipt.create(
        receipt_id="v1", claim_id="claim.alpha", verifier_id="runner-a",
        source_family="family-a", channel=EvidenceChannel.TEST, passed=True,
        knowledge_digest="knowledge", epistemic_digest="epistemic", evidence_ids=("e1",),
    )
    v2 = TruthVerificationReceipt.create(
        receipt_id="v2", claim_id="claim.alpha", verifier_id="runner-a",
        source_family="family-a", channel=EvidenceChannel.TEST, passed=True,
        scope_digest="scope-v2", evidence_ids=("e1",),
    )
    assert "binding_mode" not in v1.to_state()
    assert v2.to_state()["binding_mode"] == SCOPED_BINDING_MODE
    assert v2.to_state()["scope_digest"] == "scope-v2"
    assert RELATION_SCOPED_BINDING_MODE not in repr(v2.to_state())
