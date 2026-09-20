from __future__ import annotations

import torch

from native_core import ACTION_FEATURE_DIM
from public_planner import GOAL_HYPOTHESIS_COUNT
from selective_correction_core import (
    NativeR25SelectiveCorrectionEnsemble,
    PUBLIC_BASE_FEATURE_DIM,
    encode_public_base_features,
)


def test_parameter_count_is_preregistered() -> None:
    model = NativeR25SelectiveCorrectionEnsemble(ensemble_size=3, hidden_dim=64)
    assert model.parameter_count() == 75846


def test_public_base_feature_shape() -> None:
    support = torch.zeros(GOAL_HYPOTHESIS_COUNT, dtype=torch.bool)
    support[2] = True
    support[7] = True
    features = encode_public_base_features(
        support_mask=support,
        observation={
            "state": [1, 2, 3],
            "progress_signal": 0.5,
            "budget_remaining": 20,
            "step": 4,
        },
        previous_feedback=[0.1, 0.2, 0.0],
        r11_decision={
            "reason": "no_certified_causal_advantage",
            "override": False,
            "support": 2,
            "r9_rule_count": 3,
            "r9_reference_distance": 4.0,
            "horizon": 1,
        },
    )
    assert features.shape == (PUBLIC_BASE_FEATURE_DIM,)
    assert torch.isfinite(features).all()


def test_predict_supports_variable_action_count() -> None:
    model = NativeR25SelectiveCorrectionEnsemble(ensemble_size=3, hidden_dim=16)
    base = torch.zeros(PUBLIC_BASE_FEATURE_DIM)
    r11 = torch.zeros(ACTION_FEATURE_DIM)
    actions = torch.zeros(5, ACTION_FEATURE_DIM)
    detector, correction = model.predict(
        base_features=base,
        r11_action_features=r11,
        action_features=actions,
    )
    assert detector.shape == (3,)
    assert correction.shape == (3, 5)
    assert torch.isfinite(detector).all()
    assert torch.isfinite(correction).all()
