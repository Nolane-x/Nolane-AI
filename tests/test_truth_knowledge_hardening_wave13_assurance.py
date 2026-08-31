from __future__ import annotations

import pytest

from nolane.external_core.assurance_defeasible_truth import (
    DefeasibleTruthAssuranceGate,
    DefeasibleTruthClosureCertificate,
)
from nolane.external_core.assurance_justification_truth import JustificationTruthClosureCertificate
from nolane.external_core.epistemic_defeasible_truth import DefeasibleEpistemicJudge
from nolane.external_core.evidence_provenance_truth import (
    SourceProvenanceRegistry,
    SourceProvenanceRevision,
)
from nolane.external_core.evidence_temporal_truth import TemporalEvidenceView
from nolane.external_core.evidence_truth import (
    EvidenceChannel,
    EvidenceLedger,
    EvidencePolarity,
    TruthEvidence,
)
from nolane.external_core.knowledge_justification_truth import (
    KnowledgeJustificationRegistry,
    KnowledgeJustificationRevision,
)
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.knowledge_undercutter_truth import (
    JustificationUndercutterRegistry,
    JustificationUndercutterRevision,
)
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_defeasible_truth import (
    DefeasibleTruthVerificationLedger,
    DefeasibleTruthVerificationReceipt,
)
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


def _prov(source_id: str, controller_id: str) -> SourceProvenanceRevision:
    return SourceProvenanceRevision.create(
        source_id=source_id,
        revision=1,
        predecessor_digest="",
        controller_id=controller_id,
        parent_source_ids=(),
    )


def _record(
    evidence: EvidenceLedger,
    *,
    evidence_id: str,
    subject_id: str,
    source_id: str,
    channel: EvidenceChannel = EvidenceChannel.OBSERVATION,
    polarity: EvidencePolarity = EvidencePolarity.SUPPORT,
) -> None:
    evidence.record(
        TruthEvidence.create(
            evidence_id=evidence_id,
            subject_id=subject_id,
            source_id=source_id,
            source_family=f"family:{source_id}",
            channel=channel,
            polarity=polarity,
            payload_digest=f"payload:{evidence_id}",
        )
    )


def _state():
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    semantics = RelationSemanticsRegistry()
    knowledge_temporal = TemporalKnowledgeView()
    evidence_temporal = TemporalEvidenceView()
    provenance = SourceProvenanceRegistry()
    justifications = KnowledgeJustificationRegistry()
    undercutters = JustificationUndercutterRegistry()
    context = TemporalContext.create(as_of=AS_OF)

    _record(
        evidence,
        evidence_id="claim-support",
        subject_id="claim-critical-v7",
        source_id="claim-source",
    )
    provenance.register(_prov("claim-source", "claim-controller"))
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-critical-v7",
            subject="system",
            relation="is_safe",
            object="yes",
            risk=KnowledgeRisk.CRITICAL,
            evidence_ids=("claim-support",),
        )
    )

    for index, channel in enumerate(
        (EvidenceChannel.TEST, EvidenceChannel.REPRODUCTION, EvidenceChannel.ADVERSARIAL),
        start=1,
    ):
        verifier_id = f"verifier-{index}"
        provenance.register(_prov(verifier_id, f"verifier-controller-{index}"))
        _record(
            evidence,
            evidence_id=f"verification-{index}",
            subject_id=claim.claim_id,
            source_id=verifier_id,
            channel=channel,
        )

    return {
        "knowledge": knowledge,
        "evidence": evidence,
        "semantics": semantics,
        "knowledge_temporal": knowledge_temporal,
        "evidence_temporal": evidence_temporal,
        "provenance": provenance,
        "justifications": justifications,
        "undercutters": undercutters,
        "context": context,
        "claim": claim,
    }


def _scope(state):
    return DefeasibleEpistemicJudge().relation_aware_temporal_scope(
        state["claim"].claim_id,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
    )


def _verification(state, scope):
    ledger = DefeasibleTruthVerificationLedger()
    for index, channel in enumerate(
        (EvidenceChannel.TEST, EvidenceChannel.REPRODUCTION, EvidenceChannel.ADVERSARIAL),
        start=1,
    ):
        verifier_id = f"verifier-{index}"
        ledger.record(
            DefeasibleTruthVerificationReceipt.create(
                receipt_id=f"receipt-{index}",
                claim_id=state["claim"].claim_id,
                verifier_id=verifier_id,
                channel=channel,
                passed=True,
                scope_digest=scope.digest,
                temporal_context_digest=state["context"].digest,
                as_of=state["context"].as_of,
                evidence_ids=(f"verification-{index}",),
                source_provenance_digest=state["provenance"].projection_digest((verifier_id,)),
            )
        )
    return ledger


