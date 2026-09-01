from __future__ import annotations

import pytest

from nolane.external_core.epistemic_observation_truth import ObservationEpistemicJudge
from nolane.external_core.evidence_context_truth import EvidenceContextBindingRegistry
from nolane.external_core.evidence_dependence_truth import (
    SourceDependenceRegistry,
    SourceDependenceRevision,
)
from nolane.external_core.evidence_observation_truth import (
    ObservationOutcome,
    ObservationResultLedger,
    ObservationResultRevision,
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
from nolane.external_core.knowledge_context_truth import ClaimContextBindingRegistry, TruthContext
from nolane.external_core.knowledge_justification_truth import KnowledgeJustificationRegistry
from nolane.external_core.knowledge_observation_truth import (
    ObservationRequirement,
    ObservationRequirementRegistry,
    ObservationRequirementSetRevision,
)
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger
from nolane.external_core.knowledge_undercutter_truth import JustificationUndercutterRegistry
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_context_truth import ContextTruthVerificationReceipt
from nolane.external_core.verification_observation_truth import (
    ObservationTruthVerificationLedger,
    ObservationTruthVerificationReceipt,
)
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-09-01T00:00:00Z"


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


def _record(state, *, evidence_id: str, source_id: str, channel: EvidenceChannel) -> TruthEvidence:
    return state["evidence"].record(
        TruthEvidence.create(
            evidence_id=evidence_id,
            subject_id=state["claim"].claim_id,
            source_id=source_id,
            source_family=f"family:{source_id}",
            channel=channel,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest=f"payload:{evidence_id}",
        )
    )


def _state(*, with_requirement: bool = True):
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    provenance = SourceProvenanceRegistry()
    dependence = SourceDependenceRegistry()
    target_evidence = evidence.record(
        TruthEvidence.create(
            evidence_id="claim-support",
            subject_id="claim-v10",
            source_id="claim-source",
            source_family="family:claim-source",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:claim-support",
        )
    )
    provenance.register(_prov("claim-source", "origin-controller"))
    dependence.register(_dep("claim-source", "basis:claim"))
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-v10",
            subject="system",
            relation="works",
            object="yes",
            evidence_ids=(target_evidence.evidence_id,),
        )
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
        "claim_context": ClaimContextBindingRegistry(),
        "evidence_context": EvidenceContextBindingRegistry(),
        "observation_requirements": ObservationRequirementRegistry(),
        "observation_results": ObservationResultLedger(),
        "temporal_context": TemporalContext.create(as_of=AS_OF),
        "truth_context": TruthContext.create(),
        "claim": claim,
        "target_evidence": target_evidence,
    }
    if with_requirement:
        requirement = ObservationRequirement.create(
            claim=claim,
            observation_id="obs.target.001",
            channel=EvidenceChannel.OBSERVATION,
        )
        state["observation_requirements"].register(
            ObservationRequirementSetRevision.create(
                claim=claim,
                requirements=(requirement,),
            ),
            knowledge=knowledge,
        )
        state["observation_results"].register(
            ObservationResultRevision.create(
                requirement=requirement,
                outcome=ObservationOutcome.OBSERVED,
                evidence=target_evidence,
            ),
            evidence=evidence,
        )
        state["requirement"] = requirement
        state["observation_result"] = state["observation_results"].current(requirement.digest)
    _recompute_scope(state)
    return state


def _recompute_scope(state):
    state["scope"] = ObservationEpistemicJudge().relation_aware_temporal_scope(
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
        observation_requirements=state["observation_requirements"],
        observation_results=state["observation_results"],
    )
    return state["scope"]


def _add_verifier(
    state,
    verifier_id: str,
    controller_id: str,
    channel: EvidenceChannel,
    basis_ids: tuple[str, ...],
) -> TruthEvidence:
    state["provenance"].register(_prov(verifier_id, controller_id))
    state["dependence"].register(_dep(verifier_id, *basis_ids))
    return _record(
        state,
        evidence_id=f"evidence:{verifier_id}",
        source_id=verifier_id,
        channel=channel,
    )


def _receipt(state, verifier_id: str, channel: EvidenceChannel, *, passed: bool = True):
    return ObservationTruthVerificationReceipt.create(
        receipt_id=f"receipt:{verifier_id}:{'pass' if passed else 'fail'}",
        claim_id=state["claim"].claim_id,
        verifier_id=verifier_id,
        channel=channel,
        passed=passed,
        scope_digest=state["scope"].digest,
        truth_context_digest=state["truth_context"].digest,
        temporal_context_digest=state["temporal_context"].digest,
        as_of=state["temporal_context"].as_of,
        observation_requirement_digest=state["scope"].observation_requirement_digest,
        observation_result_digest=state["scope"].observation_result_digest,
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
        observation_requirements=state["observation_requirements"],
        observation_results=state["observation_results"],
    )


