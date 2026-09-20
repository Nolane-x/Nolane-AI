from __future__ import annotations

import torch

from native_core import PublicActionMemory
from public_planner import (
    GOAL_HYPOTHESIS_COUNT,
    PublicGoalConsistencyBelief,
    choose_public_counterfactual_action,
)


def test_progress_complete_forces_public_submit() -> None:
    memory=PublicActionMemory(4)
    posterior=torch.full((GOAL_HYPOTHESIS_COUNT,),1.0/GOAL_HYPOTHESIS_COUNT)
    action,info=choose_public_counterfactual_action(
        observation={"state":[1,2,3],"progress_signal":1.0,"actions":["opaque a","submit current hypothesis","opaque b","opaque c"]},
        memory=memory,posterior=posterior,parent_logits=torch.tensor([9.0,0.0,1.0,2.0]),max_support=1,
    )
    assert action==1
    assert info["reason"]=="public_progress_complete"


def test_visible_target_never_overridden() -> None:
    memory=PublicActionMemory(4)
    posterior=torch.zeros(GOAL_HYPOTHESIS_COUNT); posterior[0]=1.0
    action,info=choose_public_counterfactual_action(
        observation={"state":[0,0,0],"target":[0,0,0],"progress_signal":1.0,"actions":["opaque a","submit current hypothesis","opaque b","opaque c"]},
        memory=memory,posterior=posterior,parent_logits=torch.tensor([3.0,2.0,1.0,0.0]),max_support=1,
    )
    assert action==0
    assert info["reason"]=="target_visible"


def test_broad_hidden_posterior_falls_back() -> None:
    memory=PublicActionMemory(4)
    posterior=torch.full((GOAL_HYPOTHESIS_COUNT,),1.0/GOAL_HYPOTHESIS_COUNT)
    action,info=choose_public_counterfactual_action(
        observation={"state":[0,0,0],"progress_signal":0.5,"regime":"amber","actions":["opaque a","submit current hypothesis","opaque b","opaque c"]},
        memory=memory,posterior=posterior,parent_logits=torch.tensor([0.0,0.0,4.0,1.0]),max_support=1,
    )
    assert action==2
    assert not info["override"]


def test_known_local_transition_can_override_parent() -> None:
    memory=PublicActionMemory(4)
    before={"state":[0,0,0],"progress_signal":0.75,"regime":"amber","actions":["opaque a","submit current hypothesis","opaque b","opaque c"]}
    after={"state":[1,0,0],"progress_signal":0.833333,"regime":"amber","actions":before["actions"]}
    memory.update(action=0,before=before,after=after,progress_delta=0.083333,information_gain=1.0,failed=False)
    # Goal [2,0,0] is row 50 in lexicographic product 0..4^3.
    posterior=torch.zeros(GOAL_HYPOTHESIS_COUNT); posterior[50]=1.0
    action,info=choose_public_counterfactual_action(
        observation=before,memory=memory,posterior=posterior,parent_logits=torch.tensor([0.0,0.0,4.0,1.0]),max_support=1,
    )
    assert action==0
    assert info["reason"]=="known_public_counterfactual_improvement"
