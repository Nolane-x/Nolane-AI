from __future__ import annotations

import torch

from goal_belief_core import (
    GOAL_HYPOTHESIS_COUNT,
    encode_public_goal_features,
    fuse_public_and_neural_posterior,
    goal_index,
)


def test_goal_index_is_base5() -> None:
    assert goal_index((0, 0, 0)) == 0
    assert goal_index((4, 4, 4)) == 124
    assert goal_index((1, 2, 3)) == 38


def test_public_goal_features_have_locked_shape() -> None:
    support = torch.zeros(GOAL_HYPOTHESIS_COUNT, dtype=torch.bool)
    support[0] = True
    row = encode_public_goal_features(
        support_mask=support,
        observation={
            "state": [0, 1, 2],
            "progress_signal": 0.5,
            "budget_remaining": 20,
            "step": 4,
        },
        previous_feedback=[0.1, 0.5, 0.0],
    )
    assert row.shape == (146,)
    assert float(row[:125].sum().item()) == 1.0


def test_fusion_never_broadens_exact_support() -> None:
    public = torch.zeros(125)
    public[4] = 0.5
    public[9] = 0.5
    neural = torch.full((125,), 1.0 / 125.0)
    fused = fuse_public_and_neural_posterior(public, neural, beta=1.0)
    assert torch.count_nonzero(fused).item() == 2
    assert float(fused[4] + fused[9]) > 0.999999


def test_beta_zero_is_public_exact() -> None:
    public = torch.zeros(125)
    public[1] = 0.25
    public[2] = 0.75
    neural = torch.zeros(125)
    neural[1] = 1.0
    fused = fuse_public_and_neural_posterior(public, neural, beta=0.0)
    assert torch.allclose(fused, public)
