from __future__ import annotations

import importlib
import math
from copy import deepcopy

import pytest

from nolane.metadata.component_versions import component_version


def _frontier_module():
    return importlib.import_module("nolane.external_core.reasoning_frontier")


def _control_module():
    return importlib.import_module("nolane.external_core.reasoning_metacontrol")


def _review_module():
    return importlib.import_module("nolane.external_core.reasoning_review")


def _learning_module():
    return importlib.import_module("nolane.external_core.reasoning_meta_learning")


def _frontier(frontier):
    unknown = frontier.DecisionUnknown(
        description="The dependency may have changed semantics after the baseline snapshot.",
        kind=frontier.UnknownKind.REGIME_SHIFT,
        impact=0.9,
        uncertainty=0.8,
        decision_relevance=1.0,
        discovery_path_ids=("research:dependency-changelog", "experiment:dependency-version"),
        could_overturn_decision=True,
    )
    incumbent = frontier.RivalHypothesisRef(
        hypothesis_id="hypothesis:incumbent",
        category=frontier.HypothesisCategory.LOCAL,
        structural_family_id="family:local-implementation",
        prediction_ids=("prediction:local-fix-works",),
        falsifier_ids=("falsifier:clean-env-still-fails",),
        evidence_for_ids=("evidence:local-stack",),
        evidence_against_ids=(),
    )
    challenger = frontier.RivalHypothesisRef(
        hypothesis_id="hypothesis:dependency",
        category=frontier.HypothesisCategory.DEPENDENCY,
        structural_family_id="family:dependency-regime",
        prediction_ids=("prediction:version-pinned-passes",),
        falsifier_ids=("falsifier:all-versions-fail",),
        evidence_for_ids=("evidence:version-drift",),
        evidence_against_ids=(),
    )
    return frontier.ReasoningFrontier(
        reasoning_receipt_id="reasoning-invention:case-1",
        objective_id="objective:repair-regression",
        cognitive_library_digest="library:digest:1",
        unknowns=(unknown,),
        rivals=(incumbent, challenger),
        assumption_ids=("assumption:dependency-compatible",),
        hard_constraint_ids=("constraint:no-production-mutation",),
        branch_budget=4,
    )


def test_reasoning_invention_revision_is_coherent() -> None:
    core = importlib.import_module("nolane.external_core.reasoning_invention")
    evaluation = importlib.import_module("nolane.external_core.reasoning_evaluation")

    assert core.COMPONENT_ID == "external.reasoning_invention"
    assert evaluation.COMPONENT_ID == "external.reasoning_invention"
    assert core.COMPONENT_VERSION == "0.0.2"
    assert evaluation.COMPONENT_VERSION == "0.0.2"
    assert str(component_version("external.reasoning_invention")) == "0.0.2"


def test_frontier_is_bounded_canonical_and_tamper_evident() -> None:
    frontier = _frontier_module()
    row = _frontier(frontier)

    reordered = frontier.ReasoningFrontier(
        reasoning_receipt_id=row.reasoning_receipt_id,
        objective_id=row.objective_id,
        cognitive_library_digest=row.cognitive_library_digest,
        unknowns=tuple(reversed(row.unknowns)),
        rivals=tuple(reversed(row.rivals)),
        assumption_ids=tuple(reversed(row.assumption_ids)),
        hard_constraint_ids=tuple(reversed(row.hard_constraint_ids)),
        branch_budget=row.branch_budget,
    )
    assert reordered.frontier_id == row.frontier_id
    assert reordered.to_state() == row.to_state()
    assert frontier.ReasoningFrontier.from_state(row.to_state()) == row

    tampered = deepcopy(row.to_state())
    tampered["frontier_id"] = "reasoning-frontier:forged"
    with pytest.raises(ValueError, match="identity|canonical"):
        frontier.ReasoningFrontier.from_state(tampered)

    with pytest.raises(ValueError, match="branch budget"):
        frontier.ReasoningFrontier(
            row.reasoning_receipt_id,
            row.objective_id,
            row.cognitive_library_digest,
            row.unknowns,
            row.rivals,
            row.assumption_ids,
            row.hard_constraint_ids,
            8,
        )

    with pytest.raises(ValueError, match="branch budget|rival"):
        frontier.ReasoningFrontier(
            row.reasoning_receipt_id,
            row.objective_id,
            row.cognitive_library_digest,
            row.unknowns,
            row.rivals,
            row.assumption_ids,
            row.hard_constraint_ids,
            1,
        )


