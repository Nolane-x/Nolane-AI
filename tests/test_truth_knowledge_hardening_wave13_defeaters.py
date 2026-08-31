from __future__ import annotations

from nolane.external_core.epistemic_defeasible_truth import (
    DEFEASIBLE_BINDING_MODE,
    DefeasibleEpistemicJudge,
)
from nolane.external_core.epistemic_truth import EpistemicDisposition
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
from nolane.external_core.knowledge_undercutter_truth import (
    JustificationUndercutterRegistry,
    JustificationUndercutterRevision,
)
from nolane.external_core.temporal_truth import TemporalContext
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


def _provenance(source_id: str, controller_id: str) -> SourceProvenanceRevision:
    return SourceProvenanceRevision.create(
        source_id=source_id,
        revision=1,
        predecessor_digest="",
        controller_id=controller_id,
        parent_source_ids=(),
    )


def _record(
    ledger: EvidenceLedger,
    *,
    evidence_id: str,
    subject_id: str,
    source_id: str,
    polarity: EvidencePolarity = EvidencePolarity.SUPPORT,
) -> None:
    ledger.record(
        TruthEvidence.create(
            evidence_id=evidence_id,
            subject_id=subject_id,
            source_id=source_id,
            source_family=f"legacy-family:{source_id}",
            channel=EvidenceChannel.OBSERVATION,
            polarity=polarity,
            payload_digest=f"payload:{evidence_id}",
        )
    )


def _base_state():
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    relation_semantics = RelationSemanticsRegistry()
    knowledge_temporal = TemporalKnowledgeView()
    evidence_temporal = TemporalEvidenceView()
    provenance = SourceProvenanceRegistry()
    justifications = KnowledgeJustificationRegistry()
    undercutters = JustificationUndercutterRegistry()
    context = TemporalContext.create(as_of=AS_OF)

    _record(
        evidence,
        evidence_id="claim-support",
        subject_id="claim-a13",
        source_id="claim-source",
    )
    _record(
        evidence,
        evidence_id="undercutter-support",
        subject_id="u-invalid-method",
        source_id="undercutter-source",
    )
    provenance.register(_provenance("claim-source", "claim-controller"))
    provenance.register(_provenance("undercutter-source", "undercutter-controller"))

    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-a13",
            subject="system",
            relation="is_valid",
            object="yes",
            evidence_ids=("claim-support",),
        )
    )
    return {
        "knowledge": knowledge,
        "evidence": evidence,
        "relation_semantics": relation_semantics,
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
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
    )


def test_a13_supported_undercutter_defeats_exact_legacy_basis():
    state = _base_state()
    legacy = state["justifications"].legacy_basis(state["claim"])
    state["undercutters"].register(
        JustificationUndercutterRevision.create(
            undercutter_id="u-invalid-method",
            claim=state["claim"],
            target_basis=legacy,
            evidence_ids=("undercutter-support",),
        ),
        knowledge=state["knowledge"],
        justifications=state["justifications"],
    )

    scope = _scope(state)

    assert scope.binding_mode == DEFEASIBLE_BINDING_MODE
    assert scope.undercutter_status("u-invalid-method").status == "supported"
    assert scope.justification_status(legacy.justification_id).intrinsic_status == "supported"
    assert scope.justification_status(legacy.justification_id).status == "defeated"
    assert scope.assessment(state["claim"].claim_id).disposition is EpistemicDisposition.UNKNOWN
