from __future__ import annotations

import pytest

from nolane.external_core.epistemic_context_truth import ContextEpistemicJudge
from nolane.external_core.evidence_context_truth import (
    EvidenceContextBindingRegistry,
    EvidenceContextBindingRevision,
)
from nolane.external_core.evidence_dependence_truth import (
    SourceDependenceRegistry,
    SourceDependenceRevision,
)
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
from nolane.external_core.knowledge_context_truth import (
    ClaimContextBindingRegistry,
    ClaimContextBindingRevision,
    TruthContext,
)
from nolane.external_core.knowledge_justification_truth import KnowledgeJustificationRegistry
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger
from nolane.external_core.knowledge_undercutter_truth import JustificationUndercutterRegistry
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_context_truth import (
    ContextTruthVerificationLedger,
    ContextTruthVerificationReceipt,
)
from nolane.external_core.verification_dependence_truth import DependenceTruthVerificationReceipt
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"
US = TruthContext.create(qualifiers=(("jurisdiction", "us"),))
EU = TruthContext.create(qualifiers=(("jurisdiction", "eu"),))


def _prov(source_id: str, controller_id: str) -> SourceProvenanceRevision:
    return SourceProvenanceRevision.create(
        source_id=source_id,
        revision=1,
        controller_id=controller_id,
        parent_source_ids=(),
    )


def _dep(source_id: str, *basis_ids: str) -> SourceDependenceRevision:
    return SourceDependenceRevision.create(
        source_id=source_id,
        revision=1,
        basis_ids=tuple(basis_ids),
    )


def _record(
    evidence: EvidenceLedger,
    *,
    evidence_id: str,
    subject_id: str,
    source_id: str,
    channel: EvidenceChannel,
) -> TruthEvidence:
    return evidence.record(
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
    provenance = SourceProvenanceRegistry()
    dependence = SourceDependenceRegistry()
    claim_context = ClaimContextBindingRegistry()
    evidence_context = EvidenceContextBindingRegistry()
    temporal_context = TemporalContext.create(as_of=AS_OF)

    claim_evidence = _record(
        evidence,
        evidence_id="claim-support",
        subject_id="claim-v9",
        source_id="claim-source",
        channel=EvidenceChannel.OBSERVATION,
    )
    provenance.register(_prov("claim-source", "origin-controller"))
    dependence.register(_dep("claim-source", "basis:claim"))
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-v9",
            subject="system",
            relation="works",
            object="yes",
            evidence_ids=(claim_evidence.evidence_id,),
        )
    )
    claim_context.register(
        ClaimContextBindingRevision.create(
            claim=claim,
            qualifiers=(("jurisdiction", "us"),),
        ),
        knowledge=knowledge,
    )
    evidence_context.register(
        EvidenceContextBindingRevision.create(
            evidence=claim_evidence,
            qualifiers=(("jurisdiction", "us"),),
        ),
        evidence=evidence,
    )

    state = {
        "knowledge": knowledge,
        "evidence": evidence,
        "semantics": RelationSemanticsRegistry(),
        "knowledge_temporal": TemporalKnowledgeView(),
        "evidence_temporal": TemporalEvidenceView(),
        "provenance": provenance,
        "dependence": dependence,
        "justifications": KnowledgeJustificationRegistry(),
        "undercutters": JustificationUndercutterRegistry(),
        "claim_context": claim_context,
        "evidence_context": evidence_context,
        "temporal_context": temporal_context,
        "truth_context": US,
        "claim": claim,
    }
    _recompute_scope(state)
    return state