def test_frontier_unknown_numeric_validation_fails_closed() -> None:
    frontier = _frontier_module()
    for bad in (True, float("nan"), float("inf"), -0.01, 1.01):
        with pytest.raises((TypeError, ValueError)):
            frontier.DecisionUnknown(
                description="unknown",
                kind=frontier.UnknownKind.UNKNOWN,
                impact=bad,
                uncertainty=0.5,
                decision_relevance=0.5,
                discovery_path_ids=("path:1",),
                could_overturn_decision=True,
            )


def test_assumption_inversion_and_representation_shift_are_frontier_bound() -> None:
    frontier = _frontier_module()
    row = _frontier(frontier)

    inversion = frontier.bind_assumption_inversion(
        row,
        assumption_id="assumption:dependency-compatible",
        inversion_statement="Assume the dependency is not semantically compatible.",
        consequence_ids=("consequence:pin-version",),
        surviving_invariant_ids=("invariant:no-production-mutation",),
        challenger_hypothesis_ids=("hypothesis:dependency",),
    )
    assert inversion.frontier_id == row.frontier_id
    assert frontier.AssumptionInversion.from_state(inversion.to_state()) == inversion

    with pytest.raises(ValueError, match="assumption"):
        frontier.bind_assumption_inversion(
            row,
            assumption_id="assumption:not-in-frontier",
            inversion_statement="invert",
            consequence_ids=("consequence:1",),
            surviving_invariant_ids=("invariant:1",),
            challenger_hypothesis_ids=("hypothesis:1",),
        )

    shift = frontier.bind_representation_shift(
        row,
        source_representation_id="representation:stack-trace",
        target_representation_id="representation:dependency-graph",
        mapping_ids=("mapping:frame-to-package",),
        new_affordance_ids=("affordance:version-cut",),
        lost_information_ids=("loss:temporal-order",),
        challenger_hypothesis_ids=("hypothesis:dependency",),
    )
    assert frontier.RepresentationShift.from_state(shift.to_state()) == shift

    with pytest.raises(ValueError, match="source|target|differ"):
        frontier.bind_representation_shift(
            row,
            source_representation_id="representation:same",
            target_representation_id="representation:same",
            mapping_ids=("mapping:1",),
            new_affordance_ids=("affordance:1",),
            lost_information_ids=(),
            challenger_hypothesis_ids=(),
        )


def test_metacontrol_preserves_tradeoffs_and_is_order_invariant() -> None:
    frontier_mod = _frontier_module()
    control = _control_module()
    row = _frontier(frontier_mod)

    cheap = control.ReasoningActionProposal(
        frontier_id=row.frontier_id,
        kind=control.MetaActionKind.TARGET_UNKNOWN,
        target_ids=(row.unknowns[0].unknown_id,),
        expected_decision_value=0.7,
        expected_information_gain=0.8,
        uncertainty_reduction=0.8,
        estimated_cost=1.0,
        residual_risk=0.4,
        reason="Resolve the decision-overturning dependency regime unknown.",
    )
    deep = control.ReasoningActionProposal(
        frontier_id=row.frontier_id,
        kind=control.MetaActionKind.DESIGN_EXPERIMENT,
        target_ids=("hypothesis:dependency",),
        expected_decision_value=0.9,
        expected_information_gain=0.95,
        uncertainty_reduction=0.9,
        estimated_cost=3.0,
        residual_risk=0.2,
        reason="Run a discriminating version experiment.",
    )
    dominated = control.ReasoningActionProposal(
        frontier_id=row.frontier_id,
        kind=control.MetaActionKind.GENERATE_CHALLENGER,
        target_ids=("hypothesis:incumbent",),
        expected_decision_value=0.5,
        expected_information_gain=0.6,
        uncertainty_reduction=0.5,
        estimated_cost=4.0,
        residual_risk=0.6,
        reason="Generate another local challenger.",
    )

    assert control.dominates_action(deep, dominated)
    assert not control.dominates_action(deep, cheap)
    assert not control.dominates_action(cheap, deep)

    left = control.pareto_action_frontier((cheap, deep, dominated))
    right = control.pareto_action_frontier((dominated, deep, cheap))
    assert tuple(row.action_id for row in left) == tuple(row.action_id for row in right)
    assert {row.action_id for row in left} == {cheap.action_id, deep.action_id}


