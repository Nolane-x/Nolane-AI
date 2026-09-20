from __future__ import annotations

import torch

from native_core import PublicActionMemory
from public_planner import GOAL_HYPOTHESIS_COUNT
from causal_version_space import PublicCausalRuleMemory, choose_public_causal_action
from diagnostic_planner import _metrics, choose_public_diagnostic_action


def _obs(visible: bool=False)->dict:
    row={
        "state":[0,0,0],"progress_signal":0.75,"regime":"amber",
        "actions":["opaque A","opaque B","opaque C","submit current hypothesis"],
    }
    if visible:
        row["target"]=[1,1,1]
    return row


def test_feedback_metric_rewards_partitioning() -> None:
    posterior=torch.zeros(GOAL_HYPOTHESIS_COUNT)
    posterior[25]=0.5
    posterior[10]=0.5
    value=_metrics(torch.tensor([0,0,0]),posterior)
    assert value["expected_support_after_feedback"]==1.0
    assert sorted(value["partition_sizes"])==[1,1]


def test_low_support_is_exact_r11_authority() -> None:
    obs=_obs()
    exact=PublicActionMemory(4)
    causal=PublicCausalRuleMemory()
    posterior=torch.zeros(GOAL_HYPOTHESIS_COUNT)
    posterior[25]=0.5
    posterior[10]=0.5
    logits=torch.tensor([1.0,2.0,0.0,-1.0])
    expected,_=choose_public_causal_action(
        observation=obs,exact_memory=exact,causal_memory=causal,
        posterior=posterior,parent_logits=logits,horizon=1,
    )
    actual,info=choose_public_diagnostic_action(
        observation=obs,exact_memory=exact,causal_memory=causal,
        posterior=posterior,parent_logits=logits,max_support=12,
        guard_mode="expected_worst_ref",
    )
    assert actual==expected
    assert info["reason"]=="low_support_r11_authority"


def test_visible_target_is_exact_r11_authority() -> None:
    obs=_obs(visible=True)
    exact=PublicActionMemory(4)
    causal=PublicCausalRuleMemory()
    posterior=torch.full((GOAL_HYPOTHESIS_COUNT,),1.0/GOAL_HYPOTHESIS_COUNT)
    logits=torch.tensor([1.0,2.0,0.0,-1.0])
    expected,_=choose_public_causal_action(
        observation=obs,exact_memory=exact,causal_memory=causal,
        posterior=posterior,parent_logits=logits,horizon=1,
    )
    actual,info=choose_public_diagnostic_action(
        observation=obs,exact_memory=exact,causal_memory=causal,
        posterior=posterior,parent_logits=logits,max_support=24,
        guard_mode="pareto_ref",
    )
    assert actual==expected
    assert info["reason"]=="target_visible_r11_exact"