def _close(state):
    scope = _scope(state)
    verification = _verification(state, scope)
    certificate = DefeasibleTruthAssuranceGate().close(
        claim_id=state["claim"].claim_id,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
        verification=verification,
    )
    return scope, verification, certificate


def _supported_attack(state, *, undercutter_id="u-method-invalid"):
    _record(
        state["evidence"],
        evidence_id=f"evidence:{undercutter_id}",
        subject_id=undercutter_id,
        source_id=f"source:{undercutter_id}",
    )
    state["provenance"].register(_prov(f"source:{undercutter_id}", f"controller:{undercutter_id}"))
    basis = state["justifications"].legacy_basis(state["claim"])
    return state["undercutters"].register(
        JustificationUndercutterRevision.create(
            undercutter_id=undercutter_id,
            claim=state["claim"],
            target_basis=basis,
            evidence_ids=(f"evidence:{undercutter_id}",),
        ),
        knowledge=state["knowledge"],
        justifications=state["justifications"],
    )


def test_a13_clean_critical_claim_closes_with_three_independent_channels():
    state = _state()
    scope, _, certificate = _close(state)

    assert scope.assessment(state["claim"].claim_id).disposition.value == "supported"
    assert certificate.closed is True
    assert certificate.reasons == ()
    assert len(certificate.verification_receipt_ids) == 3


def test_a13_supported_undercutter_on_sole_basis_blocks_closure():
    state = _state()
    _supported_attack(state)

    scope, _, certificate = _close(state)

    assert scope.assessment(state["claim"].claim_id).disposition.value == "unknown"
    assert certificate.closed is False
    assert "epistemic_claim_not_supported" in certificate.reasons


def test_a13_clean_alternative_survives_defeated_branch_and_can_close():
    state = _state()
    _record(
        state["evidence"],
        evidence_id="alternate-support",
        subject_id=state["claim"].claim_id,
        source_id="alternate-source",
    )
    state["provenance"].register(_prov("alternate-source", "alternate-controller"))
    state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-alt",
            claim=state["claim"],
            evidence_ids=("alternate-support",),
        ),
        knowledge=state["knowledge"],
    )
    _supported_attack(state)

    scope, _, certificate = _close(state)

    assert scope.justification_status("j-alt").status == "supported"
    assert scope.assessment(state["claim"].claim_id).disposition.value == "supported"
    assert certificate.closed is True


def test_a13_critical_unknown_undercutter_debt_blocks_closure_without_defeating_support():
    state = _state()
    undercutter_id = "u-uncertain-method"
    _record(
        state["evidence"],
        evidence_id="uncertain-neutral",
        subject_id=undercutter_id,
        source_id="uncertain-source",
        polarity=EvidencePolarity.NEUTRAL,
    )
    state["provenance"].register(_prov("uncertain-source", "uncertain-controller"))
    basis = state["justifications"].legacy_basis(state["claim"])
    state["undercutters"].register(
        JustificationUndercutterRevision.create(
            undercutter_id=undercutter_id,
            claim=state["claim"],
            target_basis=basis,
            evidence_ids=("uncertain-neutral",),
        ),
        knowledge=state["knowledge"],
        justifications=state["justifications"],
    )

    scope, _, certificate = _close(state)

    assert scope.justification_status(basis.justification_id).status == "supported"
    assert scope.assessment(state["claim"].claim_id).disposition.value == "supported"
    assert any(row.reason == "undercutter_unknown" and row.critical for row in scope.debts)
    assert certificate.closed is False
    assert "critical_epistemic_debt" in certificate.reasons


def test_a13_certificate_stales_after_relevant_truth_change():
    state = _state()
    scope, verification, certificate = _close(state)
    gate = DefeasibleTruthAssuranceGate()
    assert gate.validate_certificate(
        certificate,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
        verification=verification,
    )

    state["evidence"].revoke("claim-support", reason="relevant truth changed")
    assert scope.digest != _scope(state).digest
    assert gate.validate_certificate(
        certificate,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
        verification=verification,
    ) is False


def test_a13_v6_certificate_cannot_masquerade_as_v7():
    state = _state()
    old = JustificationTruthClosureCertificate.create(
        claim_id=state["claim"].claim_id,
        risk=KnowledgeRisk.CRITICAL,
        scope_digest="old-v6-scope",
        verification_scope_digest="old-v6-verification",
        temporal_context_digest=state["context"].digest,
        as_of=state["context"].as_of,
        verification_receipt_ids=(),
        epistemic_debt_ids=(),
        closed=False,
        reasons=("old-protocol",),
    )

    with pytest.raises(ValueError, match="unsupported defeasible assurance protocol"):
        DefeasibleTruthClosureCertificate.from_state(old.to_state())
