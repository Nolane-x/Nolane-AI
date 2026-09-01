from __future__ import annotations

import pytest

from nolane.external_core.assurance_context_truth import ContextTruthClosureCertificate
from nolane.external_core.assurance_observation_truth import (
    ObservationTruthAssuranceGate,
    ObservationTruthClosureCertificate,
)
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
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.knowledge_undercutter_truth import JustificationUndercutterRegistry
from nolane.external_core.temporal_truth import TemporalContext
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


def _state():
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    provenance = SourceProvenanceRegistry()
    dependence = SourceDependenceRegistry()
    support = evidence.record(
        TruthEvidence.create(
            evidence_id="claim-support",
            subject_id="claim-high-v10",
            source_id="claim-source",
            source_family="family:claim-source",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:claim-support",
        )
    )
    provenance.register(_prov("claim-source", "claim-controller"))
    dependence.register(_dep("claim-source", "basis:decision"))
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-high-v10",
            subject="system",
            relation="is_safe",
            object="yes",
            risk=KnowledgeRisk.HIGH,
            evidence_ids=(support.evidence_id,),
        )
    )
    requirements = ObservationRequirementRegistry()
    results = ObservationResultLedger()
    requirement = ObservationRequirement.create(
        claim=claim,
        observation_id="obs.target.001",
        channel=EvidenceChannel.OBSERVATION,
    )
    requirements.register(
        ObservationRequirementSetRevision.create(claim=claim, requirements=(requirement,)),
        knowledge=knowledge,
    )
    observed = results.register(
        ObservationResultRevision.create(
            requirement=requirement,
            outcome=ObservationOutcome.OBSERVED,
            evidence=support,
        ),
        evidence=evidence,
    )
    return {
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
        "observation_requirements": requirements,
        "observation_results": results,
        "temporal_context": TemporalContext.create(as_of=AS_OF),
        "truth_context": TruthContext.create(),
        "claim": claim,
        "requirement": requirement,
        "observation_result": observed,
    }


def _add_verifier(state, verifier_id: str, controller_id: str, channel: EvidenceChannel, basis_ids: tuple[str, ...]):
    state["provenance"].register(_prov(verifier_id, controller_id))
    state["dependence"].register(_dep(verifier_id, *basis_ids))
    return state["evidence"].record(
        TruthEvidence.create(
            evidence_id=f"evidence:{verifier_id}",
            subject_id=state["claim"].claim_id,
            source_id=verifier_id,
            source_family=f"family:{verifier_id}",
            channel=channel,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest=f"payload:{verifier_id}",
        )
    )


def _scope(state):
    return ObservationEpistemicJudge().relation_aware_temporal_scope(
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


def _verification(state, scope):
    ledger = ObservationTruthVerificationLedger()
    for verifier_id, channel in (
        ("v-a", EvidenceChannel.TEST),
        ("v-b", EvidenceChannel.REPRODUCTION),
    ):
        ledger.record(
            ObservationTruthVerificationReceipt.create(
                receipt_id=f"receipt:{verifier_id}",
                claim_id=state["claim"].claim_id,
                verifier_id=verifier_id,
                channel=channel,
                passed=True,
                scope_digest=scope.digest,
                truth_context_digest=state["truth_context"].digest,
                temporal_context_digest=state["temporal_context"].digest,
                as_of=state["temporal_context"].as_of,
                observation_requirement_digest=scope.observation_requirement_digest,
                observation_result_digest=scope.observation_result_digest,
                evidence_ids=(f"evidence:{verifier_id}",),
                source_provenance_digest=state["provenance"].projection_digest((verifier_id,)),
                source_dependence_digest=state["dependence"].projection_digest((verifier_id,)),
                evidence_context_digest=state["evidence_context"].projection_digest((f"evidence:{verifier_id}",)),
            )
        )
    return ledger


def _close(state):
    scope = _scope(state)
    verification = _verification(state, scope)
    gate = ObservationTruthAssuranceGate()
    certificate = gate.close(
        claim_id=state["claim"].claim_id,
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
        verification=verification,
    )
    return scope, verification, gate, certificate


def _validate(state, gate, verification, certificate):
    return gate.validate_certificate(
        certificate,
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
        verification=verification,
    )


def test_a16_high_assurance_closes_with_complete_observation_and_two_disjoint_verifiers():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:b",))
    _, _, _, certificate = _close(state)
    assert certificate.closed is True
    assert certificate.reasons == ()


def test_a16_high_assurance_preserves_common_basis_collapse():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:shared",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:shared",))
    _, _, _, certificate = _close(state)
    assert certificate.closed is False
    assert "insufficient_independent_verification" in certificate.reasons


def test_a16_incomplete_required_observation_blocks_closure_without_becoming_refutation():
    state = _state()
    previous = state["observation_result"]
    state["observation_results"].register(
        ObservationResultRevision.create(
            requirement=state["requirement"],
            revision=2,
            predecessor_digest=previous.digest,
            outcome=ObservationOutcome.TIMEOUT,
            reason="deadline",
        ),
        evidence=state["evidence"],
    )
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:b",))
    scope, _, _, certificate = _close(state)
    assert scope.audit_context_scope.assessment(state["claim"].claim_id).disposition.value == "supported"
    assert scope.assessment(state["claim"].claim_id).disposition.value == "unknown"
    assert certificate.closed is False
    assert "observation_completeness_invalid" in certificate.reasons
    assert "critical_observation_debt" in certificate.reasons


def test_a16_relevant_observation_result_revision_stales_certificate_but_unrelated_does_not():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:b",))
    _, verification, gate, certificate = _close(state)
    assert certificate.closed is True
    assert _validate(state, gate, verification, certificate)

    unrelated = state["knowledge"].add(
        KnowledgeClaim.create(claim_id="claim-unrelated-v10", subject="other", relation="is", object="yes")
    )
    unrelated_requirement = ObservationRequirement.create(
        claim=unrelated,
        observation_id="obs.unrelated.001",
        channel=EvidenceChannel.AUDIT,
    )
    state["observation_requirements"].register(
        ObservationRequirementSetRevision.create(claim=unrelated, requirements=(unrelated_requirement,)),
        knowledge=state["knowledge"],
    )
    state["observation_results"].register(
        ObservationResultRevision.create(
            requirement=unrelated_requirement,
            outcome=ObservationOutcome.MISSING,
            reason="unrelated",
        ),
        evidence=state["evidence"],
    )
    assert _validate(state, gate, verification, certificate)

    previous = state["observation_result"]
    state["observation_results"].register(
        ObservationResultRevision.create(
            requirement=state["requirement"],
            revision=2,
            predecessor_digest=previous.digest,
            outcome=ObservationOutcome.TIMEOUT,
            reason="relevant",
        ),
        evidence=state["evidence"],
    )
    assert _validate(state, gate, verification, certificate) is False


def test_a16_v9_certificate_cannot_masquerade_as_v10():
    old = ContextTruthClosureCertificate.create(
        claim_id="claim-v9",
        risk=KnowledgeRisk.STANDARD,
        scope_digest="scope:v9",
        verification_scope_digest="verification:v9",
        truth_context_digest=TruthContext.create().digest,
        temporal_context_digest=TemporalContext.create(as_of=AS_OF).digest,
        as_of=AS_OF,
        verification_receipt_ids=(),
        epistemic_debt_ids=(),
        closed=False,
        reasons=("v9",),
    )
    with pytest.raises(ValueError, match="unsupported observation assurance protocol"):
        ObservationTruthClosureCertificate.from_state(old.to_state())
