from __future__ import annotations

import torch

from goal_belief_core import GOAL_HYPOTHESIS_COUNT, NativeR23GoalBeliefEnsemble, PUBLIC_GOAL_FEATURE_DIM
from action_consensus_training import conformal_prediction_set


def test_model_masks_public_support() -> None:
    model=NativeR23GoalBeliefEnsemble(ensemble_size=3,hidden_dim=16)
    features=torch.zeros(PUBLIC_GOAL_FEATURE_DIM)
    support=torch.zeros(GOAL_HYPOTHESIS_COUNT,dtype=torch.bool)
    support[4]=True; support[19]=True
    mean,heads=model.probabilities(features=features,support_mask=support,temperature=1.0)
    assert mean.shape==(GOAL_HYPOTHESIS_COUNT,)
    assert heads.shape==(3,GOAL_HYPOTHESIS_COUNT)
    assert float(mean[~support].abs().sum().item())==0.0
    assert abs(float(mean.sum().item())-1.0)<1e-6


def test_prediction_set_respects_support() -> None:
    mean=torch.zeros(GOAL_HYPOTHESIS_COUNT)
    support=torch.zeros(GOAL_HYPOTHESIS_COUNT,dtype=torch.bool)
    support[5]=True; support[7]=True
    mean[5]=0.65; mean[7]=0.35
    selected=conformal_prediction_set(mean,support,q=0.7)
    assert bool(selected[5])
    assert bool(selected[7])
    assert int(selected.sum().item())==2
