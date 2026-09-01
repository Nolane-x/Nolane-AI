from __future__ import annotations

from nolane.external_core.reasoning_metacontrol import MetaActionKind
from nolane.external_core.reasoning_policy_evolution import (
    MetareasoningPolicy,
    PolicyAdoptionReceipt,
    PolicyEvidenceSplit,
    PolicyMetricVector,
    PolicyRevisionProposal,
    evaluate_policy_shadow,
)
from nolane.external_core.reasoning_policy_qualification import (
    COMPONENT_ID,
    COMPONENT_VERSION,
    SCHEMA_VERSION,
    MatchedTrialVerdict,
    PolicyApplicabilityReceipt,
    PolicyApplicabilityVerdict,
    PolicyRegime,
    PolicyRegimeQualification,
    PolicyTrialContext,
    bind_matched_policy_trial,
    evaluate_policy_applicability,
    qualify_policy_regime,
)


def _policies() -> tuple[MetareasoningPolicy, MetareasoningPolicy]:
    kinds = tuple(kind.value for kind in MetaActionKind)
    parent = MetareasoningPolicy(
        revision=1,
        parent_policy_id=None,
        max_remaining_actions=6,
        max_remaining_cost=12.0,
        minimum_actionable_gain_floor=0.10,
        allowed_action_kinds=kinds,
    )
    candidate = MetareasoningPolicy(
        revision=2,
        parent_policy_id=parent.policy_id,
        max_remaining_actions=5,
        max_remaining_cost=10.0,
        minimum_actionable_gain_floor=0.15,
        allowed_action_kinds=kinds[:-1],
    )
    return parent, candidate


def _c10_fixture():
    parent, candidate = _policies()
    split = PolicyEvidenceSplit(
        development_episode_ids=("dev-1", "dev-2"),
        holdout_episode_ids=("holdout-candidate-a", "holdout-candidate-b", "holdout-parent-a", "holdout-parent-b"),
    )
    proposal = PolicyRevisionProposal(
        parent_policy_id=parent.policy_id,
        candidate_policy_id=candidate.policy_id,
        revision=candidate.revision,
        evidence_split=split,
        learning_evidence_ids=("learning-evidence-1",),
        producer_agent_id="producer-agent",
        producer_session_id="producer-session",
        rationale_ids=("rationale-1",),
    )
    aggregate_parent = PolicyMetricVector(
        decision_accuracy=0.70,
        information_gain=0.60,
        uncertainty_reduction=0.55,
        cost=5.0,
        residual_risk=0.25,
        regression_count=1,
    )
    aggregate_candidate = PolicyMetricVector(
        decision_accuracy=0.75,
        information_gain=0.62,
        uncertainty_reduction=0.58,
        cost=4.8,
        residual_risk=0.24,
        regression_count=1,
    )
    shadow = evaluate_policy_shadow(
        proposal,
        parent_metrics=aggregate_parent,
        candidate_metrics=aggregate_candidate,
        holdout_episode_ids=split.holdout_episode_ids,
    )
    adoption = PolicyAdoptionReceipt(
        source_policy_id=parent.policy_id,
        adopted_policy_id=candidate.policy_id,
        proposal_id=proposal.proposal_id,
        shadow_evaluation_id=shadow.evaluation_id,
        review_receipt_id="review-receipt-1",
        authorization_id="external-authorization-1",
    )
    return parent, candidate, proposal, shadow, adoption


def _context(task: str, objective: str, evidence: str, frontier: str, *, world: str = "world-r7") -> PolicyTrialContext:
    return PolicyTrialContext(
        task_id=task,
        objective_id=objective,
        environment_id="env-prod",
        world_revision_id=world,
        ontology_revision_id="ontology-v3",
        evidence_root_id=evidence,
        cognitive_library_digest="library-digest-9",
        action_class_id="reasoning-only",
        initial_frontier_id=frontier,
        context_tag_ids=("bounded", "repository"),
    )


def _regime() -> PolicyRegime:
    return PolicyRegime(
        environment_id="env-prod",
        world_revision_id="world-r7",
        ontology_revision_id="ontology-v3",
        cognitive_library_digest="library-digest-9",
        action_class_id="reasoning-only",
        required_context_tag_ids=("bounded",),
    )


def _metrics(*, accuracy: float, gain: float, uncertainty: float, cost: float, risk: float, regressions: int) -> PolicyMetricVector:
    return PolicyMetricVector(
        decision_accuracy=accuracy,
        information_gain=gain,
        uncertainty_reduction=uncertainty,
        cost=cost,
        residual_risk=risk,
        regression_count=regressions,
    )


