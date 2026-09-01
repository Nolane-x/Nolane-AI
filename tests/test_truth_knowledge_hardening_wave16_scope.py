from __future__ import annotations

import pytest

from nolane.external_core.epistemic_context_truth import ContextEpistemicJudge
from nolane.external_core.epistemic_observation_truth import (
    OBSERVATION_BINDING_MODE,
    ObservationEpistemicJudge,
    ObservationTruthScope,
)
from nolane.external_core.epistemic_truth import EpistemicDisposition
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
from nolane.memory.knowledge import (
    RelationCardinality,
    RelationSemanticsRegistry,
    RelationSemanticsRevision,
)


AS_OF = "2026-09-01T00:00:00Z"


def _state():
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    semantics = RelationSemanticsRegistry()
    semantics.record(
        RelationSemanticsRevision.create(
            relation="healthy",
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
    observation_requirements = ObservationRequirementRegistry()
    observation_results = ObservationResultLedger()

    target_evidence = evidence.record(
        TruthEvidence.create(
            evidence_id="evidence-target",
            subject_id="claim-target",
            source_id="source-target",
            source_family="family:target",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:target",
        )
    )
    provenance.register(
        SourceProvenanceRevision.create(
            source_id="source-target",
            revision=1,
            controller_id="controller-target",
            parent_source_ids=(),
        )
    )
    dependence.register(
        SourceDependenceRevision.create(
            source_id="source-target",
            revision=1,
            basis_ids=("basis:target",),
        )
    )
    target = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-target",
            subject="service",
            relation="healthy",
            object="yes",
            evidence_ids=(target_evidence.evidence_id,),
        )
    )

    unrelated_evidence = evidence.record(
        TruthEvidence.create(
            evidence_id="evidence-unrelated",
            subject_id="claim-unrelated",
            source_id="source-unrelated",
            source_family="family:unrelated",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:unrelated",
        )
    )
    provenance.register(
        SourceProvenanceRevision.create(
            source_id="source-unrelated",
            revision=1,
            controller_id="controller-unrelated",
            parent_source_ids=(),
        )
    )
    dependence.register(
        SourceDependenceRevision.create(
            source_id="source-unrelated",
            revision=1,
            basis_ids=("basis:unrelated",),
        )
    )
    unrelated = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-unrelated",
            subject="other-service",
            relation="healthy",
            object="yes",
            evidence_ids=(unrelated_evidence.evidence_id,),
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
        "claim_context": claim_context,
        "evidence_context": evidence_context,
        "observation_requirements": observation_requirements,
        "observation_results": observation_results,
        "target": target,
        "unrelated": unrelated,
        "target_evidence": target_evidence,
        "unrelated_evidence": unrelated_evidence,
        "truth_context": TruthContext.create(),
        "temporal_context": TemporalContext.create(as_of=AS_OF),
    }


