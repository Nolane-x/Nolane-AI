from __future__ import annotations

import pytest

from nolane.external_core.epistemic_dependence_truth import DependenceEpistemicJudge
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
from nolane.external_core.knowledge_justification_truth import KnowledgeJustificationRegistry
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger
from nolane.external_core.knowledge_undercutter_truth import JustificationUndercutterRegistry
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_defeasible_truth import DefeasibleTruthVerificationReceipt
from nolane.external_core.verification_dependence_truth import (
    DependenceTruthVerificationLedger,
    DependenceTruthVerificationReceipt,
)
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


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
    dependence = SourceDependenceRegistry()
    justifications = KnowledgeJustificationRegistry()
    undercutters = JustificationUndercutterRegistry()
    context = TemporalContext.create(as_of=AS_OF)

    _record(
        evidence,
        evidence_id="claim-support",
        subject_id="claim-v8",
        source_id="claim-source",
        channel=EvidenceChannel.OBSERVATION,
    )
    provenance.register(_prov("claim-source", "origin-controller"))
    dependence.register(_dep("claim-source", "basis:claim-measurement"))
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-v8",
            subject="system",
            relation="works",
            object="yes",
            evidence_ids=("claim-support",),
        )
    )
    state = {
        "knowledge": knowledge,
        "evidence": evidence,
        "semantics": semantics,
        "knowledge_temporal": knowledge_temporal,
        "evidence_temporal": evidence_temporal,
        "provenance": provenance,
        "dependence": dependence,
        "justifications": justifications,
        "undercutters": undercutters,
        "context": context,
        "claim": claim,
    }
    _recompute_scope(state)
    return state


def _recompute_scope(state):
    state["scope"] = DependenceEpistemicJudge().relation_aware_temporal_scope(
        state["claim"].claim_id,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        source_dependence=state["dependence"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
    )
    return state["scope"]


def _add_verifier(
    state,
    verifier_id: str,
    controller_id: str,
    channel: EvidenceChannel,
    basis_ids: tuple[str, ...] | None,
) -> None:
    state["provenance"].register(_prov(verifier_id, controller_id))
    if basis_ids is not None:
        state["dependence"].register(_dep(verifier_id, *basis_ids))
    _record(
        state["evidence"],
        evidence_id=f"evidence:{verifier_id}",
        subject_id=state["claim"].claim_id,
        source_id=verifier_id,
        channel=channel,
    )


def _receipt(state, verifier_id: str, channel: EvidenceChannel, *, passed: bool = True):
    return DependenceTruthVerificationReceipt.create(
        receipt_id=f"receipt:{verifier_id}:{'pass' if passed else 'fail'}",
        claim_id=state["claim"].claim_id,
        verifier_id=verifier_id,
        channel=channel,
        passed=passed,
        scope_digest=state["scope"].digest,
        temporal_context_digest=state["context"].digest,
        as_of=state["context"].as_of,
        evidence_ids=(f"evidence:{verifier_id}",),
        source_provenance_digest=state["provenance"].projection_digest((verifier_id,)),
        source_dependence_digest=state["dependence"].projection_digest((verifier_id,)),
    )


def _coverage(state, ledger):
    return ledger.coverage(
        state["claim"].claim_id,
        scope=state["scope"],
        temporal_context=state["context"],
        evidence=state["evidence"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        source_dependence=state["dependence"],
    )


def test_a14_two_distinct_controllers_sharing_basis_collapse_to_one_group():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:shared",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:shared",))
    ledger = DependenceTruthVerificationLedger()
    ledger.record(_receipt(state, "v-a", EvidenceChannel.TEST))
    ledger.record(_receipt(state, "v-b", EvidenceChannel.REPRODUCTION))

    coverage = _coverage(state, ledger)
    assert coverage.independent_source_count == 1
    assert len(coverage.passing_independence_keys) == 1


