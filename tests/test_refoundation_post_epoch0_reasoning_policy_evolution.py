from __future__ import annotations

import pytest

from nolane.external_core.reasoning_metacontrol import MetareasoningBudget
from nolane.external_core.reasoning_policy_evolution import (
    COMPONENT_VERSION,
    ExternalPolicyAuthorization,
    MetareasoningPolicy,
    PolicyEvidenceSplit,
    PolicyMetricVector,
    PolicyOperation,
    PolicyReviewRequest,
    PolicyReviewVerdict,
    PolicyShadowVerdict,
    apply_authorized_policy_revision,
    bind_policy_review,
    constrain_metareasoning_budget,
    evaluate_policy_shadow,
    propose_policy_revision,
    rollback_policy_revision,
)


def _root() -> MetareasoningPolicy:
    return MetareasoningPolicy(
        revision=1,
        parent_policy_id=None,
        max_remaining_actions=5,
        max_remaining_cost=12.0,
        minimum_actionable_gain_floor=0.15,
        allowed_action_kinds=(
            "target_unknown",
            "generate_challenger",
            "design_experiment",
            "fresh_context_review",
        ),
    )


def _candidate(parent: MetareasoningPolicy) -> MetareasoningPolicy:
    return MetareasoningPolicy(
        revision=2,
        parent_policy_id=parent.policy_id,
        max_remaining_actions=3,
        max_remaining_cost=8.0,
        minimum_actionable_gain_floor=0.25,
        allowed_action_kinds=("target_unknown", "design_experiment", "fresh_context_review"),
    )


def _split() -> PolicyEvidenceSplit:
    return PolicyEvidenceSplit(
        development_episode_ids=("episode:dev-1", "episode:dev-2"),
        holdout_episode_ids=("episode:hold-1", "episode:hold-2"),
    )


def _proposal(parent: MetareasoningPolicy, candidate: MetareasoningPolicy):
    return propose_policy_revision(
        parent,
        candidate,
        evidence_split=_split(),
        learning_evidence_ids=("learning:1", "learning:2"),
        producer_agent_id="reasoner:producer",
        producer_session_id="session:producer",
        rationale_ids=("rationale:policy-delta",),
    )


def _supported_shadow(proposal):
    parent_metrics = PolicyMetricVector(
        decision_accuracy=0.80,
        information_gain=0.55,
        uncertainty_reduction=0.50,
        cost=6.0,
        residual_risk=0.20,
        regression_count=1,
    )
    candidate_metrics = PolicyMetricVector(
        decision_accuracy=0.85,
        information_gain=0.60,
        uncertainty_reduction=0.55,
        cost=5.0,
        residual_risk=0.18,
        regression_count=0,
    )
    return evaluate_policy_shadow(
        proposal,
        parent_metrics=parent_metrics,
        candidate_metrics=candidate_metrics,
        holdout_episode_ids=_split().holdout_episode_ids,
    )


def _supported_review(proposal, shadow):
    request = PolicyReviewRequest(
        proposal_id=proposal.proposal_id,
        shadow_evaluation_id=shadow.evaluation_id,
        producer_agent_id=proposal.producer_agent_id,
        reviewer_agent_id="reasoner:independent-reviewer",
        producer_session_id=proposal.producer_session_id,
        reviewer_session_id="session:independent-reviewer",
        evidence_packet_ids=(proposal.proposal_id, shadow.evaluation_id, "learning:1"),
        review_context_ids=(proposal.proposal_id, shadow.evaluation_id, "learning:1", "contract:C10"),
        withheld_rationale_ids=("rationale:policy-delta",),
        required_check_ids=(
            "check:evidence-leakage",
            "check:budget-escalation",
            "check:false-halt",
            "check:specification-gaming",
        ),
    )
    return bind_policy_review(
        request,
        verdict=PolicyReviewVerdict.SUPPORTED_FOR_ADOPTION,
        completed_check_ids=request.required_check_ids,
        reproduced_evidence_ids=(proposal.proposal_id, shadow.evaluation_id),
        reason="fresh-context reviewer reproduced the holdout evidence and found no blocker",
    )


def _authorization(*, operation, source, target, decision_artifact_id):
    return ExternalPolicyAuthorization(
        operation=operation,
        source_policy_id=source.policy_id,
        target_policy_id=target.policy_id,
        decision_artifact_id=decision_artifact_id,
        issuer_component_id="external.assurance",
        issuer_authority_id="authority:reasoning-policy-change",
        authorization_evidence_ids=("assurance:evidence:1", "assurance:evidence:2"),
    )


def test_c10_revision_and_policy_identity_are_explicit_and_round_trip() -> None:
    assert COMPONENT_VERSION == "0.0.5"
    root = _root()
    assert root.revision == 1
    assert root.parent_policy_id is None
    assert MetareasoningPolicy.from_state(root.to_state()) == root


