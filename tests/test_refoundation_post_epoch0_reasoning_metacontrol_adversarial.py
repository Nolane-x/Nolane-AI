from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.external_core import reasoning_frontier as frontier
from nolane.external_core import reasoning_meta_learning as learning
from nolane.external_core import reasoning_metacontrol as control
from nolane.external_core import reasoning_review as review


def _unknown(*, overturning: bool = True) -> frontier.DecisionUnknown:
    return frontier.DecisionUnknown(
        description="A dependency regime may invalidate the incumbent explanation.",
        kind=frontier.UnknownKind.REGIME_SHIFT,
        impact=0.9,
        uncertainty=0.8,
        decision_relevance=0.9,
        discovery_path_ids=("path:changelog",),
        could_overturn_decision=overturning,
    )


def _rival(hypothesis_id: str, family: str) -> frontier.RivalHypothesisRef:
    return frontier.RivalHypothesisRef(
        hypothesis_id=hypothesis_id,
        category=frontier.HypothesisCategory.DEPENDENCY,
        structural_family_id=family,
        prediction_ids=(f"prediction:{family}",),
        falsifier_ids=(f"falsifier:{family}",),
    )


def _frontier(receipt_id: str = "reasoning-invention:a") -> frontier.ReasoningFrontier:
    return frontier.ReasoningFrontier(
        reasoning_receipt_id=receipt_id,
        objective_id="objective:repair",
        cognitive_library_digest="library:digest",
        unknowns=(_unknown(),),
        rivals=(_rival("hypothesis:a", "family:a"),),
        assumption_ids=("assumption:a",),
        hard_constraint_ids=("constraint:a",),
        branch_budget=3,
    )


def _proposal(row: frontier.ReasoningFrontier) -> control.ReasoningActionProposal:
    return control.ReasoningActionProposal(
        frontier_id=row.frontier_id,
        kind=control.MetaActionKind.TARGET_UNKNOWN,
        target_ids=(row.unknowns[0].unknown_id,),
        expected_decision_value=0.8,
        expected_information_gain=0.8,
        uncertainty_reduction=0.7,
        estimated_cost=1.0,
        residual_risk=0.2,
        reason="Resolve the overturning unknown.",
    )


def _review_request() -> review.FreshContextReviewRequest:
    return review.FreshContextReviewRequest(
        goal_id="goal:repair",
        candidate_id="candidate:patch",
        producer_agent_id="agent:producer",
        reviewer_agent_id="agent:reviewer",
        producer_session_id="session:producer",
        reviewer_session_id="session:reviewer",
        evidence_packet_ids=("evidence:test",),
        review_context_ids=("evidence:test", "context:requirements"),
        withheld_rationale_ids=("rationale:producer",),
        required_check_ids=("check:reproduce", "check:counterexample"),
    )


def _outcome(action_id: str, receipt_id: str) -> learning.MetareasoningActionOutcome:
    return learning.MetareasoningActionOutcome(
        frontier_id="frontier:learning",
        control_decision_id=f"control:{action_id}",
        action_id=action_id,
        action_kind=control.MetaActionKind.DESIGN_EXPERIMENT,
        evaluation_receipt_id=receipt_id,
        outcome_evidence_ids=(f"evidence:{action_id}",),
        decision_correct=True,
        observed_information_gain=1.0,
        actual_cost=1.0,
        regression_count=0,
        generalized=True,
        robust=True,
    )


def test_frontier_rejects_duplicate_hypothesis_identity_even_if_rival_content_differs() -> None:
    first = _rival("hypothesis:same", "family:a")
    second = _rival("hypothesis:same", "family:b")
    assert first.rival_id != second.rival_id

    with pytest.raises(ValueError, match="unique hypothesis"):
        frontier.ReasoningFrontier(
            reasoning_receipt_id="reasoning-invention:duplicate",
            objective_id="objective:duplicate",
            cognitive_library_digest="library:duplicate",
            unknowns=(_unknown(),),
            rivals=(first, second),
            assumption_ids=(),
            hard_constraint_ids=(),
            branch_budget=2,
        )


def test_metacontrol_rejects_cross_frontier_budget_and_proposal() -> None:
    left = _frontier("reasoning-invention:left")
    right = _frontier("reasoning-invention:right")
    proposal = _proposal(left)

    wrong_budget = control.MetareasoningBudget(
        frontier_id=right.frontier_id,
        remaining_actions=1,
        remaining_cost=2.0,
        minimum_actionable_gain=0.1,
    )
    with pytest.raises(ValueError, match="wrong frontier"):
        control.plan_next_reasoning_actions(left, wrong_budget, (proposal,))

    correct_budget = control.MetareasoningBudget(
        frontier_id=left.frontier_id,
        remaining_actions=1,
        remaining_cost=2.0,
        minimum_actionable_gain=0.1,
    )
    wrong_proposal = _proposal(right)
    with pytest.raises(ValueError, match="wrong frontier"):
        control.plan_next_reasoning_actions(left, correct_budget, (wrong_proposal,))


