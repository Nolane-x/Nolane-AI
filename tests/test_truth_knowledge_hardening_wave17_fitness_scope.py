from __future__ import annotations

import pytest

from nolane.external_core.epistemic_observation_fitness_truth import (
    FITNESS_BINDING_MODE,
    ObservationFitnessEpistemicJudge,
)
from nolane.external_core.epistemic_observation_truth import ObservationEpistemicJudge
from nolane.external_core.epistemic_truth import EpistemicDisposition
from nolane.external_core.evidence_context_truth import EvidenceContextBindingRegistry
from nolane.external_core.evidence_dependence_truth import SourceDependenceRegistry, SourceDependenceRevision
from nolane.external_core.evidence_observation_fitness_truth import (
    FitnessCheckAssessment,
    FitnessCheckStatus,
    ObservationFitnessAssessmentLedger,
    ObservationFitnessAssessmentRevision,
)
from nolane.external_core.evidence_observation_truth import (
    ObservationOutcome,
    ObservationResultLedger,
    ObservationResultRevision,
)
from nolane.external_core.evidence_provenance_truth import SourceProvenanceRegistry, SourceProvenanceRevision
from nolane.external_core.evidence_temporal_truth import TemporalEvidenceView
from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_context_truth import ClaimContextBindingRegistry, TruthContext
from nolane.external_core.knowledge_justification_truth import KnowledgeJustificationRegistry
from nolane.external_core.knowledge_observation_fitness_truth import (
    FitnessCheck,
    ObservationFitnessRequirementRegistry,
    ObservationFitnessRequirementRevision,
)
from nolane.external_core.knowledge_observation_truth import (
    ObservationRequirement,
    ObservationRequirementRegistry,
    ObservationRequirementSetRevision,
)
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger
from nolane.external_core.knowledge_undercutter_truth import JustificationUndercutterRegistry
from nolane.external_core.temporal_truth import TemporalContext
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-09-01T00:00:00Z"


def _state(*, constrained: bool = True):
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    provenance = SourceProvenanceRegistry()
    dependence = SourceDependenceRegistry()

    support = evidence.record(
        TruthEvidence.create(
            evidence_id="evidence:target-v11",
            subject_id="claim:target-v11",
            source_id="source:target-v11",
            source_family="family:target-v11",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:target-v11",
        )
    )
    provenance.register(
        SourceProvenanceRevision.create(
            source_id=support.source_id,
            revision=1,
            controller_id="controller:target-v11",
            parent_source_ids=(),
        )
    )
    dependence.register(
        SourceDependenceRevision.create(
            source_id=support.source_id,
            revision=1,
            basis_ids=("basis:target-v11",),
        )
    )
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim:target-v11",
            subject="service",
            relation="healthy",
            object="yes",
            evidence_ids=(support.evidence_id,),
        )
    )

    basis = evidence.record(
        TruthEvidence.create(
            evidence_id="evidence:fitness-basis-v11",
            subject_id="sensor:target-v11",
            source_id="source:calibration-v11",
            source_family="family:calibration-v11",
            channel=EvidenceChannel.AUDIT,
            polarity=EvidencePolarity.NEUTRAL,
            payload_digest="payload:calibration-v11",
        )
    )

    observation_requirements = ObservationRequirementRegistry()
    observation = ObservationRequirement.create(
        claim=claim,
        observation_id="observation:target-v11",
        channel=EvidenceChannel.OBSERVATION,
    )
    observation_requirements.register(
        ObservationRequirementSetRevision.create(
            claim=claim,
            requirements=(observation,),
        ),
        knowledge=knowledge,
    )
    observation_results = ObservationResultLedger()
    observed = observation_results.register(
        ObservationResultRevision.create(
            requirement=observation,
            outcome=ObservationOutcome.OBSERVED,
            evidence=support,
        ),
        evidence=evidence,
    )

    fitness_requirements = ObservationFitnessRequirementRegistry()
    fitness_requirement = None
    if constrained:
        fitness_requirement = fitness_requirements.register(
            ObservationFitnessRequirementRevision.create(
                observation_requirement=observation,
                checks=(FitnessCheck.CALIBRATION, FitnessCheck.INTEGRITY),
            ),
            observation_requirements=observation_requirements,
        )

    return {
        "knowledge": knowledge,
        "evidence": evidence,
        "provenance": provenance,
        "dependence": dependence,
        "claim": claim,
        "support": support,
        "basis": basis,
        "semantics": RelationSemanticsRegistry(),
        "knowledge_temporal": TemporalKnowledgeView(),
        "evidence_temporal": TemporalEvidenceView(),
        "justifications": KnowledgeJustificationRegistry(),
        "undercutters": JustificationUndercutterRegistry(),
        "claim_context": ClaimContextBindingRegistry(),
        "evidence_context": EvidenceContextBindingRegistry(),
        "observation_requirements": observation_requirements,
        "observation_results": observation_results,
        "observation": observation,
        "observed": observed,
        "fitness_requirements": fitness_requirements,
        "fitness_requirement": fitness_requirement,
        "fitness_assessments": ObservationFitnessAssessmentLedger(),
        "truth_context": TruthContext.create(),
        "temporal_context": TemporalContext.create(as_of=AS_OF),
    }