def test_policy_is_constraint_only_and_cannot_expand_caller_budget() -> None:
    policy = _root()
    caller = MetareasoningBudget(
        frontier_id="frontier:1",
        remaining_actions=2,
        remaining_cost=4.0,
        minimum_actionable_gain=0.40,
    )
    effective = constrain_metareasoning_budget(policy, caller)
    assert effective.frontier_id == caller.frontier_id
    assert effective.remaining_actions == 2
    assert effective.remaining_cost == 4.0
    assert effective.minimum_actionable_gain == 0.40

    looser_caller = MetareasoningBudget(
        frontier_id="frontier:1",
        remaining_actions=9,
        remaining_cost=20.0,
        minimum_actionable_gain=0.05,
    )
    constrained = constrain_metareasoning_budget(policy, looser_caller)
    assert constrained.remaining_actions == 5
    assert constrained.remaining_cost == 12.0
    assert constrained.minimum_actionable_gain == 0.15


def test_policy_evidence_split_requires_multi_episode_disjoint_dev_and_holdout() -> None:
    split = _split()
    assert set(split.development_episode_ids).isdisjoint(split.holdout_episode_ids)
    with pytest.raises(ValueError, match="disjoint"):
        PolicyEvidenceSplit(
            development_episode_ids=("episode:1", "episode:2"),
            holdout_episode_ids=("episode:2", "episode:3"),
        )


def test_policy_revision_proposal_binds_exact_parent_candidate_and_evidence() -> None:
    parent = _root()
    candidate = _candidate(parent)
    proposal = _proposal(parent, candidate)
    assert proposal.parent_policy_id == parent.policy_id
    assert proposal.candidate_policy_id == candidate.policy_id
    assert proposal.evidence_split == _split()
    assert proposal.learning_evidence_ids == ("learning:1", "learning:2")
    assert proposal.revision == parent.revision + 1


def test_shadow_gate_is_pareto_and_rejects_compensating_regression() -> None:
    parent = _root()
    proposal = _proposal(parent, _candidate(parent))
    supported = _supported_shadow(proposal)
    assert supported.verdict is PolicyShadowVerdict.PARETO_NON_REGRESSING

    regression = evaluate_policy_shadow(
        proposal,
        parent_metrics=PolicyMetricVector(0.80, 0.55, 0.50, 6.0, 0.20, 1),
        candidate_metrics=PolicyMetricVector(0.99, 0.95, 0.90, 9.0, 0.10, 0),
        holdout_episode_ids=_split().holdout_episode_ids,
    )
    assert regression.verdict is PolicyShadowVerdict.REJECTED
    assert regression.regressed_metric_ids == ("cost",)


def test_fresh_context_review_binds_proposal_shadow_and_complete_checks() -> None:
    parent = _root()
    proposal = _proposal(parent, _candidate(parent))
    shadow = _supported_shadow(proposal)
    receipt = _supported_review(proposal, shadow)
    assert receipt.proposal_id == proposal.proposal_id
    assert receipt.shadow_evaluation_id == shadow.evaluation_id
    assert receipt.verdict is PolicyReviewVerdict.SUPPORTED_FOR_ADOPTION


def test_policy_adoption_requires_exact_external_authorization() -> None:
    parent = _root()
    candidate = _candidate(parent)
    proposal = _proposal(parent, candidate)
    shadow = _supported_shadow(proposal)
    review = _supported_review(proposal, shadow)
    authorization = _authorization(
        operation=PolicyOperation.ADOPT,
        source=parent,
        target=candidate,
        decision_artifact_id=proposal.proposal_id,
    )

    adoption = apply_authorized_policy_revision(
        parent,
        candidate,
        proposal=proposal,
        shadow=shadow,
        review=review,
        authorization=authorization,
    )
    assert adoption.source_policy_id == parent.policy_id
    assert adoption.adopted_policy_id == candidate.policy_id
    assert adoption.authorization_id == authorization.authorization_id


def test_policy_rollback_is_lineage_exact_and_restores_parent_without_mutation() -> None:
    parent = _root()
    candidate = _candidate(parent)
    proposal = _proposal(parent, candidate)
    shadow = _supported_shadow(proposal)
    review = _supported_review(proposal, shadow)
    adoption = apply_authorized_policy_revision(
        parent,
        candidate,
        proposal=proposal,
        shadow=shadow,
        review=review,
        authorization=_authorization(
            operation=PolicyOperation.ADOPT,
            source=parent,
            target=candidate,
            decision_artifact_id=proposal.proposal_id,
        ),
    )
    rollback_auth = _authorization(
        operation=PolicyOperation.ROLLBACK,
        source=candidate,
        target=parent,
        decision_artifact_id=adoption.receipt_id,
    )
    rollback = rollback_policy_revision(
        candidate,
        parent,
        adoption=adoption,
        authorization=rollback_auth,
    )
    assert rollback.rolled_back_policy_id == candidate.policy_id
    assert rollback.restored_policy_id == parent.policy_id
    assert parent.revision == 1
    assert candidate.revision == 2