def test_a16_verification_receipt_binds_exact_observation_scope():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    ledger = ObservationTruthVerificationLedger()
    receipt = ledger.record(_receipt(state, "v-a", EvidenceChannel.TEST))
    coverage = _coverage(state, ledger)
    assert coverage.independent_source_count == 1
    assert ledger.receipt_is_current(
        receipt,
        scope=state["scope"],
        truth_context=state["truth_context"],
        temporal_context=state["temporal_context"],
    )


def test_a16_relevant_observation_result_revision_stales_verification():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    ledger = ObservationTruthVerificationLedger()
    receipt = ledger.record(_receipt(state, "v-a", EvidenceChannel.TEST))
    assert _coverage(state, ledger).independent_source_count == 1

    previous = state["observation_result"]
    state["observation_results"].register(
        ObservationResultRevision.create(
            requirement=state["requirement"],
            revision=2,
            predecessor_digest=previous.digest,
            outcome=ObservationOutcome.TIMEOUT,
            reason="new timeout",
        ),
        evidence=state["evidence"],
    )
    coverage = _coverage(state, ledger)
    assert coverage.independent_source_count == 0
    assert receipt.receipt_id in coverage.invalid_receipt_ids
    assert "verification_observation_results_stale" in coverage.issues


def test_a16_unrelated_observation_revision_does_not_stale_verification():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    ledger = ObservationTruthVerificationLedger()
    ledger.record(_receipt(state, "v-a", EvidenceChannel.TEST))

    unrelated = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="claim-unrelated-observation",
            subject="other",
            relation="works",
            object="yes",
        )
    )
    requirement = ObservationRequirement.create(
        claim=unrelated,
        observation_id="obs.unrelated.001",
        channel=EvidenceChannel.AUDIT,
    )
    state["observation_requirements"].register(
        ObservationRequirementSetRevision.create(
            claim=unrelated,
            requirements=(requirement,),
        ),
        knowledge=state["knowledge"],
    )
    state["observation_results"].register(
        ObservationResultRevision.create(
            requirement=requirement,
            outcome=ObservationOutcome.MISSING,
            reason="unrelated",
        ),
        evidence=state["evidence"],
    )
    assert _coverage(state, ledger).independent_source_count == 1


def test_a16_observation_identity_never_mints_independence_credit():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:shared",))
    _add_verifier(
        state,
        "v-b",
        "controller-b",
        EvidenceChannel.REPRODUCTION,
        ("basis:shared",),
    )
    ledger = ObservationTruthVerificationLedger()
    ledger.record(_receipt(state, "v-a", EvidenceChannel.TEST))
    ledger.record(_receipt(state, "v-b", EvidenceChannel.REPRODUCTION))
    coverage = _coverage(state, ledger)
    assert coverage.independent_source_count == 1
    assert len(coverage.passing_independence_keys) == 1


def test_a16_negative_receipt_is_retained():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    ledger = ObservationTruthVerificationLedger()
    receipt = ledger.record(_receipt(state, "v-a", EvidenceChannel.TEST, passed=False))
    coverage = _coverage(state, ledger)
    assert coverage.negative_receipt_ids == (receipt.receipt_id,)
    assert coverage.independent_source_count == 0


def test_a16_v9_receipt_cannot_masquerade_as_v10():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    old = ContextTruthVerificationReceipt.create(
        receipt_id="receipt:v9",
        claim_id=state["claim"].claim_id,
        verifier_id="v-a",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest=state["scope"].audit_context_scope.digest,
        truth_context_digest=state["truth_context"].digest,
        temporal_context_digest=state["temporal_context"].digest,
        as_of=state["temporal_context"].as_of,
        evidence_ids=("evidence:v-a",),
        source_provenance_digest=state["provenance"].projection_digest(("v-a",)),
        source_dependence_digest=state["dependence"].projection_digest(("v-a",)),
        evidence_context_digest=state["evidence_context"].projection_digest(("evidence:v-a",)),
    )
    with pytest.raises(TypeError, match="v10 receipts only"):
        ObservationTruthVerificationLedger().record(old)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported observation verification protocol"):
        ObservationTruthVerificationReceipt.from_state(old.to_state())
