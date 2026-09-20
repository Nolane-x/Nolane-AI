from __future__ import annotations

import torch

from native_core import ACTION_FEATURE_DIM
from public_planner import GOAL_HYPOTHESIS_COUNT
from sequential_evidence_core import (
    NativeR24SequentialEvidenceEnsemble,
    TRANSITION_FEATURE_DIM,
    encode_transition_evidence,
)


def _observation(state: list[int], progress: float, step: int, budget: int) -> dict:
    return {
        "state": list(state),
        "progress_signal": float(progress),
        "step": int(step),
        "budget_remaining": int(budget),
    }


def test_transition_encoder_has_locked_shape() -> None:
    action = torch.zeros(ACTION_FEATURE_DIM)
    action[0] = 1.0
    encoded = encode_transition_evidence(
        before=_observation([0, 1, 2], 0.25, 2, 30),
        after=_observation([1, 1, 2], 0.5, 3, 29),
        selected_action_features=action,
        progress_delta=0.25,
        information_gain=1.0,
        failed=False,
    )
    assert encoded.shape == (TRANSITION_FEATURE_DIM,)
    assert torch.isfinite(encoded).all()


def test_parameter_count_is_preregistered() -> None:
    model = NativeR24SequentialEvidenceEnsemble(ensemble_size=3, hidden_dim=96)
    assert model.parameter_count() == 82455


def test_posterior_hard_masks_exact_public_support() -> None:
    model = NativeR24SequentialEvidenceEnsemble(ensemble_size=3, hidden_dim=16)
    cumulative = torch.randn(3, GOAL_HYPOTHESIS_COUNT)
    support = torch.zeros(GOAL_HYPOTHESIS_COUNT, dtype=torch.bool)
    support[7] = True
    support[22] = True
    mean, per_head = model.posterior(
        cumulative_logits=cumulative,
        support_mask=support,
        temperature=1.0,
    )
    assert mean.shape == (GOAL_HYPOTHESIS_COUNT,)
    assert per_head.shape == (3, GOAL_HYPOTHESIS_COUNT)
    assert float(mean[~support].abs().sum().item()) == 0.0
    assert abs(float(mean.sum().item()) - 1.0) < 1.0e-6


def test_zero_evidence_is_uniform_inside_support() -> None:
    model = NativeR24SequentialEvidenceEnsemble(ensemble_size=3, hidden_dim=16)
    support = torch.zeros(GOAL_HYPOTHESIS_COUNT, dtype=torch.bool)
    support[3] = True
    support[17] = True
    mean, _ = model.posterior(
        cumulative_logits=model.zero_cumulative_logits(),
        support_mask=support,
        temperature=1.0,
    )
    assert abs(float(mean[3].item()) - 0.5) < 1.0e-6
    assert abs(float(mean[17].item()) - 0.5) < 1.0e-6
