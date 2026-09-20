from __future__ import annotations

import torch

from native_core import PublicActionMemory
from multistep_planner import choose_public_multistep_action
from public_planner import GOAL_HYPOTHESIS_COUNT


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


def _remember(memory: PublicActionMemory, action: int, before: dict, after_state: list[int]) -> None:
    after={**before,"state":after_state}
    memory.update(
        action=action,
        before=before,
        after=after,
        progress_delta=0.0,
        information_gain=1.0,
        failed=False,
    )


def test_visible_target_is_exact_r9_fallback() -> None:
    memory=PublicActionMemory(4)
    obs={**_obs([0,0,0],1.0),"target":[0,0,0]}
    posterior=torch.zeros(GOAL_HYPOTHESIS_COUNT); posterior[0]=1.0
    action,info=choose_public_multistep_action(
        observation=obs,
        memory=memory,
        posterior=posterior,
        parent_logits=torch.tensor([9.0,0.0,0.0,1.0]),
        horizon=3,
    )
    assert action==0
    assert info["reason"]=="target_visible_r9_exact"


def test_public_progress_complete_preserves_r9_submit_guard() -> None:
    memory=PublicActionMemory(4)
    posterior=torch.full((GOAL_HYPOTHESIS_COUNT,),1.0/GOAL_HYPOTHESIS_COUNT)
    action,info=choose_public_multistep_action(
        observation=_obs([1,2,3],1.0),
        memory=memory,
        posterior=posterior,
        parent_logits=torch.tensor([9.0,0.0,1.0,2.0]),
        horizon=4,
    )
    assert action==3
    assert info["reason"]=="r9_public_progress_complete"


def test_broad_posterior_falls_back_to_r9() -> None:
    memory=PublicActionMemory(4)
    posterior=torch.full((GOAL_HYPOTHESIS_COUNT,),1.0/GOAL_HYPOTHESIS_COUNT)
    action,info=choose_public_multistep_action(
        observation=_obs([0,0,0],0.5),
        memory=memory,
        posterior=posterior,
        parent_logits=torch.tensor([0.0,4.0,1.0,0.0]),
        horizon=2,
    )
    assert action==1
    assert info["reason"]=="posterior_too_broad_r9_fallback"


def test_multistep_can_choose_certified_better_first_action() -> None:
    memory=PublicActionMemory(4)
    start=_obs([0,0,0])
    # Action 0: immediate +1 on dim0. This is attractive to R9.
    _remember(memory,0,start,[1,0,0])
    # Action 1: same immediate distance as action 0, but reaches a parity
    # with a known second transition to the exact goal.
    _remember(memory,1,start,[0,1,0])
    parity_state=_obs([0,1,0])
    _remember(memory,2,parity_state,[2,0,0])

    posterior=torch.zeros(GOAL_HYPOTHESIS_COUNT)
    # Lexicographic goal [2,0,0] => index 50.
    posterior[50]=1.0
    action,info=choose_public_multistep_action(
        observation=start,
        memory=memory,
        posterior=posterior,
        parent_logits=torch.tensor([5.0,4.0,0.0,-1.0]),
        horizon=2,
    )
    assert action==1
    assert info["reason"]=="certified_multistep_advantage"
    assert info["selected_depth"]==2


def test_horizon_bounds_are_locked() -> None:
    memory=PublicActionMemory(4)
    posterior=torch.zeros(GOAL_HYPOTHESIS_COUNT); posterior[0]=1.0
    try:
        choose_public_multistep_action(
            observation=_obs([0,0,0]),
            memory=memory,
            posterior=posterior,
            parent_logits=torch.zeros(4),
            horizon=1,
        )
    except ValueError as exc:
        assert "horizon" in str(exc)
    else:
        raise AssertionError("horizon=1 must be rejected")
