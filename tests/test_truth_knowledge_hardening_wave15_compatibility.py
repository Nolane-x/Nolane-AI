from __future__ import annotations

from nolane.external_core.epistemic_context_truth import ContextEpistemicJudge
from nolane.external_core.epistemic_dependence_truth import DependenceEpistemicJudge
from nolane.external_core.evidence_context_truth import EvidenceContextBindingRegistry
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
from nolane.external_core.knowledge_context_truth import ClaimContextBindingRegistry, TruthContext
from nolane.external_core.knowledge_justification_truth import KnowledgeJustificationRegistry
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger
from nolane.external_core.knowledge_undercutter_truth import JustificationUndercutterRegistry
from nolane.external_core.temporal_truth import TemporalContext
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


def _source_provenance(source_id: str) -> SourceProvenanceRevision:
    return SourceProvenanceRevision.create(
        source_id=source_id,
        revision=1,
        controller_id=f"controller:{source_id}",
        parent_source_ids=(),
    )


def _source_dependence(source_id: str) -> SourceDependenceRevision:
    return SourceDependenceRevision.create(
        source_id=source_id,
        revision=1,
        basis_ids=(f"basis:{source_id}",),
    )


def test_a15_empty_context_and_empty_registries_reproduce_v8_epistemic_semantics():
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    semantics = RelationSemanticsRegistry()
    knowledge_temporal = TemporalKnowledgeView()
    evidence_temporal = TemporalEvidenceView()
    provenance = SourceProvenanceRegistry()
    dependence = SourceDependenceRegistry()
    justifications = KnowledgeJustificationRegistry()
    undercutters = JustificationUndercutterRegistry()
    claim_context = ClaimContextBindingRegistry()
    evidence_context = EvidenceContextBindingRegistry()
    temporal_context = TemporalContext.create(as_of=AS_OF)
    truth_context = TruthContext.create()

    evidence.record(
        TruthEvidence.create(
            evidence_id="support:compat",
            subject_id="claim:compat",
            source_id="source:compat",
            source_family="family:compat",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:compat",
        )
    )
    provenance.register(_source_provenance("source:compat"))
    dependence.register(_source_dependence("source:compat"))
    knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim:compat",
            subject="system",
            relation="works",
            object="yes",
            evidence_ids=("support:compat",),
        )
    )

    v8 = DependenceEpistemicJudge().relation_aware_temporal_scope(
        "claim:compat",
        temporal_context=temporal_context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        source_provenance=provenance,
        source_dependence=dependence,
        justifications=justifications,
        undercutters=undercutters,
    )
    v9 = ContextEpistemicJudge().relation_aware_temporal_scope(
        "claim:compat",
        truth_context=truth_context,
        temporal_context=temporal_context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        source_provenance=provenance,
        source_dependence=dependence,
        justifications=justifications,
        undercutters=undercutters,
        claim_context=claim_context,
        evidence_context=evidence_context,
    )

    assert v9.audit_dependence_scope == v8
    assert v9.lineage_claim_ids == v8.defeasible_scope.lineage_claim_ids
    assert v9.scope_claim_ids == v8.defeasible_scope.scope_claim_ids
    assert v9.evidence_ids == v8.defeasible_scope.evidence_ids
    assert v9.relation_ids == v8.defeasible_scope.relation_ids
    assert v9.source_ids == v8.source_ids
    assert v9.decision_source_ids == v8.decision_source_ids
    assert v9.assessments == v8.defeasible_scope.assessments
    assert v9.justification_statuses == v8.defeasible_scope.justification_statuses
    assert v9.undercutter_statuses == v8.defeasible_scope.undercutter_statuses
    assert v9.contradictions == v8.defeasible_scope.contradictions
    assert v9.debts == v8.defeasible_scope.debts
    assert v9.context_mismatch_claim_ids == ()
    assert v9.context_mismatch_evidence_ids == ()


def test_a15_v9_protocol_domains_are_distinct_from_v8():
    from nolane.external_core import assurance_context_truth, assurance_dependence_truth
    from nolane.external_core import epistemic_context_truth, epistemic_dependence_truth
    from nolane.external_core import verification_context_truth, verification_dependence_truth

    assert epistemic_context_truth.TRUTH_PROTOCOL != epistemic_dependence_truth.TRUTH_PROTOCOL
    assert verification_context_truth.TRUTH_PROTOCOL != verification_dependence_truth.TRUTH_PROTOCOL
    assert assurance_context_truth.TRUTH_PROTOCOL != assurance_dependence_truth.TRUTH_PROTOCOL