def test_metacontrol_budget_returns_continue_halt_or_fail_closed_abstain() -> None:
    frontier_mod = _frontier_module()
    control = _control_module()
    row = _frontier(frontier_mod)
    proposal = control.ReasoningActionProposal(
        frontier_id=row.frontier_id,
        kind=control.MetaActionKind.TARGET_UNKNOWN,
        target_ids=(row.unknowns[0].unknown_id,),
        expected_decision_value=0.8,
        expected_information_gain=0.9,
        uncertainty_reduction=0.7,
        estimated_cost=1.0,
        residual_risk=0.3,
        reason="Resolve the highest-impact unknown.",
    )
    budget = control.MetareasoningBudget(
        frontier_id=row.frontier_id,
        remaining_actions=2,
        remaining_cost=2.0,
        minimum_actionable_gain=0.2,
    )
    decision = control.plan_next_reasoning_actions(row, budget, (proposal,))
    assert decision.disposition is control.ControlDisposition.CONTINUE
    assert decision.pareto_action_ids == (proposal.action_id,)
    assert decision.unresolved_overturning_unknown_ids == (row.unknowns[0].unknown_id,)

    exhausted = control.MetareasoningBudget(
        frontier_id=row.frontier_id,
        remaining_actions=0,
        remaining_cost=0.0,
        minimum_actionable_gain=0.2,
    )
    abstain = control.plan_next_reasoning_actions(row, exhausted, (proposal,))
    assert abstain.disposition is control.ControlDisposition.ABSTAIN_UNRESOLVED
    assert not hasattr(abstain, "accepted")
    assert not hasattr(abstain, "promoted")

    safe_unknown = frontier_mod.DecisionUnknown(
        description="Low-impact logging detail.",
        kind=frontier_mod.UnknownKind.MISSING_EVIDENCE,
        impact=0.1,
        uncertainty=0.3,
        decision_relevance=0.1,
        discovery_path_ids=("path:logs",),
        could_overturn_decision=False,
    )
    safe_frontier = frontier_mod.ReasoningFrontier(
        reasoning_receipt_id="reasoning-invention:safe",
        objective_id="objective:safe",
        cognitive_library_digest="library:safe",
        unknowns=(safe_unknown,),
        rivals=(row.rivals[0],),
        assumption_ids=(),
        hard_constraint_ids=(),
        branch_budget=1,
    )
    safe_budget = control.MetareasoningBudget(
        frontier_id=safe_frontier.frontier_id,
        remaining_actions=0,
        remaining_cost=0.0,
        minimum_actionable_gain=0.2,
    )
    halt = control.plan_next_reasoning_actions(safe_frontier, safe_budget, ())
    assert halt.disposition is control.ControlDisposition.HALT_NO_FURTHER_VALUE


def test_metacontrol_rejects_wrong_frontier_and_nonfinite_numeric_inputs() -> None:
    control = _control_module()
    with pytest.raises((TypeError, ValueError)):
        control.ReasoningActionProposal(
            frontier_id="frontier:1",
            kind=control.MetaActionKind.TARGET_UNKNOWN,
            target_ids=("unknown:1",),
            expected_decision_value=math.nan,
            expected_information_gain=0.5,
            uncertainty_reduction=0.5,
            estimated_cost=1.0,
            residual_risk=0.5,
            reason="bad",
        )


def test_fresh_context_review_enforces_information_partition() -> None:
    review = _review_module()
    request = review.FreshContextReviewRequest(
        goal_id="goal:repair",
        candidate_id="candidate:patch",
        producer_agent_id="agent:producer",
        reviewer_agent_id="agent:reviewer",
        producer_session_id="session:producer",
        reviewer_session_id="session:reviewer",
        evidence_packet_ids=("evidence:test", "evidence:trace"),
        review_context_ids=("evidence:test", "evidence:trace", "context:requirements"),
        withheld_rationale_ids=("rationale:producer-chain",),
        required_check_ids=("check:reproduce", "check:counterexample", "check:spec-gaming"),
    )
    assert review.FreshContextReviewRequest.from_state(request.to_state()) == request

    with pytest.raises(ValueError, match="reviewer|producer"):
        review.FreshContextReviewRequest(
            goal_id="goal:repair",
            candidate_id="candidate:patch",
            producer_agent_id="agent:same",
            reviewer_agent_id="agent:same",
            producer_session_id="session:producer",
            reviewer_session_id="session:reviewer",
            evidence_packet_ids=("evidence:test",),
            review_context_ids=("evidence:test",),
            withheld_rationale_ids=("rationale:1",),
            required_check_ids=("check:1",),
        )

    with pytest.raises(ValueError, match="withheld|context|overlap"):
        review.FreshContextReviewRequest(
            goal_id="goal:repair",
            candidate_id="candidate:patch",
            producer_agent_id="agent:producer",
            reviewer_agent_id="agent:reviewer",
            producer_session_id="session:producer",
            reviewer_session_id="session:reviewer",
            evidence_packet_ids=("evidence:test",),
            review_context_ids=("evidence:test", "rationale:1"),
            withheld_rationale_ids=("rationale:1",),
            required_check_ids=("check:1",),
        )