def test_metacontrol_rejects_bool_smuggling_and_forged_action_identity() -> None:
    row = _frontier()
    with pytest.raises(TypeError):
        control.MetareasoningBudget(
            frontier_id=row.frontier_id,
            remaining_actions=True,
            remaining_cost=1.0,
            minimum_actionable_gain=0.1,
        )
    with pytest.raises(TypeError):
        control.MetareasoningBudget(
            frontier_id=row.frontier_id,
            remaining_actions=1,
            remaining_cost=True,
            minimum_actionable_gain=0.1,
        )

    proposal = _proposal(row)
    forged = deepcopy(proposal.to_state())
    forged["action_id"] = "reasoning-action:forged"
    with pytest.raises(ValueError, match="identity|canonical"):
        control.ReasoningActionProposal.from_state(forged)


def test_fresh_context_rejects_same_session_and_missing_evidence_context() -> None:
    with pytest.raises(ValueError, match="session"):
        review.FreshContextReviewRequest(
            goal_id="goal:repair",
            candidate_id="candidate:patch",
            producer_agent_id="agent:producer",
            reviewer_agent_id="agent:reviewer",
            producer_session_id="session:same",
            reviewer_session_id="session:same",
            evidence_packet_ids=("evidence:test",),
            review_context_ids=("evidence:test",),
            withheld_rationale_ids=("rationale:producer",),
            required_check_ids=("check:reproduce",),
        )

    with pytest.raises(ValueError, match="evidence packet"):
        review.FreshContextReviewRequest(
            goal_id="goal:repair",
            candidate_id="candidate:patch",
            producer_agent_id="agent:producer",
            reviewer_agent_id="agent:reviewer",
            producer_session_id="session:producer",
            reviewer_session_id="session:reviewer",
            evidence_packet_ids=("evidence:hidden",),
            review_context_ids=("context:requirements",),
            withheld_rationale_ids=("rationale:producer",),
            required_check_ids=("check:reproduce",),
        )


def test_supported_review_rejects_objections_and_counterexamples() -> None:
    request = _review_request()
    for objections, counterexamples in (
        (("objection:1",), ()),
        ((), ("counterexample:1",)),
    ):
        with pytest.raises(ValueError, match="supported"):
            review.bind_fresh_context_review(
                request,
                verdict=review.FreshReviewVerdict.SUPPORTED_FOR_SCOPE,
                completed_check_ids=request.required_check_ids,
                reproduced_evidence_ids=request.evidence_packet_ids,
                objection_ids=objections,
                counterexample_ids=counterexamples,
                gaming_findings=(),
                reason="attempted false support",
            )


def test_review_and_learning_restore_reject_forged_derived_identities() -> None:
    request = _review_request()
    receipt = review.bind_fresh_context_review(
        request,
        verdict=review.FreshReviewVerdict.SUPPORTED_FOR_SCOPE,
        completed_check_ids=request.required_check_ids,
        reproduced_evidence_ids=request.evidence_packet_ids,
        reason="fresh reviewer reproduced the bounded evidence",
    )
    forged_receipt = deepcopy(receipt.to_state())
    forged_receipt["receipt_id"] = "fresh-context-review:forged"
    with pytest.raises(ValueError, match="identity|canonical"):
        review.FreshContextReviewReceipt.from_state(forged_receipt)

    first = _outcome("action:a", "reasoning-evaluation:a")
    second = _outcome("action:b", "reasoning-evaluation:b")
    evidence = learning.compile_metareasoning_learning_evidence((first, second))
    forged_evidence = deepcopy(evidence.to_state())
    forged_evidence["evidence_id"] = "metareasoning-learning:forged"
    with pytest.raises(ValueError, match="identity|canonical"):
        learning.MetareasoningLearningEvidence.from_state(forged_evidence)


def test_meta_learning_rejects_duplicate_outcomes_and_bool_numeric_fields() -> None:
    first = _outcome("action:a", "reasoning-evaluation:a")
    with pytest.raises(ValueError, match="distinct"):
        learning.compile_metareasoning_learning_evidence((first, first))

    with pytest.raises(TypeError):
        learning.MetareasoningActionOutcome(
            frontier_id="frontier:learning",
            control_decision_id="control:bad",
            action_id="action:bad",
            action_kind=control.MetaActionKind.DESIGN_EXPERIMENT,
            evaluation_receipt_id="reasoning-evaluation:bad",
            outcome_evidence_ids=("evidence:bad",),
            decision_correct=True,
            observed_information_gain=1.0,
            actual_cost=True,
            regression_count=0,
            generalized=True,
            robust=True,
        )
