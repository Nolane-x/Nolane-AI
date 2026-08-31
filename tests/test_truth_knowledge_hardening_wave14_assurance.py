from __future__ import annotations

from nolane.external_core.assurance_dependence_truth import DependenceTruthAssuranceGate
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
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.knowledge_undercutter_truth import JustificationUndercutterRegistry
from nolane.external_core.temporal_truth import TemporalContext
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


def _record(evidence, evidence_id, subject_id, source_id, channel):
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


def _state(*, decision_dependence: bool = True):
    state = {
        "knowledge": KnowledgeLedger(),
        "evidence": EvidenceLedger(),
        "semantics": RelationSemanticsRegistry(),
        "knowledge_temporal": TemporalKnowledgeView(),
        "evidence_temporal": TemporalEvidenceView(),
        "provenance": SourceProvenanceRegistry(),
        "dependence": SourceDependenceRegistry(),
        "justifications": KnowledgeJustificationRegistry(),
        "undercutters": JustificationUndercutterRegistry(),
        "context": TemporalContext.create(as_of=AS_OF),
    }
    _record(
        state["evidence"],
        "claim-support",
        "claim-high-v8",
        "claim-source",
        EvidenceChannel.OBSERVATION,
    )
    state["provenance"].register(_prov("claim-source", "claim-controller"))
    if decision_dependence:
        state["dependence"].register(_dep("claim-source", "basis:decision"))
    state["claim"] = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="claim-high-v8",
            subject="system",
            relation="is_safe",
            object="yes",
            risk=KnowledgeRisk.HIGH,
            evidence_ids=("claim-support",),
        )
    )
    return state


def _add_verifier(state, verifier_id, controller_id, channel, basis_ids):
    state["provenance"].register(_prov(verifier_id, controller_id))
    state["dependence"].register(_dep(verifier_id, *basis_ids))
    _record(
        state["evidence"],
        f"evidence:{verifier_id}",
        state["claim"].claim_id,
        verifier_id,
        channel,
    )


def _scope(state):
    return DependenceEpistemicJudge().relation_aware_temporal_scope(
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


def _verification(state, scope):
    ledger = DependenceTruthVerificationLedger()
    rows = (
        ("v-a", EvidenceChannel.TEST),
        ("v-b", EvidenceChannel.REPRODUCTION),
    )
    for verifier_id, channel in rows:
        ledger.record(
            DependenceTruthVerificationReceipt.create(
                receipt_id=f"receipt:{verifier_id}",
                claim_id=state["claim"].claim_id,
                verifier_id=verifier_id,
                channel=channel,
                passed=True,
                scope_digest=scope.digest,
                temporal_context_digest=state["context"].digest,
                as_of=state["context"].as_of,
                evidence_ids=(f"evidence:{verifier_id}",),
                source_provenance_digest=state["provenance"].projection_digest((verifier_id,)),
                source_dependence_digest=state["dependence"].projection_digest((verifier_id,)),
            )
        )
    return ledger


def _close(state):
    scope = _scope(state)
    verification = _verification(state, scope)
    gate = DependenceTruthAssuranceGate()
    certificate = gate.close(
        claim_id=state["claim"].claim_id,
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
        verification=verification,
    )
    return scope, verification, gate, certificate


def _validate(state, gate, verification, certificate):
    return gate.validate_certificate(
        certificate,
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
        verification=verification,
    )


def test_a14_high_assurance_rejects_two_controller_distinct_verifiers_on_same_basis():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:shared",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:shared",))
    _, _, _, certificate = _close(state)
    assert certificate.closed is False
    assert "insufficient_independent_verification" in certificate.reasons


def test_a14_high_assurance_accepts_two_disjoint_controller_and_basis_verifiers():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:b",))
    _, _, _, certificate = _close(state)
    assert certificate.closed is True
    assert certificate.reasons == ()


def test_a14_missing_decision_dependence_blocks_closure_fail_closed():
    state = _state(decision_dependence=False)
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:b",))
    _, _, _, certificate = _close(state)
    assert certificate.closed is False
    assert "source_dependence_incomplete" in certificate.reasons
    assert "verification_dependence_invalid" in certificate.reasons


def test_a14_relevant_dependence_revision_stales_certificate_but_unrelated_does_not():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:b",))
    _, verification, gate, certificate = _close(state)
    assert certificate.closed is True
    assert _validate(state, gate, verification, certificate)

    unrelated = state["dependence"].register(_dep("unrelated-source", "basis:u"))
    state["dependence"].register(
        SourceDependenceRevision.create(
            source_id="unrelated-source",
            revision=2,
            predecessor_digest=unrelated.digest,
            basis_ids=("basis:u2",),
        )
    )
    assert _validate(state, gate, verification, certificate)

    current = state["dependence"].current("claim-source")
    assert current is not None
    state["dependence"].register(
        SourceDependenceRevision.create(
            source_id="claim-source",
            revision=2,
            predecessor_digest=current.digest,
            basis_ids=("basis:decision-v2",),
        )
    )
    assert _validate(state, gate, verification, certificate) is False
