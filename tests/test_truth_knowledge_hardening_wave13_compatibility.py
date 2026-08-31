from __future__ import annotations

from nolane.external_core.epistemic_defeasible_truth import DefeasibleEpistemicJudge
from nolane.external_core.epistemic_justification_truth import JustificationEpistemicJudge
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
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


def _record(evidence: EvidenceLedger, *, evidence_id: str, claim_id: str, source_id: str) -> None:
    evidence.record(
        TruthEvidence.create(
            evidence_id=evidence_id,
            subject_id=claim_id,
            source_id=source_id,
            source_family=f"family:{source_id}",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest=f"payload:{evidence_id}",
        )
    )


def _provenance(source_id: str) -> SourceProvenanceRevision:
    return SourceProvenanceRevision.create(
        source_id=source_id,
        revision=1,
        predecessor_digest="",
        controller_id=f"controller:{source_id}",
        parent_source_ids=(),
    )


def test_a13_empty_undercutter_registry_is_semantically_equivalent_to_v6():
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    relation_semantics = RelationSemanticsRegistry()
    knowledge_temporal = TemporalKnowledgeView()
    evidence_temporal = TemporalEvidenceView()
    provenance = SourceProvenanceRegistry()
    justifications = KnowledgeJustificationRegistry()
    undercutters = JustificationUndercutterRegistry()
    context = TemporalContext.create(as_of=AS_OF)

    _record(evidence, evidence_id="parent-support", claim_id="parent", source_id="parent-source")
    _record(evidence, evidence_id="target-support", claim_id="target", source_id="target-source")
    provenance.register(_provenance("parent-source"))
    provenance.register(_provenance("target-source"))

    parent = knowledge.add(
        KnowledgeClaim.create(
            claim_id="parent",
            subject="method",
            relation="is_calibrated",
            object="yes",
            evidence_ids=("parent-support",),
        )
    )
    target = knowledge.add(
        KnowledgeClaim.create(
            claim_id="target",
            subject="system",
            relation="is_valid",
            object="yes",
            evidence_ids=("target-support",),
            parent_claim_ids=(parent.claim_id,),
        )
    )

    v6 = JustificationEpistemicJudge().relation_aware_temporal_scope(
        target.claim_id,
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=relation_semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        source_provenance=provenance,
        justifications=justifications,
    )
    v7 = DefeasibleEpistemicJudge().relation_aware_temporal_scope(
        target.claim_id,
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=relation_semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        source_provenance=provenance,
        justifications=justifications,
        undercutters=undercutters,
    )

    target_legacy = justifications.legacy_basis(target).justification_id
    parent_legacy = justifications.legacy_basis(parent).justification_id

    assert v7.assessment(target.claim_id).disposition is v6.assessment(target.claim_id).disposition
    assert v7.assessment(parent.claim_id).disposition is v6.assessment(parent.claim_id).disposition
    assert v7.justification_status(target_legacy).status == v6.justification_status(target_legacy).status
    assert v7.justification_status(parent_legacy).status == v6.justification_status(parent_legacy).status
    assert v7.lineage_claim_ids == v6.lineage_claim_ids
    assert v7.decision_source_ids == v6.supporting_source_ids
