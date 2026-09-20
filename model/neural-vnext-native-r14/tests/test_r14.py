from __future__ import annotations

import torch

from native_core import PublicActionMemory
from public_planner import GOAL_HYPOTHESIS_COUNT
from causal_version_space import PublicCausalRuleMemory, choose_public_causal_action
from belief_tree_planner import (
    choose_public_belief_tree_action,
    posterior_branches,
)


def _observation(*, visible: bool = False) -> dict:
    row = {
        "state": [0, 0, 0],
        "progress_signal": 0.833333,
        "regime": "amber",
        "actions": [
            "opaque actuator A",
            "opaque actuator B",
            "opaque actuator C",
            "submit current hypothesis",
        ],
    }
    if visible:
        row["target"] = [1, 0, 0]
    return row


def test_progress_feedback_partition_can_reduce_support() -> None:
    # goals [1,0,0] (index 25) and [0,2,0] (index 10)
    posterior = torch.zeros(GOAL_HYPOTHESIS_COUNT)
    posterior[25] = 0.5
    posterior[10] = 0.5
    branches = posterior_branches(torch.tensor([0, 0, 0]), posterior)
    assert len(branches) == 2
    assert sorted(int((branch > 0).sum().item()) for _, _, branch in branches) == [1, 1]
    assert abs(sum(mass for mass, _, _ in branches) - 1.0) < 1.0e-6


def test_visible_target_is_exact_r11_fallback() -> None:
    observation = _observation(visible=True)
    exact = PublicActionMemory(4)
    causal = PublicCausalRuleMemory()
    posterior = torch.zeros(GOAL_HYPOTHESIS_COUNT)
    posterior[25] = 1.0
    logits = torch.tensor([0.0, 3.0, 1.0, -1.0])
    expected, _ = choose_public_causal_action(
        observation=observation,
        exact_memory=exact,
        causal_memory=causal,
        posterior=posterior,
        parent_logits=logits,
        horizon=1,
    )
    actual, info = choose_public_belief_tree_action(
        observation=observation,
        exact_memory=exact,
        causal_memory=causal,
        posterior=posterior,
        parent_logits=logits,
        depth=2,
        guard_mode="expected_worst",
    )
    assert actual == expected
    assert info["reason"] == "target_visible_r11_exact"


def test_broad_posterior_is_exact_r11_fallback() -> None:
    observation = _observation()
    exact = PublicActionMemory(4)
    causal = PublicCausalRuleMemory()
    posterior = torch.full(
        (GOAL_HYPOTHESIS_COUNT,),
        1.0 / GOAL_HYPOTHESIS_COUNT,
    )
    logits = torch.tensor([0.0, 3.0, 1.0, -1.0])
    expected, _ = choose_public_causal_action(
        observation=observation,
        exact_memory=exact,
        causal_memory=causal,
        posterior=posterior,
        parent_logits=logits,
        horizon=1,
    )
    actual, info = choose_public_belief_tree_action(
        observation=observation,
        exact_memory=exact,
        causal_memory=causal,
        posterior=posterior,
        parent_logits=logits,
        depth=3,
        guard_mode="expected_worst",
    )
    assert actual == expected
    assert info["reason"] == "posterior_too_broad_r11_fallback"


def test_planner_source_does_not_require_private_goal() -> None:
    observation = _observation()
    exact = PublicActionMemory(4)
    causal = PublicCausalRuleMemory()
    posterior = torch.zeros(GOAL_HYPOTHESIS_COUNT)
    posterior[25] = 1.0
    logits = torch.tensor([2.0, 1.0, 0.0, -1.0])
    action, info = choose_public_belief_tree_action(
        observation=observation,
        exact_memory=exact,
        causal_memory=causal,
        posterior=posterior,
        parent_logits=logits,
        depth=2,
        guard_mode="pareto_current",
    )
    assert 0 <= action < 4
    assert "reason" in info
