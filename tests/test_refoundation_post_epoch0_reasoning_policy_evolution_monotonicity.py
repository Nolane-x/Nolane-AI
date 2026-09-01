from __future__ import annotations

import pytest

from nolane.external_core.reasoning_policy_evolution import (
    MetareasoningPolicy,
    PolicyEvidenceSplit,
    propose_policy_revision,
)


def _parent() -> MetareasoningPolicy:
    return MetareasoningPolicy(
        revision=1,
        parent_policy_id=None,
        max_remaining_actions=4,
        max_remaining_cost=8.0,
        minimum_actionable_gain_floor=0.25,
        allowed_action_kinds=("target_unknown", "design_experiment", "fresh_context_review"),
    )


def _split() -> PolicyEvidenceSplit:
    return PolicyEvidenceSplit(
        development_episode_ids=("dev:1", "dev:2"),
        holdout_episode_ids=("hold:1", "hold:2"),
    )


def _propose(parent: MetareasoningPolicy, candidate: MetareasoningPolicy):
    return propose_policy_revision(
        parent,
        candidate,
        evidence_split=_split(),
        learning_evidence_ids=("learning:1",),
        producer_agent_id="producer",
        producer_session_id="producer-session",
        rationale_ids=("rationale:constraint-change",),
    )


def test_candidate_revision_cannot_expand_action_or_cost_budget() -> None:
    parent = _parent()
    expanded_actions = MetareasoningPolicy(
        revision=2,
        parent_policy_id=parent.policy_id,
        max_remaining_actions=5,
        max_remaining_cost=8.0,
        minimum_actionable_gain_floor=0.25,
        allowed_action_kinds=parent.allowed_action_kinds,
    )
    with pytest.raises(ValueError, match="constraint"):
        _propose(parent, expanded_actions)

    expanded_cost = MetareasoningPolicy(
        revision=2,
        parent_policy_id=parent.policy_id,
        max_remaining_actions=4,
        max_remaining_cost=9.0,
        minimum_actionable_gain_floor=0.25,
        allowed_action_kinds=parent.allowed_action_kinds,
    )
    with pytest.raises(ValueError, match="constraint"):
        _propose(parent, expanded_cost)


def test_candidate_revision_cannot_lower_gain_floor_or_add_action_kind() -> None:
    parent = _parent()
    lower_floor = MetareasoningPolicy(
        revision=2,
        parent_policy_id=parent.policy_id,
        max_remaining_actions=4,
        max_remaining_cost=8.0,
        minimum_actionable_gain_floor=0.20,
        allowed_action_kinds=parent.allowed_action_kinds,
    )
    with pytest.raises(ValueError, match="constraint"):
        _propose(parent, lower_floor)

    added_kind = MetareasoningPolicy(
        revision=2,
        parent_policy_id=parent.policy_id,
        max_remaining_actions=4,
        max_remaining_cost=8.0,
        minimum_actionable_gain_floor=0.25,
        allowed_action_kinds=parent.allowed_action_kinds + ("causal_challenge",),
    )
    with pytest.raises(ValueError, match="constraint"):
        _propose(parent, added_kind)


def test_candidate_revision_may_only_tighten_parent_constraints() -> None:
    parent = _parent()
    tighter = MetareasoningPolicy(
        revision=2,
        parent_policy_id=parent.policy_id,
        max_remaining_actions=3,
        max_remaining_cost=6.0,
        minimum_actionable_gain_floor=0.30,
        allowed_action_kinds=("target_unknown", "fresh_context_review"),
    )
    proposal = _propose(parent, tighter)
    assert proposal.parent_policy_id == parent.policy_id
    assert proposal.candidate_policy_id == tighter.policy_id