def _kwargs(state):
    return dict(
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


def _v11(state):
    return ObservationFitnessEpistemicJudge().relation_aware_temporal_scope(
        state["claim"].claim_id,
        **_kwargs(state),
        fitness_requirements=state["fitness_requirements"],
        fitness_assessments=state["fitness_assessments"],
    )


def _assessment(state, *, calibration=FitnessCheckStatus.PASS, integrity=FitnessCheckStatus.PASS, revision=1, predecessor_digest="", reason=""):
    return ObservationFitnessAssessmentRevision.create(
        fitness_requirement=state["fitness_requirement"],
        observation_result=state["observed"],
        revision=revision,
        predecessor_digest=predecessor_digest,
        checks=(
            FitnessCheckAssessment.create(check=FitnessCheck.CALIBRATION, status=calibration),
            FitnessCheckAssessment.create(check=FitnessCheck.INTEGRITY, status=integrity),
        ),
        basis_evidence_ids=(state["basis"].evidence_id,),
        reason=reason,
    )


def test_a17_empty_fitness_state_preserves_exact_v10_epistemic_semantics():
    state = _state(constrained=False)
    v10 = ObservationEpistemicJudge().relation_aware_temporal_scope(
        state["claim"].claim_id,
        **_kwargs(state),
    )
    v11 = _v11(state)
    assert v11.audit_observation_scope == v10
    assert v11.assessment(state["claim"].claim_id) == v10.assessment(state["claim"].claim_id)
    assert not v11.fitness_debts
    assert v11.binding_mode == FITNESS_BINDING_MODE


def test_a17_observed_but_unassessed_required_fitness_becomes_unknown_not_refuted():
    state = _state()
    scope = _v11(state)
    target = scope.assessment(state["claim"].claim_id)
    assert target.disposition is EpistemicDisposition.UNKNOWN
    assert state["observation"].observation_id in scope.unassessed_fitness_observation_ids
    assert scope.failed_fitness_observation_ids == ()
    assert state["evidence"].is_active(state["support"].evidence_id)
    assert state["support"].polarity is EvidencePolarity.SUPPORT


def test_a17_all_required_fitness_checks_pass_preserves_v10_support():
    state = _state()
    row = _assessment(state)
    state["fitness_assessments"].register(
        row,
        evidence=state["evidence"],
        fitness_requirements=state["fitness_requirements"],
        observation_results=state["observation_results"],
    )
    scope = _v11(state)
    assert scope.assessment(state["claim"].claim_id).disposition is EpistemicDisposition.SUPPORTED
    assert scope.unfit_fitness_observation_ids == ()
    assert scope.fitness_debts == ()


def test_a17_failed_fitness_revision_downgrades_support_to_unknown_without_mutating_evidence():
    state = _state()
    passed = _assessment(state)
    state["fitness_assessments"].register(
        passed,
        evidence=state["evidence"],
        fitness_requirements=state["fitness_requirements"],
        observation_results=state["observation_results"],
    )
    failed = _assessment(
        state,
        calibration=FitnessCheckStatus.FAIL,
        revision=2,
        predecessor_digest=passed.digest,
        reason="calibration_out_of_tolerance",
    )
    state["fitness_assessments"].register(
        failed,
        evidence=state["evidence"],
        fitness_requirements=state["fitness_requirements"],
        observation_results=state["observation_results"],
    )
    scope = _v11(state)
    assert scope.assessment(state["claim"].claim_id).disposition is EpistemicDisposition.UNKNOWN
    assert state["observation"].observation_id in scope.failed_fitness_observation_ids
    assert state["evidence"].is_active(state["support"].evidence_id)
    assert state["support"].polarity is EvidencePolarity.SUPPORT


def test_a17_target_observation_evidence_cannot_self_certify_fitness():
    state = _state()
    with pytest.raises(ValueError, match="self-certify"):
        ObservationFitnessAssessmentRevision.create(
            fitness_requirement=state["fitness_requirement"],
            observation_result=state["observed"],
            checks=(
                FitnessCheckAssessment.create(check=FitnessCheck.CALIBRATION, status=FitnessCheckStatus.PASS),
                FitnessCheckAssessment.create(check=FitnessCheck.INTEGRITY, status=FitnessCheckStatus.PASS),
            ),
            basis_evidence_ids=(state["support"].evidence_id,),
        )
