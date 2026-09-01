from __future__ import annotations

from nolane.external_core.assurance_context_truth import ContextTruthAssuranceGate
from nolane.external_core.assurance_observation_truth import ObservationTruthAssuranceGate
from nolane.external_core.epistemic_context_truth import ContextEpistemicJudge
from nolane.external_core.epistemic_observation_truth import ObservationEpistemicJudge
from nolane.external_core.evidence_context_truth import EvidenceContextBindingRegistry
from nolane.external_core.evidence_dependence_truth import (
    SourceDependenceRegistry,
    SourceDependenceRevision,
)
from nolane.external_core.evidence_observation_truth import ObservationResultLedger
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
from nolane.external_core.knowledge_observation_truth import ObservationRequirementRegistry
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.knowledge_undercutter_truth import JustificationUndercutterRegistry
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_context_truth import (
    ContextTruthVerificationLedger,
    ContextTruthVerificationReceipt,
)
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


def _dep(source_id: str, basis_id: str) -> SourceDependenceRevision:
    return SourceDependenceRevision.create(
        source_id=source_id,
        revision=1,
        basis_ids=(basis_id,),
    )


def _state():
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    provenance = SourceProvenanceRegistry()
    dependence = SourceDependenceRegistry()
    support = evidence.record(
        TruthEvidence.create(
            evidence_id="support:compat-v10",
            subject_id="claim:compat-v10",
            source_id="source:compat-v10",
            source_family="family:compat-v10",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:compat-v10",
        )
    )
    provenance.register(_prov("source:compat-v10", "controller:decision"))
    dependence.register(_dep("source:compat-v10", "basis:decision"))
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim:compat-v10",
            subject="system",
            relation="works",
            object="yes",
            risk=KnowledgeRisk.STANDARD,
            evidence_ids=(support.evidence_id,),
        )
    )
    return {
        "knowledge": knowledge,
        "evidence": evidence,
        "provenance": provenance,
        "dependence": dependence,
        "claim": claim,
        "semantics": RelationSemanticsRegistry(),
        "knowledge_temporal": TemporalKnowledgeView(),
        "evidence_temporal": TemporalEvidenceView(),
        "justifications": KnowledgeJustificationRegistry(),
        "undercutters": JustificationUndercutterRegistry(),
        "claim_context": ClaimContextBindingRegistry(),
        "evidence_context": EvidenceContextBindingRegistry(),
        "observation_requirements": ObservationRequirementRegistry(),
        "observation_results": ObservationResultLedger(),
        "truth_context": TruthContext.create(),
        "temporal_context": TemporalContext.create(as_of=AS_OF),
    }


def _v9_scope(state):
    return ContextEpistemicJudge().relation_aware_temporal_scope(
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


def _v10_scope(state):
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


def _add_verifier(state):
    verifier_id = "verifier:compat-v10"
    state["provenance"].register(_prov(verifier_id, "controller:verifier"))
    state["dependence"].register(_dep(verifier_id, "basis:verifier"))
    state["evidence"].record(
        TruthEvidence.create(
            evidence_id="evidence:verifier-compat-v10",
            subject_id=state["claim"].claim_id,
            source_id=verifier_id,
            source_family="family:verifier",
            channel=EvidenceChannel.TEST,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:verifier",
        )
    )
    return verifier_id


def test_a16_empty_observation_state_reproduces_v9_epistemic_semantics():
    state = _state()
    v9 = _v9_scope(state)
    v10 = _v10_scope(state)

    assert v10.audit_context_scope == v9
    assert v10.assessments == v9.assessments
    assert v10.debts == v9.debts
    assert v10.observation_debts == ()
    assert v10.observation_ids == ()
    assert v10.incomplete_observation_ids == ()


def test_a16_empty_observation_state_reproduces_v9_verification_and_assurance():
    state = _state()
    v9 = _v9_scope(state)
    v10 = _v10_scope(state)
    verifier_id = _add_verifier(state)

    v9_verification = ContextTruthVerificationLedger()
    v9_verification.record(
        ContextTruthVerificationReceipt.create(
            receipt_id="receipt:v9-compat",
            claim_id=state["claim"].claim_id,
            verifier_id=verifier_id,
            channel=EvidenceChannel.TEST,
            passed=True,
            scope_digest=v9.digest,
            truth_context_digest=state["truth_context"].digest,
            temporal_context_digest=state["temporal_context"].digest,
            as_of=state["temporal_context"].as_of,
            evidence_ids=("evidence:verifier-compat-v10",),
            source_provenance_digest=state["provenance"].projection_digest((verifier_id,)),
            source_dependence_digest=state["dependence"].projection_digest((verifier_id,)),
            evidence_context_digest=state["evidence_context"].projection_digest(("evidence:verifier-compat-v10",)),
        )
    )
    v10_verification = ObservationTruthVerificationLedger()
    v10_verification.record(
        ObservationTruthVerificationReceipt.create(
            receipt_id="receipt:v10-compat",
            claim_id=state["claim"].claim_id,
            verifier_id=verifier_id,
            channel=EvidenceChannel.TEST,
            passed=True,
            scope_digest=v10.digest,
            truth_context_digest=state["truth_context"].digest,
            temporal_context_digest=state["temporal_context"].digest,
            as_of=state["temporal_context"].as_of,
            observation_requirement_digest=v10.observation_requirement_digest,
            observation_result_digest=v10.observation_result_digest,
            evidence_ids=("evidence:verifier-compat-v10",),
            source_provenance_digest=state["provenance"].projection_digest((verifier_id,)),
            source_dependence_digest=state["dependence"].projection_digest((verifier_id,)),
            evidence_context_digest=state["evidence_context"].projection_digest(("evidence:verifier-compat-v10",)),
        )
    )

    v9_coverage = v9_verification.coverage(
        state["claim"].claim_id,
        scope=v9,
        truth_context=state["truth_context"],
        temporal_context=state["temporal_context"],
        evidence=state["evidence"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        source_dependence=state["dependence"],
        claim_context=state["claim_context"],
        evidence_context=state["evidence_context"],
    )
    v10_coverage = v10_verification.coverage(
        state["claim"].claim_id,
        scope=v10,
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
    assert v10_coverage.independent_source_count == v9_coverage.independent_source_count
    assert v10_coverage.channel_count == v9_coverage.channel_count

    v9_certificate = ContextTruthAssuranceGate().close(
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
        verification=v9_verification,
    )
    v10_certificate = ObservationTruthAssuranceGate().close(
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
        verification=v10_verification,
    )
    assert v10_certificate.closed == v9_certificate.closed
    assert v10_certificate.reasons == v9_certificate.reasons
