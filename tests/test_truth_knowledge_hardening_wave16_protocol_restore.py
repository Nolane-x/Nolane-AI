from __future__ import annotations

import pytest

from nolane.external_core.assurance_observation_truth import ObservationTruthClosureCertificate
from nolane.external_core.epistemic_observation_truth import OBSERVATION_BINDING_MODE
from nolane.external_core.evidence_truth import EvidenceChannel
from nolane.external_core.knowledge_truth import KnowledgeRisk
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_observation_truth import (
    TRUTH_PROTOCOL as VERIFICATION_PROTOCOL,
    ObservationTruthVerificationLedger,
    ObservationTruthVerificationReceipt,
)


AS_OF = "2026-09-01T00:00:00Z"


def _receipt() -> ObservationTruthVerificationReceipt:
    temporal = TemporalContext.create(as_of=AS_OF)
    return ObservationTruthVerificationReceipt.create(
        receipt_id="receipt:restore-v10",
        claim_id="claim:restore-v10",
        verifier_id="verifier:restore-v10",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest="scope:v10",
        truth_context_digest="truth-context:v10",
        temporal_context_digest=temporal.digest,
        as_of=temporal.as_of,
        observation_requirement_digest="requirements:v10",
        observation_result_digest="results:v10",
        evidence_ids=("evidence:restore-v10",),
        source_provenance_digest="provenance:restore-v10",
        source_dependence_digest="dependence:restore-v10",
        evidence_context_digest="evidence-context:restore-v10",
    )


def _certificate() -> ObservationTruthClosureCertificate:
    temporal = TemporalContext.create(as_of=AS_OF)
    return ObservationTruthClosureCertificate.create(
        claim_id="claim:restore-v10",
        risk=KnowledgeRisk.STANDARD,
        scope_digest="scope:v10",
        verification_scope_digest="verification:v10",
        truth_context_digest="truth-context:v10",
        temporal_context_digest=temporal.digest,
        as_of=temporal.as_of,
        observation_requirement_digest="requirements:v10",
        observation_result_digest="results:v10",
        verification_receipt_ids=("receipt:restore-v10",),
        epistemic_debt_ids=(),
        closed=True,
        reasons=(),
    )


def test_a16_verification_restore_rejects_tampered_requirement_projection():
    state = _receipt().to_state()
    state["observation_requirement_digest"] = "requirements:tampered"
    with pytest.raises(ValueError, match="digest mismatch"):
        ObservationTruthVerificationReceipt.from_state(state)


def test_a16_verification_restore_rejects_tampered_result_projection():
    state = _receipt().to_state()
    state["observation_result_digest"] = "results:tampered"
    with pytest.raises(ValueError, match="digest mismatch"):
        ObservationTruthVerificationReceipt.from_state(state)


def test_a16_verification_restore_rejects_protocol_downgrade_and_unknown_field():
    state = _receipt().to_state()
    downgraded = dict(state)
    downgraded["protocol"] = "truth-verification-context-dependence-defeasible-justification-provenance-lineage-temporal-v9"
    with pytest.raises(ValueError, match="unsupported observation verification protocol"):
        ObservationTruthVerificationReceipt.from_state(downgraded)

    unexpected = dict(state)
    unexpected["legacy_observation_mode"] = True
    with pytest.raises(ValueError, match="unexpected observation verification receipt"):
        ObservationTruthVerificationReceipt.from_state(unexpected)


def test_a16_verification_ledger_restore_rejects_duplicate_receipt():
    state = _receipt().to_state()
    with pytest.raises(ValueError, match="duplicate serialized"):
        ObservationTruthVerificationLedger.from_state(
            {"protocol": VERIFICATION_PROTOCOL, "receipts": [state, state]}
        )


def test_a16_assurance_restore_rejects_tampered_observation_projection():
    state = _certificate().to_state()
    state["observation_result_digest"] = "results:tampered"
    with pytest.raises(ValueError, match="digest mismatch"):
        ObservationTruthClosureCertificate.from_state(state)


def test_a16_assurance_restore_rejects_binding_mode_downgrade():
    state = _certificate().to_state()
    state["binding_mode"] = "context-dependence-defeasible-justification-provenance-lineage-temporal-v9"
    with pytest.raises(ValueError, match="unsupported observation assurance binding mode"):
        ObservationTruthClosureCertificate.from_state(state)


def test_a16_assurance_restore_rejects_unknown_field():
    state = _certificate().to_state()
    state["legacy_mode"] = True
    with pytest.raises(ValueError, match="unexpected observation assurance certificate"):
        ObservationTruthClosureCertificate.from_state(state)


def test_a16_receipt_and_certificate_bind_exact_v10_mode():
    assert _receipt().binding_mode == OBSERVATION_BINDING_MODE
    assert _certificate().binding_mode == OBSERVATION_BINDING_MODE
