from __future__ import annotations

import pytest

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
from nolane.external_core.knowledge_justification_truth import KnowledgeJustificationRegistry
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger
from nolane.external_core.knowledge_undercutter_truth import JustificationUndercutterRegistry
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_defeasible_truth import (
    DefeasibleTruthVerificationLedger,
    DefeasibleTruthVerificationReceipt,
)
from nolane.external_core.verification_justification_truth import (
    JustificationTruthVerificationReceipt,
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
    channel: EvidenceChannel,
) -> None:
    evidence.record(
        TruthEvidence.create(
            evidence_id=evidence_id,
            subject_id=subject_id,
            source_id=source_id,
            source_family=f"family:{source_id}",
            channel=channel,
            polarity=EvidencePolarity.SUPPORT,
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
        subject_id="claim-v7",
        source_id="claim-source",
        channel=EvidenceChannel.OBSERVATION,
    )
    provenance.register(_prov("claim-source", "origin-controller"))
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-v7",
            subject="system",
            relation="works",
            object="yes",
            evidence_ids=("claim-support",),
        )
    )

    for verifier_id, controller_id, channel in (
        ("verifier-same", "origin-controller", EvidenceChannel.TEST),
        ("verifier-independent", "independent-controller", EvidenceChannel.REPRODUCTION),
    ):
        provenance.register(_prov(verifier_id, controller_id))
        _record(
            evidence,
            evidence_id=f"evidence:{verifier_id}",
            subject_id=claim.claim_id,
            source_id=verifier_id,
            channel=channel,
        )

    scope = DefeasibleEpistemicJudge().relation_aware_temporal_scope(
        claim.claim_id,
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        source_provenance=provenance,
        justifications=justifications,
        undercutters=undercutters,
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
        "scope": scope,
    }


def _receipt(state, *, receipt_id: str, verifier_id: str, channel: EvidenceChannel, passed: bool = True):
    return DefeasibleTruthVerificationReceipt.create(
        receipt_id=receipt_id,
        claim_id=state["claim"].claim_id,
        verifier_id=verifier_id,
        channel=channel,
        passed=passed,
        scope_digest=state["scope"].digest,
        temporal_context_digest=state["context"].digest,
        as_of=state["context"].as_of,
        evidence_ids=(f"evidence:{verifier_id}",),
        source_provenance_digest=state["provenance"].projection_digest((verifier_id,)),
    )


def test_a13_decision_origin_controller_cannot_self_verify_as_independent():
    state = _state()
    ledger = DefeasibleTruthVerificationLedger()
    ledger.record(
        _receipt(
            state,
            receipt_id="r-same",
            verifier_id="verifier-same",
            channel=EvidenceChannel.TEST,
        )
    )
    ledger.record(
        _receipt(
            state,
            receipt_id="r-independent",
            verifier_id="verifier-independent",
            channel=EvidenceChannel.REPRODUCTION,
        )
    )

    coverage = ledger.coverage(
        state["claim"].claim_id,
        scope=state["scope"],
        temporal_context=state["context"],
        evidence=state["evidence"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
    )

    assert "claim-source" in state["scope"].decision_source_ids
    assert coverage.independent_source_count == 1
    assert coverage.passing_independence_keys == ("independent-controller",)
    assert "r-same" in coverage.non_independent_receipt_ids


def test_a13_negative_verification_is_retained_not_laundered_away():
    state = _state()
    ledger = DefeasibleTruthVerificationLedger()
    ledger.record(
        _receipt(
            state,
            receipt_id="r-negative",
            verifier_id="verifier-independent",
            channel=EvidenceChannel.REPRODUCTION,
            passed=False,
        )
    )

    coverage = ledger.coverage(
        state["claim"].claim_id,
        scope=state["scope"],
        temporal_context=state["context"],
        evidence=state["evidence"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
    )

    assert coverage.negative_receipt_ids == ("r-negative",)
    assert coverage.independent_source_count == 0


def test_a13_v6_receipt_cannot_masquerade_as_v7():
    state = _state()
    old = JustificationTruthVerificationReceipt.create(
        receipt_id="r-v6",
        claim_id=state["claim"].claim_id,
        verifier_id="verifier-independent",
        channel=EvidenceChannel.REPRODUCTION,
        passed=True,
        scope_digest="v6-scope-digest",
        temporal_context_digest=state["context"].digest,
        as_of=state["context"].as_of,
        evidence_ids=("evidence:verifier-independent",),
        source_provenance_digest=state["provenance"].projection_digest(("verifier-independent",)),
    )

    with pytest.raises(TypeError, match="v7 receipts only"):
        DefeasibleTruthVerificationLedger().record(old)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported defeasible verification protocol"):
        DefeasibleTruthVerificationReceipt.from_state(old.to_state())


def test_a13_receipt_is_exact_scope_bound_and_stales_after_relevant_change():
    state = _state()
    receipt = _receipt(
        state,
        receipt_id="r-current",
        verifier_id="verifier-independent",
        channel=EvidenceChannel.REPRODUCTION,
    )
    ledger = DefeasibleTruthVerificationLedger()
    ledger.record(receipt)
    assert ledger.current_receipts(
        state["claim"].claim_id,
        scope=state["scope"],
        temporal_context=state["context"],
    ) == (receipt,)

    state["evidence"].revoke("claim-support", reason="truth state changed")
    changed_scope = DefeasibleEpistemicJudge().relation_aware_temporal_scope(
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

    assert changed_scope.digest != state["scope"].digest
    assert ledger.current_receipts(
        state["claim"].claim_id,
        scope=changed_scope,
        temporal_context=state["context"],
    ) == ()