def test_a14_transitive_basis_overlap_collapses_complete_component():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:x",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:x", "basis:y"))
    _add_verifier(state, "v-c", "controller-c", EvidenceChannel.ADVERSARIAL, ("basis:y",))
    ledger = DependenceTruthVerificationLedger()
    for verifier_id, channel in (
        ("v-a", EvidenceChannel.TEST),
        ("v-b", EvidenceChannel.REPRODUCTION),
        ("v-c", EvidenceChannel.ADVERSARIAL),
    ):
        ledger.record(_receipt(state, verifier_id, channel))

    coverage = _coverage(state, ledger)
    assert coverage.independent_source_count == 1


def test_a14_verifier_sharing_decision_basis_gets_zero_independence_credit():
    state = _state()
    _add_verifier(
        state,
        "v-shared-origin-basis",
        "different-controller",
        EvidenceChannel.TEST,
        ("basis:claim-measurement",),
    )
    ledger = DependenceTruthVerificationLedger()
    receipt = _receipt(state, "v-shared-origin-basis", EvidenceChannel.TEST)
    ledger.record(receipt)

    coverage = _coverage(state, ledger)
    assert coverage.independent_source_count == 0
    assert coverage.non_independent_receipt_ids == (receipt.receipt_id,)


def test_a14_disjoint_controller_and_basis_sources_remain_independent():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:b",))
    ledger = DependenceTruthVerificationLedger()
    ledger.record(_receipt(state, "v-a", EvidenceChannel.TEST))
    ledger.record(_receipt(state, "v-b", EvidenceChannel.REPRODUCTION))

    coverage = _coverage(state, ledger)
    assert coverage.independent_source_count == 2
    assert len(coverage.passing_independence_keys) == 2


def test_a14_missing_dependence_metadata_cannot_mint_independence():
    state = _state()
    _add_verifier(state, "v-missing", "controller-missing", EvidenceChannel.TEST, None)
    ledger = DependenceTruthVerificationLedger()
    receipt = _receipt(state, "v-missing", EvidenceChannel.TEST)
    ledger.record(receipt)

    coverage = _coverage(state, ledger)
    assert coverage.independent_source_count == 0
    assert coverage.invalid_receipt_ids == (receipt.receipt_id,)
    assert "verification_source_dependence_missing" in coverage.issues


def test_a14_verifier_dependence_revision_invalidates_existing_receipt():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    ledger = DependenceTruthVerificationLedger()
    receipt = _receipt(state, "v-a", EvidenceChannel.TEST)
    ledger.record(receipt)
    assert _coverage(state, ledger).independent_source_count == 1

    current = state["dependence"].current("v-a")
    assert current is not None
    state["dependence"].register(
        SourceDependenceRevision.create(
            source_id="v-a",
            revision=2,
            predecessor_digest=current.digest,
            basis_ids=("basis:a-v2",),
        )
    )
    coverage = _coverage(state, ledger)
    assert coverage.independent_source_count == 0
    assert coverage.invalid_receipt_ids == (receipt.receipt_id,)
    assert "verification_source_dependence_stale" in coverage.issues


def test_a14_negative_receipt_is_retained():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    ledger = DependenceTruthVerificationLedger()
    receipt = _receipt(state, "v-a", EvidenceChannel.TEST, passed=False)
    ledger.record(receipt)
    coverage = _coverage(state, ledger)
    assert coverage.negative_receipt_ids == (receipt.receipt_id,)
    assert coverage.independent_source_count == 0


def test_a14_v7_receipt_cannot_masquerade_as_v8():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    old = DefeasibleTruthVerificationReceipt.create(
        receipt_id="receipt:v7",
        claim_id=state["claim"].claim_id,
        verifier_id="v-a",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest=state["scope"].defeasible_scope.digest,
        temporal_context_digest=state["context"].digest,
        as_of=state["context"].as_of,
        evidence_ids=("evidence:v-a",),
        source_provenance_digest=state["provenance"].projection_digest(("v-a",)),
    )
    with pytest.raises(TypeError, match="v8 receipts only"):
        DependenceTruthVerificationLedger().record(old)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported dependence verification protocol"):
        DependenceTruthVerificationReceipt.from_state(old.to_state())