def _trials():
    parent, candidate, proposal, shadow, adoption = _c10_fixture()
    trial_a = bind_matched_policy_trial(
        proposal,
        shadow,
        parent_policy=parent,
        candidate_policy=candidate,
        context=_context("task-a", "objective-a", "evidence-a", "frontier-a"),
        parent_episode_id="holdout-parent-a",
        candidate_episode_id="holdout-candidate-a",
        parent_metrics=_metrics(accuracy=0.70, gain=0.60, uncertainty=0.50, cost=5.0, risk=0.25, regressions=1),
        candidate_metrics=_metrics(accuracy=0.76, gain=0.60, uncertainty=0.50, cost=5.0, risk=0.25, regressions=1),
    )
    trial_b = bind_matched_policy_trial(
        proposal,
        shadow,
        parent_policy=parent,
        candidate_policy=candidate,
        context=_context("task-b", "objective-b", "evidence-b", "frontier-b"),
        parent_episode_id="holdout-parent-b",
        candidate_episode_id="holdout-candidate-b",
        parent_metrics=_metrics(accuracy=0.72, gain=0.58, uncertainty=0.52, cost=5.4, risk=0.23, regressions=1),
        candidate_metrics=_metrics(accuracy=0.72, gain=0.61, uncertainty=0.52, cost=5.0, risk=0.23, regressions=1),
    )
    return parent, candidate, proposal, shadow, adoption, trial_a, trial_b


def test_c11_revision_and_schema_are_additive() -> None:
    assert COMPONENT_ID == "external.reasoning_invention"
    assert COMPONENT_VERSION == "0.0.5"
    assert SCHEMA_VERSION == "reasoning-policy-qualification-v1"


def test_matched_trial_derives_effect_and_pareto_verdict() -> None:
    _, _, _, _, _, trial_a, _ = _trials()
    assert trial_a.verdict is MatchedTrialVerdict.PARETO_NON_REGRESSING
    assert trial_a.effect.decision_accuracy_gain > 0.0
    assert trial_a.effect.cost_reduction == 0.0
    assert trial_a.improved_metric_ids == ("decision_accuracy",)
    assert trial_a.regressed_metric_ids == ()


def test_regime_qualification_requires_distinct_matched_tasks_and_no_tail_regression() -> None:
    _, candidate, proposal, shadow, adoption, trial_a, trial_b = _trials()
    qualification = qualify_policy_regime(
        proposal,
        shadow,
        adoption,
        candidate_policy=candidate,
        regime=_regime(),
        trials=(trial_b, trial_a),
    )
    assert qualification.candidate_policy_id == candidate.policy_id
    assert qualification.trial_ids == tuple(sorted((trial_a.trial_id, trial_b.trial_id)))
    assert qualification.distinct_task_ids == ("task-a", "task-b")
    assert qualification.regressed_metric_ids == ()
    assert set(qualification.improved_metric_ids) == {"decision_accuracy", "information_gain", "cost"}


def test_applicability_is_explicit_and_out_of_scope_abstains() -> None:
    _, candidate, proposal, shadow, adoption, trial_a, trial_b = _trials()
    qualification = qualify_policy_regime(
        proposal,
        shadow,
        adoption,
        candidate_policy=candidate,
        regime=_regime(),
        trials=(trial_a, trial_b),
    )
    in_scope = evaluate_policy_applicability(
        qualification,
        _context("task-live", "objective-live", "evidence-live", "frontier-live"),
    )
    assert in_scope.verdict is PolicyApplicabilityVerdict.QUALIFIED_FOR_CONTEXT
    assert in_scope.authority == "qualification_evidence_only"

    out_of_scope = evaluate_policy_applicability(
        qualification,
        _context("task-live", "objective-live", "evidence-live", "frontier-live", world="world-r8"),
    )
    assert out_of_scope.verdict is PolicyApplicabilityVerdict.ABSTAIN_OUT_OF_SCOPE
    assert out_of_scope.policy_id == candidate.policy_id


def test_c11_artifacts_round_trip_canonically() -> None:
    _, candidate, proposal, shadow, adoption, trial_a, trial_b = _trials()
    qualification = qualify_policy_regime(
        proposal,
        shadow,
        adoption,
        candidate_policy=candidate,
        regime=_regime(),
        trials=(trial_a, trial_b),
    )
    receipt = evaluate_policy_applicability(
        qualification,
        _context("task-live", "objective-live", "evidence-live", "frontier-live"),
    )

    assert PolicyTrialContext.from_state(trial_a.context.to_state()) == trial_a.context
    assert PolicyRegime.from_state(qualification.regime.to_state()) == qualification.regime
    assert type(trial_a).from_state(trial_a.to_state()) == trial_a
    assert PolicyRegimeQualification.from_state(qualification.to_state()) == qualification
    assert PolicyApplicabilityReceipt.from_state(receipt.to_state()) == receipt
