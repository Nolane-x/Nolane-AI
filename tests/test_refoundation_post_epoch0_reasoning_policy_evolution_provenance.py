from __future__ import annotations

import copy

import pytest

from nolane.external_core.reasoning_policy_evolution import (
    MetareasoningPolicy,
    PolicyEvidenceSplit,
    PolicyMetricVector,
    PolicyReviewReceipt,
    PolicyReviewRequest,
    PolicyReviewVerdict,
    bind_policy_review,
    evaluate_policy_shadow,
    propose_policy_revision,
)


def _artifacts():
    parent = MetareasoningPolicy(
        revision=1,
        parent_policy_id=None,
        max_remaining_actions=5,
        max_remaining_cost=12.0,
        minimum_actionable_gain_floor=0.15,
        allowed_action_kinds=("target_unknown", "design_experiment", "fresh_context_review"),
    )
    candidate = MetareasoningPolicy(
        revision=2,
        parent_policy_id=parent.policy_id,
        max_remaining_actions=3,
        max_remaining_cost=8.0,
        minimum_actionable_gain_floor=0.25,
        allowed_action_kinds=("target_unknown", "fresh_context_review"),
    )
    split = PolicyEvidenceSplit(
        development_episode_ids=("dev:1", "dev:2"),
        holdout_episode_ids=("hold:1", "hold:2"),
    )
    proposal = propose_policy_revision(
        parent,
        candidate,
        evidence_split=split,
        learning_evidence_ids=("learning:1",),
        producer_agent_id="producer",
        producer_session_id="producer-session",
        rationale_ids=("rationale:1",),
    )
    shadow = evaluate_policy_shadow(
        proposal,
        parent_metrics=PolicyMetricVector(0.70, 0.50, 0.40, 5.0, 0.30, 1),
        candidate_metrics=PolicyMetricVector(0.80, 0.60, 0.50, 4.0, 0.20, 0),
        holdout_episode_ids=split.holdout_episode_ids,
    )
    request = PolicyReviewRequest(
        proposal_id=proposal.proposal_id,
        shadow_evaluation_id=shadow.evaluation_id,
        producer_agent_id="producer",
        reviewer_agent_id="independent-reviewer",
        producer_session_id="producer-session",
        reviewer_session_id="independent-reviewer-session",
        evidence_packet_ids=(proposal.proposal_id, shadow.evaluation_id),
        review_context_ids=(proposal.proposal_id, shadow.evaluation_id, "contract:C10"),
        withheld_rationale_ids=("rationale:1",),
        required_check_ids=("check:authority", "check:gaming", "check:leakage"),
    )
    receipt = bind_policy_review(
        request,
        verdict=PolicyReviewVerdict.SUPPORTED_FOR_ADOPTION,
        completed_check_ids=request.required_check_ids,
        reproduced_evidence_ids=request.evidence_packet_ids,
        reason="independent reviewer reproduced the bounded holdout evidence",
    )
    return request, receipt


def test_review_receipt_is_self_contained_fresh_context_provenance() -> None:
    request, receipt = _artifacts()

    assert receipt.request_id == request.request_id
    assert receipt.producer_agent_id == request.producer_agent_id
    assert receipt.reviewer_agent_id == request.reviewer_agent_id
    assert receipt.producer_session_id == request.producer_session_id
    assert receipt.reviewer_session_id == request.reviewer_session_id
    assert receipt.evidence_packet_ids == request.evidence_packet_ids
    assert receipt.review_context_ids == request.review_context_ids
    assert receipt.withheld_rationale_ids == request.withheld_rationale_ids
    assert receipt.required_check_ids == request.required_check_ids
    assert PolicyReviewReceipt.from_state(receipt.to_state()) == receipt


def test_review_receipt_provenance_tampering_breaks_canonical_identity() -> None:
    _, receipt = _artifacts()
    state = copy.deepcopy(receipt.to_state())
    state["producer_agent_id"] = "different-producer"

    with pytest.raises(ValueError, match="identity"):
        PolicyReviewReceipt.from_state(state)


def test_supported_receipt_cannot_exist_without_fresh_context_provenance() -> None:
    with pytest.raises(ValueError, match="fresh-context"):
        PolicyReviewReceipt(
            proposal_id="proposal:1",
            shadow_evaluation_id="shadow:1",
            reviewer_agent_id="reviewer",
            reviewer_session_id="reviewer-session",
            verdict=PolicyReviewVerdict.SUPPORTED_FOR_ADOPTION,
            completed_check_ids=("check:1",),
            reproduced_evidence_ids=("proposal:1", "shadow:1"),
            objection_ids=(),
            gaming_finding_ids=(),
            leakage_finding_ids=(),
            reason="missing request provenance",
        )
