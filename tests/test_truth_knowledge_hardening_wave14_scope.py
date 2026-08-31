from __future__ import annotations

from nolane.external_core.epistemic_defeasible_truth import DefeasibleEpistemicJudge
from nolane.external_core.epistemic_dependence_truth import (
    DEPENDENCE_BINDING_MODE,
    DependenceEpistemicJudge,
    DependenceTruthScope,
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
from nolane.external_core.knowledge_justification_truth import KnowledgeJustificationRegistry
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger
from nolane.external_core.knowledge_undercutter_truth import JustificationUndercutterRegistry
from nolane.external_core.temporal_truth import TemporalContext
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


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

    evidence.record(
        TruthEvidence.create(
            evidence_id="claim-support",
            subject_id="claim-v8",
            source_id="claim-source",
            source_family="family:claim-source",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:claim-support",
        )
    )
    provenance.register(
        SourceProvenanceRevision.create(
            source_id="claim-source",
            revision=1,
            controller_id="origin-controller",
            parent_source_ids=(),
        )
    )
    dependence.register(
        SourceDependenceRevision.create(
            source_id="claim-source",
            revision=1,
            basis_ids=("basis:claim-measurement",),
        )
    )
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-v8",
            subject="system",
            relation="works",
            object="yes",
            evidence_ids=("claim-support",),
        )
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
        "context": context,
        "claim": claim,
    }


def _scope(state) -> DependenceTruthScope:
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


def _validate(state, scope: DependenceTruthScope) -> bool:
    return DependenceEpistemicJudge().validate_scope(
        scope,
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


def test_a14_scope_wraps_exact_live_v7_scope_without_reimplementing_truth():
    state = _state()
    scope = _scope(state)
    v7 = DefeasibleEpistemicJudge().relation_aware_temporal_scope(
        state["claim"].claim_id,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
    )

    assert scope.binding_mode == DEPENDENCE_BINDING_MODE
    assert scope.defeasible_scope == v7
    assert scope.target_claim_id == v7.target_claim_id
    assert scope.source_ids == v7.source_ids
    assert scope.decision_source_ids == v7.decision_source_ids
    assert _validate(state, scope)


def test_a14_relevant_dependence_revision_stales_scope():
    state = _state()
    scope = _scope(state)
    current = state["dependence"].current("claim-source")
    assert current is not None
    state["dependence"].register(
        SourceDependenceRevision.create(
            source_id="claim-source",
            revision=2,
            predecessor_digest=current.digest,
            basis_ids=("basis:claim-measurement-v2",),
        )
    )
    assert not _validate(state, scope)
    assert _scope(state).digest != scope.digest


def test_a14_unrelated_dependence_revision_does_not_stale_scope():
    state = _state()
    first = state["dependence"].register(
        SourceDependenceRevision.create(
            source_id="unrelated-source",
            revision=1,
            basis_ids=("basis:unrelated",),
        )
    )
    scope = _scope(state)
    state["dependence"].register(
        SourceDependenceRevision.create(
            source_id="unrelated-source",
            revision=2,
            predecessor_digest=first.digest,
            basis_ids=("basis:unrelated-v2",),
        )
    )
    assert _validate(state, scope)
    assert _scope(state) == scope


def test_a14_scope_serialization_is_domain_separated_and_digest_bound():
    state = _state()
    scope = _scope(state)
    restored = DependenceTruthScope.from_state(scope.to_state())
    assert restored == scope

    wrong = dict(scope.to_state())
    wrong["binding_mode"] = "defeasible-justification-provenance-lineage-temporal-v7"
    try:
        DependenceTruthScope.from_state(wrong)
    except ValueError as exc:
        assert "binding mode" in str(exc)
    else:
        raise AssertionError("v7 binding mode must not masquerade as v8")

    tampered = dict(scope.to_state())
    tampered["source_dependence_digest"] = "tampered"
    try:
        DependenceTruthScope.from_state(tampered)
    except ValueError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("tampered dependence scope must fail closed")