def _v9(state):
    return ContextEpistemicJudge().relation_aware_temporal_scope(
        state["target"].claim_id,
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


def _v10(state):
    return ObservationEpistemicJudge().relation_aware_temporal_scope(
        state["target"].claim_id,
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


def _require_target(state, observation_id: str = "obs.target.001") -> ObservationRequirement:
    requirement = ObservationRequirement.create(
        claim=state["target"],
        observation_id=observation_id,
        channel=EvidenceChannel.OBSERVATION,
    )
    state["observation_requirements"].register(
        ObservationRequirementSetRevision.create(
            claim=state["target"],
            requirements=(requirement,),
        ),
        knowledge=state["knowledge"],
    )
    return requirement


def _validate(state, scope: ObservationTruthScope) -> bool:
    return ObservationEpistemicJudge().validate_scope(
        scope,
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


def test_a16_empty_observation_state_is_exact_v9_compatible():
    state = _state()
    v9 = _v9(state)
    scope = _v10(state)
    assert scope.binding_mode == OBSERVATION_BINDING_MODE
    assert scope.audit_context_scope == v9
    assert scope.assessment(state["target"].claim_id) == v9.assessment(state["target"].claim_id)
    assert scope.observation_debts == ()
    assert scope.incomplete_observation_ids == ()
    assert _validate(state, scope)


def test_a16_unrecorded_required_observation_downgrades_supported_target_to_unknown():
    state = _state()
    requirement = _require_target(state)
    v9 = _v9(state)
    assert v9.assessment(state["target"].claim_id).disposition is EpistemicDisposition.SUPPORTED

    scope = _v10(state)
    assert scope.audit_context_scope == v9
    assert scope.assessment(state["target"].claim_id).disposition is EpistemicDisposition.UNKNOWN
    assert scope.incomplete_observation_ids == (requirement.observation_id,)
    assert scope.unrecorded_observation_ids == (requirement.observation_id,)
    assert any(
        row.claim_id == state["target"].claim_id
        and row.reason == "required_observation_unrecorded"
        and row.critical
        for row in scope.observation_debts
    )


@pytest.mark.parametrize(
    ("outcome", "reason"),
    (
        (ObservationOutcome.MISSING, "required_observation_missing"),
        (ObservationOutcome.CENSORED, "required_observation_censored"),
        (ObservationOutcome.UNAVAILABLE, "required_observation_unavailable"),
        (ObservationOutcome.TIMEOUT, "required_observation_timeout"),
        (ObservationOutcome.INTERFERED, "required_observation_interfered"),
    ),
)
def test_a16_explicit_incomplete_outcomes_remain_unknown_never_refuted(outcome, reason):
    state = _state()
    requirement = _require_target(state)
    state["observation_results"].register(
        ObservationResultRevision.create(
            requirement=requirement,
            outcome=outcome,
            reason=f"reason:{outcome.value}",
        ),
        evidence=state["evidence"],
    )
    scope = _v10(state)
    assert scope.assessment(state["target"].claim_id).disposition is EpistemicDisposition.UNKNOWN
    assert scope.assessment(state["target"].claim_id).disposition is not EpistemicDisposition.REFUTED
    assert any(row.reason == reason for row in scope.observation_debts)


def test_a16_exact_observed_requirement_preserves_supported_target():
    state = _state()
    requirement = _require_target(state)
    state["observation_results"].register(
        ObservationResultRevision.create(
            requirement=requirement,
            outcome=ObservationOutcome.OBSERVED,
            evidence=state["target_evidence"],
        ),
        evidence=state["evidence"],
    )
    scope = _v10(state)
    assert scope.assessment(state["target"].claim_id).disposition is EpistemicDisposition.SUPPORTED
    assert scope.incomplete_observation_ids == ()
    assert scope.observation_debts == ()


def test_a16_relevant_requirement_and_result_revisions_stale_scope_but_unrelated_do_not():
    state = _state()
    target_req = _require_target(state)
    first_result = state["observation_results"].register(
        ObservationResultRevision.create(
            requirement=target_req,
            outcome=ObservationOutcome.TIMEOUT,
            reason="deadline",
        ),
        evidence=state["evidence"],
    )
    scope = _v10(state)
    assert _validate(state, scope)

    unrelated_req = ObservationRequirement.create(
        claim=state["unrelated"],
        observation_id="obs.unrelated.001",
        channel=EvidenceChannel.OBSERVATION,
    )
    state["observation_requirements"].register(
        ObservationRequirementSetRevision.create(
            claim=state["unrelated"],
            requirements=(unrelated_req,),
        ),
        knowledge=state["knowledge"],
    )
    state["observation_results"].register(
        ObservationResultRevision.create(
            requirement=unrelated_req,
            outcome=ObservationOutcome.MISSING,
            reason="unrelated gap",
        ),
        evidence=state["evidence"],
    )
    assert _validate(state, scope)

    state["observation_results"].register(
        ObservationResultRevision.create(
            requirement=target_req,
            revision=2,
            predecessor_digest=first_result.digest,
            outcome=ObservationOutcome.OBSERVED,
            evidence=state["target_evidence"],
        ),
        evidence=state["evidence"],
    )
    assert not _validate(state, scope)

    current_requirements = state["observation_requirements"].current(state["target"].claim_id)
    assert current_requirements is not None
    second_req = ObservationRequirement.create(
        claim=state["target"],
        observation_id="obs.target.002",
        channel=EvidenceChannel.AUDIT,
    )
    refreshed = _v10(state)
    state["observation_requirements"].register(
        ObservationRequirementSetRevision.create(
            claim=state["target"],
            revision=2,
            predecessor_digest=current_requirements.digest,
            requirements=(target_req, second_req),
        ),
        knowledge=state["knowledge"],
    )
    assert not _validate(state, refreshed)


def test_a16_scope_restore_is_strict_and_tamper_evident():
    state = _state()
    _require_target(state)
    scope = _v10(state)
    restored = ObservationTruthScope.from_state(scope.to_state())
    assert restored == scope

    unexpected = scope.to_state()
    unexpected["extra"] = True
    with pytest.raises(ValueError, match="unexpected"):
        ObservationTruthScope.from_state(unexpected)

    tampered = scope.to_state()
    tampered["observation_result_digest"] = "tampered"
    with pytest.raises(ValueError, match="digest"):
        ObservationTruthScope.from_state(tampered)
