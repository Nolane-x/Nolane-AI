from __future__ import annotations

import torch

from native_core import PublicActionMemory
from public_planner import GOAL_HYPOTHESIS_COUNT
from causal_version_space import (
    PublicCausalRuleMemory,
    choose_public_causal_action,
)


def _obs(state: list[int], progress: float = 0.75) -> dict:
    return {
        "state": state,
        "progress_signal": progress,
        "regime": "amber",
        "actions": [
            "opaque actuator a",
            "opaque actuator b",
            "opaque actuator c",
            "submit current hypothesis",
        ],
    }


def _record(
    exact: PublicActionMemory,
    causal: PublicCausalRuleMemory,
    *,
    action: int,
    before_state: list[int],
    after_state: list[int],
) -> None:
    before=_obs(before_state)
    after=_obs(after_state)
    exact.update(
        action=action,
        before=before,
        after=after,
        progress_delta=0.0,
        information_gain=1.0,
        failed=False,
    )
    causal.update(action=action,before=before,after=after)


def test_version_space_certifies_when_all_remaining_rules_agree() -> None:
    causal=PublicCausalRuleMemory()
    exact=PublicActionMemory(4)
    _record(exact,causal,action=0,before_state=[0,0,0],after_state=[1,0,0])
    predicted,count=causal.predict_certified(
        context="amber",
        state=torch.tensor([2,2,2]),
        action=0,
    )
    assert count==3
    assert predicted is not None
    assert predicted.tolist()==[3,2,2]


def test_version_space_learns_factorized_condition_dimension() -> None:
    causal=PublicCausalRuleMemory()
    exact=PublicActionMemory(4)
    _record(exact,causal,action=0,before_state=[0,0,0],after_state=[1,0,0])
    _record(exact,causal,action=0,before_state=[0,1,0],after_state=[1,1,0])
    _record(exact,causal,action=0,before_state=[0,0,1],after_state=[1,0,1])
    rules=causal.consistent_rules(context="amber",action=0)
    assert rules==((0,0,1),)
    predicted,count=causal.predict_certified(
        context="amber",
        state=torch.tensor([2,1,1]),
        action=0,
    )
    assert count==1
    assert predicted is not None
    assert predicted.tolist()==[3,1,1]


def test_causal_generalization_can_override_r9_on_unseen_full_parity() -> None:
    exact=PublicActionMemory(4)
    causal=PublicCausalRuleMemory()
    _record(exact,causal,action=0,before_state=[0,0,0],after_state=[1,0,0])
    _record(exact,causal,action=0,before_state=[0,1,0],after_state=[1,1,0])
    _record(exact,causal,action=0,before_state=[0,0,1],after_state=[1,0,1])

    posterior=torch.zeros(GOAL_HYPOTHESIS_COUNT)
    # Goal [3,1,1] => 3*25 + 1*5 + 1 = 81.
    posterior[81]=1.0
    action,info=choose_public_causal_action(
        observation=_obs([2,1,1],0.916667),
        exact_memory=exact,
        causal_memory=causal,
        posterior=posterior,
        parent_logits=torch.tensor([0.0,5.0,1.0,-1.0]),
        horizon=1,
    )
    assert action==0
    assert info["reason"]=="certified_causal_advantage"
    assert info["selected_rule_count"]==1


def test_visible_target_is_exact_r9_fallback() -> None:
    exact=PublicActionMemory(4)
    causal=PublicCausalRuleMemory()
    obs={**_obs([0,0,0],1.0),"target":[0,0,0]}
    posterior=torch.zeros(GOAL_HYPOTHESIS_COUNT); posterior[0]=1.0
    action,info=choose_public_causal_action(
        observation=obs,
        exact_memory=exact,
        causal_memory=causal,
        posterior=posterior,
        parent_logits=torch.tensor([9.0,0.0,0.0,1.0]),
        horizon=3,
    )
    assert action==0
    assert info["reason"]=="target_visible_r9_exact"


def test_no_public_samples_falls_back_to_r9() -> None:
    exact=PublicActionMemory(4)
    causal=PublicCausalRuleMemory()
    posterior=torch.zeros(GOAL_HYPOTHESIS_COUNT); posterior[81]=1.0
    action,info=choose_public_causal_action(
        observation=_obs([2,1,1],0.916667),
        exact_memory=exact,
        causal_memory=causal,
        posterior=posterior,
        parent_logits=torch.tensor([0.0,5.0,1.0,-1.0]),
        horizon=2,
    )
    assert action==1
    assert info["reason"]=="no_certified_causal_advantage"
