from __future__ import annotations

from nolane.external_core.epistemic_context_truth import (
    CONTEXT_BINDING_MODE,
    ContextEpistemicJudge,
)
from nolane.external_core.epistemic_truth import EpistemicDisposition
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
from nolane.memory.knowledge import (
    RelationCardinality,
    RelationSemanticsRegistry,
    RelationSemanticsRevision,
)


AS_OF = "2026-08-31T00:00:00Z"


def _state(*, eu_claim_context: str = "eu", us_evidence_context: str = "us"):
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    semantics = RelationSemanticsRegistry()
    semantics.record(
        RelationSemanticsRevision.create(
            relation="permits",
            revision=1,
            cardinality=RelationCardinality.EXCLUSIVE,
        )
    )
    knowledge_temporal = TemporalKnowledgeView()
    evidence_temporal = TemporalEvidenceView()
    provenance = SourceProvenanceRegistry()
    dependence = SourceDependenceRegistry()
    justifications = KnowledgeJustificationRegistry()
    undercutters = JustificationUndercutterRegistry()
    claim_context = ClaimContextBindingRegistry()
    evidence_context = EvidenceContextBindingRegistry()

    claims = {}
    for region, object_value in (("us", "yes"), ("eu", "no")):
        evidence_id = f"evidence-{region}"
        source_id = f"source-{region}"
        item = evidence.record(
            TruthEvidence.create(
                evidence_id=evidence_id,
                subject_id=f"claim-{region}",
                source_id=source_id,
                source_family=f"family:{source_id}",
                channel=EvidenceChannel.OBSERVATION,
                polarity=EvidencePolarity.SUPPORT,
                payload_digest=f"payload:{evidence_id}",
            )
        )
        provenance.register(
            SourceProvenanceRevision.create(
                source_id=source_id,
                revision=1,
                controller_id=f"controller-{region}",
                parent_source_ids=(),
            )
        )
        dependence.register(
            SourceDependenceRevision.create(
                source_id=source_id,
                revision=1,
                basis_ids=(f"basis:{region}",),
            )
        )
        claim = knowledge.add(
            KnowledgeClaim.create(
                claim_id=f"claim-{region}",
                subject="policy",
                relation="permits",
                object=object_value,
                evidence_ids=(evidence_id,),
            )
        )
        claims[region] = claim

    claim_context.register(
        ClaimContextBindingRevision.create(
            claim=claims["us"],
            revision=1,
            qualifiers=(("jurisdiction", "us"),),
        ),
        knowledge=knowledge,
    )
    claim_context.register(
        ClaimContextBindingRevision.create(
            claim=claims["eu"],
            revision=1,
            qualifiers=(("jurisdiction", eu_claim_context),),
        ),
        knowledge=knowledge,
    )
    evidence_context.register(
        EvidenceContextBindingRevision.create(
            evidence=evidence.get("evidence-us"),
            revision=1,
            qualifiers=(("jurisdiction", us_evidence_context),),
        ),
        evidence=evidence,
    )
    evidence_context.register(
        EvidenceContextBindingRevision.create(
            evidence=evidence.get("evidence-eu"),
            revision=1,
            qualifiers=(("jurisdiction", eu_claim_context),),
        ),
        evidence=evidence,
    )

    return {
        "knowledge": knowledge,
        "evidence": evidence,
        "semantics": semantics,
        "knowledge_temporal": knowledge_temporal,
        "evidence_temporal": evidence_temporal,
        "provenance": provenance,
        "dependence": dependence,
        "justifications": justifications,
        "undercutters": undercutters,
        "claim_context": claim_context,
        "evidence_context": evidence_context,
        "claims": claims,
        "temporal_context": TemporalContext.create(as_of=AS_OF),
    }


def _scope(state, truth_context: TruthContext):
    return ContextEpistemicJudge().relation_aware_temporal_scope(
        state["claims"]["us"].claim_id,
        truth_context=truth_context,
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


def test_a15_disjoint_context_exclusive_competitor_does_not_contradict():
    state = _state(eu_claim_context="eu")
    scope = _scope(
        state,
        TruthContext.create(qualifiers=(("jurisdiction", "us"),)),
    )
    assert scope.binding_mode == CONTEXT_BINDING_MODE
    assert scope.assessment("claim-us").disposition is EpistemicDisposition.SUPPORTED
    assert scope.contradictions == ()
    assert "claim-eu" not in scope.scope_claim_ids


def test_a15_same_context_exclusive_competitors_still_contradict():
    state = _state(eu_claim_context="us")
    scope = _scope(
        state,
        TruthContext.create(qualifiers=(("jurisdiction", "us"),)),
    )
    assert {row.claim_id for row in scope.assessments} == {"claim-us", "claim-eu"}
    assert len(scope.contradictions) == 1
    assert set(scope.contradictions[0].claim_ids) == {"claim-us", "claim-eu"}


def test_a15_missing_target_qualifier_is_unknown_and_explicitly_mismatched():
    state = _state()
    scope = _scope(state, TruthContext.create())
    assert scope.assessment("claim-us").disposition is EpistemicDisposition.UNKNOWN
    assert scope.context_mismatch_claim_ids == ("claim-us",)
    assert scope.context_mismatch_evidence_ids == ()


def test_a15_context_mismatched_evidence_cannot_support_target():
    state = _state(us_evidence_context="eu")
    scope = _scope(
        state,
        TruthContext.create(qualifiers=(("jurisdiction", "us"),)),
    )
    assert scope.assessment("claim-us").disposition is EpistemicDisposition.UNKNOWN
    assert scope.context_mismatch_evidence_ids == ("evidence-us",)
