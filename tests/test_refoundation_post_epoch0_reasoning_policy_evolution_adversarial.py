from __future__ import annotations

import pytest

import nolane.external_core.reasoning_policy_evolution as policy_module
from nolane.external_core.reasoning_metacontrol import MetareasoningBudget
from nolane.external_core.reasoning_policy_evolution import (
    ExternalPolicyAuthorization,
    MetareasoningPolicy,
    PolicyEvidenceSplit,
    PolicyMetricVector,
    PolicyOperation,
    PolicyReviewRequest,
    PolicyReviewReceipt,
    PolicyReviewVerdict,
    PolicyShadowEvaluation,
    PolicyShadowVerdict,
    apply_authorized_policy_revision,
    bind_policy_review,
    constrain_metareasoning_budget,
    evaluate_policy_shadow,
    propose_policy_revision,
)


def _root() -> MetareasoningPolicy:
    return MetareasoningPolicy(
        revision=1,
        parent_policy_id=None,
        max_remaining_actions=4,
        max_remaining_cost=10.0,
        minimum_actionable_gain_floor=0.2,
        allowed_action_kinds=("target_unknown", "design_experiment", "fresh_context_review"),
    )


def _candidate(parent: MetareasoningPolicy) -> MetareasoningPolicy:
    return MetareasoningPolicy(
        revision=2,
        parent_policy_id=parent.policy_id,
        max_remaining_actions=3,
        max_remaining_cost=8.0,
        minimum_actionable_gain_floor=0.25,
        allowed_action_kinds=("target_unknown", "fresh_context_review"),
    )


def _split() -> PolicyEvidenceSplit:
    return PolicyEvidenceSplit(
        development_episode_ids=("dev:1", "dev:2"),
        holdout_episode_ids=("hold:1", "hold:2"),
    )


def _proposal(parent, candidate):
    return propose_policy_revision(
        parent,
        candidate,
        evidence_split=_split(),
        learning_evidence_ids=("learning:1",),
        producer_agent_id="producer",
        producer_session_id="producer-session",
        rationale_ids=("rationale:1",),
    )


def _shadow(proposal):
    return evaluate_policy_shadow(
        proposal,
        parent_metrics=PolicyMetricVector(0.7, 0.5, 0.4, 5.0, 0.3, 1),
        candidate_metrics=PolicyMetricVector(0.8, 0.6, 0.5, 4.0, 0.2, 0),
        holdout_episode_ids=_split().holdout_episode_ids,
    )


def _review(proposal, shadow):
    request = PolicyReviewRequest(
        proposal_id=proposal.proposal_id,
        shadow_evaluation_id=shadow.evaluation_id,
        producer_agent_id="producer",
        reviewer_agent_id="reviewer",
        producer_session_id="producer-session",
        reviewer_session_id="reviewer-session",
        evidence_packet_ids=(proposal.proposal_id, shadow.evaluation_id),
        review_context_ids=(proposal.proposal_id, shadow.evaluation_id, "contract:c10"),
        withheld_rationale_ids=("rationale:1",),
        required_check_ids=("check:gaming", "check:leakage", "check:authority"),
    )
    return bind_policy_review(
        request,
        verdict=PolicyReviewVerdict.SUPPORTED_FOR_ADOPTION,
        completed_check_ids=request.required_check_ids,
        reproduced_evidence_ids=request.evidence_packet_ids,
        reason="supported",
    )


def test_numeric_contracts_reject_bool_smuggling() -> None:
    with pytest.raises(TypeError):
        MetareasoningPolicy(1, None, True, 10.0, 0.2, ("target_unknown",))
    with pytest.raises(TypeError):
        PolicyMetricVector(True, 0.5, 0.4, 5.0, 0.3, 0)
    with pytest.raises(TypeError):
        PolicyMetricVector(0.7, 0.5, 0.4, 5.0, 0.3, True)


def test_policy_revision_cannot_skip_or_forge_parent_lineage() -> None:
    root = _root()
    with pytest.raises(ValueError, match="parent"):
        MetareasoningPolicy(
            revision=2,
            parent_policy_id=None,
            max_remaining_actions=3,
            max_remaining_cost=8.0,
            minimum_actionable_gain_floor=0.25,
            allowed_action_kinds=("target_unknown",),
        )
    skipped = MetareasoningPolicy(
        revision=3,
        parent_policy_id=root.policy_id,
        max_remaining_actions=3,
        max_remaining_cost=8.0,
        minimum_actionable_gain_floor=0.25,
        allowed_action_kinds=("target_unknown",),
    )
    with pytest.raises(ValueError, match="one revision"):
        _proposal(root, skipped)


def test_forged_content_addressed_policy_and_shadow_ids_are_rejected() -> None:
    root = _root()
    forged_policy = root.to_state()
    forged_policy["policy_id"] = "reasoning-policy:forged"
    with pytest.raises(ValueError, match="identity"):
        MetareasoningPolicy.from_state(forged_policy)

    proposal = _proposal(root, _candidate(root))
    shadow = _shadow(proposal)
    forged_shadow = shadow.to_state()
    forged_shadow["evaluation_id"] = "policy-shadow:forged"
    with pytest.raises(ValueError, match="identity"):
        PolicyShadowEvaluation.from_state(forged_shadow)