def _recompute_scope(state):
    state["scope"] = ContextEpistemicJudge().relation_aware_temporal_scope(
        state["claim"].claim_id,
        truth_context=state["truth_context"],
        temporal_context=state["temporal_context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        source_dependence=state["dependence"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
        claim_context=state["claim_context"],
        evidence_context=state["evidence_context"],
    )
    return state["scope"]


def _add_verifier(
    state,
    verifier_id: str,
    controller_id: str,
    channel: EvidenceChannel,
    basis_ids: tuple[str, ...],
    *,
    jurisdiction: str = "us",
) -> TruthEvidence:
    state["provenance"].register(_prov(verifier_id, controller_id))
    state["dependence"].register(_dep(verifier_id, *basis_ids))
    item = _record(
        state["evidence"],
        evidence_id=f"evidence:{verifier_id}",
        subject_id=state["claim"].claim_id,
        source_id=verifier_id,
        channel=channel,
    )
    state["evidence_context"].register(
        EvidenceContextBindingRevision.create(
            evidence=item,
            qualifiers=(("jurisdiction", jurisdiction),),
        ),
        evidence=state["evidence"],
    )
    return item


def _receipt(state, verifier_id: str, channel: EvidenceChannel, *, passed: bool = True):
    return ContextTruthVerificationReceipt.create(
        receipt_id=f"receipt:{verifier_id}:{'pass' if passed else 'fail'}",
        claim_id=state["claim"].claim_id,
        verifier_id=verifier_id,
        channel=channel,
        passed=passed,
        scope_digest=state["scope"].digest,
        truth_context_digest=state["truth_context"].digest,
        temporal_context_digest=state["temporal_context"].digest,
        as_of=state["temporal_context"].as_of,
        evidence_ids=(f"evidence:{verifier_id}",),
        source_provenance_digest=state["provenance"].projection_digest((verifier_id,)),
        source_dependence_digest=state["dependence"].projection_digest((verifier_id,)),
        evidence_context_digest=state["evidence_context"].projection_digest(
            (f"evidence:{verifier_id}",)
        ),
    )


def _coverage(state, ledger):
    return ledger.coverage(
        state["claim"].claim_id,
        scope=state["scope"],
        truth_context=state["truth_context"],
        temporal_context=state["temporal_context"],
        evidence=state["evidence"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        source_dependence=state["dependence"],
        claim_context=state["claim_context"],
        evidence_context=state["evidence_context"],
    )


def test_a15_verification_receipt_binds_exact_truth_context():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    ledger = ContextTruthVerificationLedger()
    receipt = _receipt(state, "v-a", EvidenceChannel.TEST)
    ledger.record(receipt)

    assert _coverage(state, ledger).independent_source_count == 1
    assert ledger.receipt_is_current(
        receipt,
        scope=state["scope"],
        truth_context=US,
        temporal_context=state["temporal_context"],
    )
    assert not ledger.receipt_is_current(
        receipt,
        scope=state["scope"],
        truth_context=EU,
        temporal_context=state["temporal_context"],
    )


def test_a15_context_mismatched_verification_evidence_is_invalid_not_independent():
    state = _state()
    _add_verifier(
        state,
        "v-eu",
        "controller-eu",
        EvidenceChannel.TEST,
        ("basis:eu",),
        jurisdiction="eu",
    )
    ledger = ContextTruthVerificationLedger()
    receipt = _receipt(state, "v-eu", EvidenceChannel.TEST)
    ledger.record(receipt)

    coverage = _coverage(state, ledger)
    assert coverage.independent_source_count == 0
    assert coverage.invalid_receipt_ids == (receipt.receipt_id,)
    assert "verification_evidence_context_mismatch" in coverage.issues


def test_a15_relevant_verification_evidence_context_revision_stales_receipt():
    state = _state()
    item = _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    ledger = ContextTruthVerificationLedger()
    receipt = _receipt(state, "v-a", EvidenceChannel.TEST)
    ledger.record(receipt)
    assert _coverage(state, ledger).independent_source_count == 1

    previous = state["evidence_context"].current(item.evidence_id)
    assert previous is not None
    state["evidence_context"].register(
        EvidenceContextBindingRevision.create(
            evidence=item,
            revision=2,
            predecessor_digest=previous.digest,
            qualifiers=(("jurisdiction", "us"), ("mode", "strict")),
        ),
        evidence=state["evidence"],
    )

    coverage = _coverage(state, ledger)
    assert coverage.independent_source_count == 0
    assert coverage.invalid_receipt_ids == (receipt.receipt_id,)
    assert "verification_evidence_context_stale" in coverage.issues


def test_a15_unrelated_context_revision_does_not_stale_receipt():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    ledger = ContextTruthVerificationLedger()
    receipt = _receipt(state, "v-a", EvidenceChannel.TEST)
    ledger.record(receipt)

    unrelated = _record(
        state["evidence"],
        evidence_id="unrelated",
        subject_id="other-claim",
        source_id="other-source",
        channel=EvidenceChannel.OBSERVATION,
    )
    state["evidence_context"].register(
        EvidenceContextBindingRevision.create(
            evidence=unrelated,
            qualifiers=(("jurisdiction", "eu"),),
        ),
        evidence=state["evidence"],
    )

    assert _coverage(state, ledger).independent_source_count == 1


def test_a15_context_change_never_mints_independence_credit():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:shared",))
    _add_verifier(
        state,
        "v-b",
        "controller-b",
        EvidenceChannel.REPRODUCTION,
        ("basis:shared",),
    )
    ledger = ContextTruthVerificationLedger()
    ledger.record(_receipt(state, "v-a", EvidenceChannel.TEST))
    ledger.record(_receipt(state, "v-b", EvidenceChannel.REPRODUCTION))

    coverage = _coverage(state, ledger)
    assert coverage.independent_source_count == 1
    assert len(coverage.passing_independence_keys) == 1


def test_a15_negative_receipt_is_retained():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    ledger = ContextTruthVerificationLedger()
    receipt = _receipt(state, "v-a", EvidenceChannel.TEST, passed=False)
    ledger.record(receipt)
    coverage = _coverage(state, ledger)
    assert coverage.negative_receipt_ids == (receipt.receipt_id,)
    assert coverage.independent_source_count == 0


def test_a15_v8_receipt_cannot_masquerade_as_v9():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    old = DependenceTruthVerificationReceipt.create(
        receipt_id="receipt:v8",
        claim_id=state["claim"].claim_id,
        verifier_id="v-a",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest=state["scope"].audit_dependence_scope.digest,
        temporal_context_digest=state["temporal_context"].digest,
        as_of=state["temporal_context"].as_of,
        evidence_ids=("evidence:v-a",),
        source_provenance_digest=state["provenance"].projection_digest(("v-a",)),
        source_dependence_digest=state["dependence"].projection_digest(("v-a",)),
    )
    with pytest.raises(TypeError, match="v9 receipts only"):
        ContextTruthVerificationLedger().record(old)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported context verification protocol"):
        ContextTruthVerificationReceipt.from_state(old.to_state())