def test_fresh_review_blocks_specification_gaming_and_incomplete_checks() -> None:
    review = _review_module()
    request = review.FreshContextReviewRequest(
        goal_id="goal:repair",
        candidate_id="candidate:patch",
        producer_agent_id="agent:producer",
        reviewer_agent_id="agent:reviewer",
        producer_session_id="session:producer",
        reviewer_session_id="session:reviewer",
        evidence_packet_ids=("evidence:test",),
        review_context_ids=("evidence:test", "context:requirement"),
        withheld_rationale_ids=("rationale:producer",),
        required_check_ids=("check:reproduce", "check:spec-gaming"),
    )
    finding = review.SpecificationGamingFinding(
        requirement_id="requirement:no-regression",
        loophole_id="loophole:disable-test",
        gaming_behavior_id="behavior:skip-suite",
        intent_violation_id="violation:regression-hidden",
        blocking=True,
    )

    with pytest.raises(ValueError, match="supported|gaming|blocking"):
        review.bind_fresh_context_review(
            request,
            verdict=review.FreshReviewVerdict.SUPPORTED_FOR_SCOPE,
            completed_check_ids=request.required_check_ids,
            reproduced_evidence_ids=("evidence:test",),
            objection_ids=(),
            counterexample_ids=(),
            gaming_findings=(finding,),
            reason="would otherwise pass",
        )

    with pytest.raises(ValueError, match="check"):
        review.bind_fresh_context_review(
            request,
            verdict=review.FreshReviewVerdict.ABSTAIN,
            completed_check_ids=("check:reproduce",),
            reproduced_evidence_ids=("evidence:test",),
            objection_ids=(),
            counterexample_ids=(),
            gaming_findings=(),
            reason="missing required check",
        )

    supported = review.bind_fresh_context_review(
        request,
        verdict=review.FreshReviewVerdict.SUPPORTED_FOR_SCOPE,
        completed_check_ids=request.required_check_ids,
        reproduced_evidence_ids=("evidence:test",),
        objection_ids=(),
        counterexample_ids=(),
        gaming_findings=(),
        reason="fresh reviewer reproduced the evidence and found no blocking issue",
    )
    assert review.FreshContextReviewReceipt.from_state(supported.to_state()) == supported
    assert not hasattr(supported, "accepted")
    assert not hasattr(supported, "promoted")


def test_meta_learning_compiles_descriptive_evidence_only() -> None:
    control = _control_module()
    learning = _learning_module()
    first = learning.MetareasoningActionOutcome(
        frontier_id="frontier:1",
        control_decision_id="control:1",
        action_id="action:1",
        action_kind=control.MetaActionKind.TARGET_UNKNOWN,
        evaluation_receipt_id="reasoning-evaluation:1",
        outcome_evidence_ids=("evidence:o1",),
        decision_correct=True,
        observed_information_gain=3.0,
        actual_cost=2.0,
        regression_count=0,
        generalized=True,
        robust=True,
    )
    second = learning.MetareasoningActionOutcome(
        frontier_id="frontier:2",
        control_decision_id="control:2",
        action_id="action:2",
        action_kind=control.MetaActionKind.DESIGN_EXPERIMENT,
        evaluation_receipt_id="reasoning-evaluation:2",
        outcome_evidence_ids=("evidence:o2",),
        decision_correct=False,
        observed_information_gain=1.0,
        actual_cost=2.0,
        regression_count=1,
        generalized=False,
        robust=False,
    )

    left = learning.compile_metareasoning_learning_evidence((first, second))
    right = learning.compile_metareasoning_learning_evidence((second, first))
    assert left.evidence_id == right.evidence_id
    assert left.to_state() == right.to_state()
    assert left.metrics.outcome_count == 2
    assert left.metrics.correct_decision_count == 1
    assert left.metrics.information_efficiency == pytest.approx(1.0)
    assert left.metrics.regression_count == 1
    assert learning.MetareasoningLearningEvidence.from_state(left.to_state()) == left
    assert not hasattr(left, "apply")
    assert not hasattr(left, "update_policy")
    assert not hasattr(left, "promoted")

    with pytest.raises(ValueError, match="at least two"):
        learning.compile_metareasoning_learning_evidence((first,))


def test_new_reasoning_modules_have_no_mutable_authority_backdoor() -> None:
    modules = (_frontier_module(), _control_module(), _review_module(), _learning_module())
    forbidden = (
        "CapabilityAcquisitionGovernor",
        "TransferMetaGovernor",
        "AssuranceControlPlane",
        "register_abstraction(",
        ".promote(",
        ".accept(",
        "neural",
    )
    for module in modules:
        source = __import__("inspect").getsource(module)
        for token in forbidden:
            assert token not in source
