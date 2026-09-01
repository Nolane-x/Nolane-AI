from __future__ import annotations

import pytest

from nolane.external_core.assurance_context_truth import ContextTruthClosureCertificate
from nolane.external_core.knowledge_truth import KnowledgeRisk
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_context_truth import (
    TRUTH_PROTOCOL as VERIFICATION_PROTOCOL,
    ContextTruthVerificationLedger,
    ContextTruthVerificationReceipt,
)
from nolane.external_core.evidence_truth import EvidenceChannel


AS_OF = "2026-08-31T00:00:00Z"


def _receipt() -> ContextTruthVerificationReceipt:
    temporal = TemporalContext.create(as_of=AS_OF)
    return ContextTruthVerificationReceipt.create(
        receipt_id="receipt:restore",
        claim_id="claim:restore",
        verifier_id="verifier:restore",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest="scope:v9",
        truth_context_digest="truth-context:v9",
        temporal_context_digest=temporal.digest,
        as_of=temporal.as_of,
        evidence_ids=("evidence:restore",),
        source_provenance_digest="provenance:restore",
        source_dependence_digest="dependence:restore",
        evidence_context_digest="evidence-context:restore",
    )


def test_a15_verification_restore_rejects_tampered_context_projection():
    state = _receipt().to_state()
    state["evidence_context_digest"] = "evidence-context:tampered"
    with pytest.raises(ValueError, match="digest mismatch"):
        ContextTruthVerificationReceipt.from_state(state)


def test_a15_verification_ledger_restore_rejects_duplicate_receipt():
    state = _receipt().to_state()
    with pytest.raises(ValueError, match="duplicate serialized"):
        ContextTruthVerificationLedger.from_state(
            {"protocol": VERIFICATION_PROTOCOL, "receipts": [state, state]}
        )


def test_a15_verification_restore_rejects_unknown_field():
    state = _receipt().to_state()
    state["legacy_context"] = "bypass"
    with pytest.raises(ValueError, match="unexpected context verification receipt"):
        ContextTruthVerificationReceipt.from_state(state)


def test_a15_assurance_restore_rejects_tampered_truth_context():
    temporal = TemporalContext.create(as_of=AS_OF)
    certificate = ContextTruthClosureCertificate.create(
        claim_id="claim:restore",
        risk=KnowledgeRisk.STANDARD,
        scope_digest="scope:v9",
        verification_scope_digest="verification:v9",
        truth_context_digest="truth-context:v9",
        temporal_context_digest=temporal.digest,
        as_of=temporal.as_of,
        verification_receipt_ids=("receipt:restore",),
        epistemic_debt_ids=(),
        closed=True,
        reasons=(),
    )
    state = certificate.to_state()
    state["truth_context_digest"] = "truth-context:tampered"
    with pytest.raises(ValueError, match="digest mismatch"):
        ContextTruthClosureCertificate.from_state(state)


def test_a15_assurance_restore_rejects_unknown_field():
    temporal = TemporalContext.create(as_of=AS_OF)
    certificate = ContextTruthClosureCertificate.create(
        claim_id="claim:restore",
        risk=KnowledgeRisk.STANDARD,
        scope_digest="scope:v9",
        verification_scope_digest="verification:v9",
        truth_context_digest="truth-context:v9",
        temporal_context_digest=temporal.digest,
        as_of=temporal.as_of,
        verification_receipt_ids=(),
        epistemic_debt_ids=("debt:restore",),
        closed=False,
        reasons=("blocked",),
    )
    state = certificate.to_state()
    state["legacy_mode"] = True
    with pytest.raises(ValueError, match="unexpected context assurance certificate"):
        ContextTruthClosureCertificate.from_state(state)