def test_duplicate_and_leaking_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        PolicyEvidenceSplit(("dev:1", "dev:1"), ("hold:1", "hold:2"))
    with pytest.raises(ValueError, match="disjoint"):
        PolicyEvidenceSplit(("dev:1", "shared"), ("hold:1", "shared"))


def test_review_must_be_fresh_context_and_withhold_rationale() -> None:
    root = _root()
    proposal = _proposal(root, _candidate(root))
    shadow = _shadow(proposal)
    common = dict(
        proposal_id=proposal.proposal_id,
        shadow_evaluation_id=shadow.evaluation_id,
        evidence_packet_ids=(proposal.proposal_id, shadow.evaluation_id),
        review_context_ids=(proposal.proposal_id, shadow.evaluation_id),
        withheld_rationale_ids=("rationale:1",),
        required_check_ids=("check:gaming",),
    )
    with pytest.raises(ValueError, match="reviewer must differ"):
        PolicyReviewRequest(
            producer_agent_id="same",
            reviewer_agent_id="same",
            producer_session_id="p-session",
            reviewer_session_id="r-session",
            **common,
        )
    with pytest.raises(ValueError, match="session must differ"):
        PolicyReviewRequest(
            producer_agent_id="producer",
            reviewer_agent_id="reviewer",
            producer_session_id="same-session",
            reviewer_session_id="same-session",
            **common,
        )
    with pytest.raises(ValueError, match="withheld"):
        PolicyReviewRequest(
            producer_agent_id="producer",
            reviewer_agent_id="reviewer",
            producer_session_id="p-session",
            reviewer_session_id="r-session",
            **{**common, "review_context_ids": (proposal.proposal_id, shadow.evaluation_id, "rationale:1")},
        )


def test_supported_review_cannot_hide_objections_gaming_or_leakage() -> None:
    with pytest.raises(ValueError, match="supported"):
        PolicyReviewReceipt(
            proposal_id="proposal:1",
            shadow_evaluation_id="shadow:1",
            reviewer_agent_id="reviewer",
            reviewer_session_id="reviewer-session",
            verdict=PolicyReviewVerdict.SUPPORTED_FOR_ADOPTION,
            completed_check_ids=("check:1",),
            reproduced_evidence_ids=("evidence:1",),
            objection_ids=("objection:1",),
            gaming_finding_ids=(),
            leakage_finding_ids=(),
            reason="invalid support",
        )
    with pytest.raises(ValueError, match="supported"):
        PolicyReviewReceipt(
            proposal_id="proposal:1",
            shadow_evaluation_id="shadow:1",
            reviewer_agent_id="reviewer",
            reviewer_session_id="reviewer-session",
            verdict=PolicyReviewVerdict.SUPPORTED_FOR_ADOPTION,
            completed_check_ids=("check:1",),
            reproduced_evidence_ids=("evidence:1",),
            objection_ids=(),
            gaming_finding_ids=("gaming:1",),
            leakage_finding_ids=(),
            reason="invalid support",
        )


def test_reasoning_invention_cannot_mint_its_own_adoption_authority() -> None:
    root = _root()
    candidate = _candidate(root)
    with pytest.raises(ValueError, match="external"):
        ExternalPolicyAuthorization(
            operation=PolicyOperation.ADOPT,
            source_policy_id=root.policy_id,
            target_policy_id=candidate.policy_id,
            decision_artifact_id="proposal:1",
            issuer_component_id="external.reasoning_invention",
            issuer_authority_id="self-authority",
            authorization_evidence_ids=("evidence:1",),
        )
    assert not hasattr(policy_module, "authorize_policy_revision")
    assert not hasattr(policy_module, "self_promote_policy")


def test_adoption_rejects_wrong_authorization_target_and_non_green_review() -> None:
    root = _root()
    candidate = _candidate(root)
    proposal = _proposal(root, candidate)
    shadow = _shadow(proposal)
    review = _review(proposal, shadow)
    wrong = ExternalPolicyAuthorization(
        operation=PolicyOperation.ADOPT,
        source_policy_id=root.policy_id,
        target_policy_id="reasoning-policy:wrong",
        decision_artifact_id=proposal.proposal_id,
        issuer_component_id="external.assurance",
        issuer_authority_id="authority:policy",
        authorization_evidence_ids=("evidence:1",),
    )
    with pytest.raises(ValueError, match="target"):
        apply_authorized_policy_revision(
            root,
            candidate,
            proposal=proposal,
            shadow=shadow,
            review=review,
            authorization=wrong,
        )


def test_constraint_function_never_reduces_safety_threshold() -> None:
    policy = _root()
    budget = MetareasoningBudget("frontier:1", 1, 2.0, 0.8)
    effective = constrain_metareasoning_budget(policy, budget)
    assert effective.remaining_actions <= budget.remaining_actions
    assert effective.remaining_cost <= budget.remaining_cost
    assert effective.minimum_actionable_gain >= budget.minimum_actionable_gain
