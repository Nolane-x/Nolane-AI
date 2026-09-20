from __future__ import annotations

import random

import torch

from dual_evidence_set_ranker_core import (
    BOTH_FAIL_CLASS,
    BOTH_SOLVE_CLASS,
    HARM_CLASS,
    JOINT_OUTCOME_CLASS_COUNT,
    PAIR_FEATURE_DIM,
    RESCUE_CLASS,
    NativeR38DualEvidenceSetRankerEnsemble,
)
from dual_evidence_set_ranker_training import (
    _round_robin_stratified_order,
    _select_action_row,
    _training_stratum,
)


def _group(task_index: int) -> list[dict[str, object]]:
    return [
        {
            "task_index": task_index,
            "step": 0,
            "class_id": BOTH_SOLVE_CLASS,
            "features": torch.zeros(PAIR_FEATURE_DIM),
        }
    ]


def test_parameter_count_is_identical_to_r36() -> None:
    model = NativeR38DualEvidenceSetRankerEnsemble(
        ensemble_size=3,
        goal_hidden_dim=96,
        set_hidden_dim=64,
    )
    assert model.goal_parameter_count() == 107799
    assert model.set_parameter_count() == 275730
    assert model.parameter_count() == 383529


def test_runtime_set_model_still_has_null_option() -> None:
    model = NativeR38DualEvidenceSetRankerEnsemble(
        ensemble_size=3,
        goal_hidden_dim=16,
        set_hidden_dim=16,
    )
    output = model.decision_set_outputs(torch.zeros(3, PAIR_FEATURE_DIM))
    assert output["outcome_probabilities"].shape == (3, 3, JOINT_OUTCOME_CLASS_COUNT)
    assert output["selection_probabilities"].shape == (3, 4)
    assert torch.allclose(
        output["selection_probabilities"].sum(dim=-1),
        torch.ones(3),
        atol=1e-6,
    )


def test_eight_training_strata_cover_contiguous_range() -> None:
    minimum = 22144
    maximum = 22527
    values = [
        _training_stratum(
            _group(index),
            minimum_index=minimum,
            maximum_index=maximum,
            stratum_count=8,
        )
        for index in range(minimum, maximum + 1)
    ]
    assert min(values) == 0
    assert max(values) == 7
    counts = [values.count(index) for index in range(8)]
    assert counts == [48] * 8


def test_round_robin_order_interleaves_strata_deterministically() -> None:
    groups = [_group(index) for index in range(22144, 22144 + 8 * 2)]
    order, strata = _round_robin_stratified_order(
        groups,
        stratum_count=8,
        rng=random.Random(123),
    )
    assert sorted(order) == list(range(len(groups)))
    observed = [strata[index] for index in order[:8]]
    assert observed == list(range(8))


def test_joint_classes_are_unchanged() -> None:
    assert (BOTH_FAIL_CLASS, RESCUE_CLASS, HARM_CLASS, BOTH_SOLVE_CLASS) == (0, 1, 2, 3)
    assert JOINT_OUTCOME_CLASS_COUNT == 4


class _FakeSetModel:
    ensemble_size = 3

    def decision_set_outputs(self, features: torch.Tensor) -> dict[str, torch.Tensor]:
        selection = torch.tensor([
            [0.10, 0.80, 0.10],
            [0.12, 0.78, 0.10],
            [0.11, 0.79, 0.10],
        ])
        outcome = torch.zeros(3, 2, 4)
        outcome[:, 0, :] = torch.tensor([0.03, 0.92, 0.02, 0.03])
        outcome[:, 1, :] = torch.tensor([0.10, 0.15, 0.65, 0.10])
        return {
            "selection_probabilities": selection,
            "selection_logits": selection.log(),
            "outcome_probabilities": outcome,
        }


def test_dual_evidence_selector_accepts_only_when_both_signals_pass() -> None:
    rows = [
        {"features": torch.zeros(PAIR_FEATURE_DIM), "candidate_action": 1},
        {"features": torch.ones(PAIR_FEATURE_DIM), "candidate_action": 2},
    ]
    selected, score = _select_action_row(
        _FakeSetModel(),
        rows,
        selection_threshold=0.70,
        rescue_threshold=0.85,
        harm_ceiling=0.05,
    )
    assert selected is not None
    assert int(selected["candidate_action"]) == 1
    assert score is not None
    assert score["min_selection"] >= 0.779
    assert score["min_rescue"] >= 0.919
    assert score["max_harm"] <= 0.02


def test_direct_rescue_gate_rejects_high_selection_false_positive() -> None:
    rows = [
        {"features": torch.zeros(PAIR_FEATURE_DIM), "candidate_action": 1},
        {"features": torch.ones(PAIR_FEATURE_DIM), "candidate_action": 2},
    ]
    model = _FakeSetModel()
    original = model.decision_set_outputs

    def low_rescue(features: torch.Tensor) -> dict[str, torch.Tensor]:
        output = original(features)
        outcome = output["outcome_probabilities"].clone()
        outcome[:, 0, RESCUE_CLASS] = 0.40
        outcome[:, 0, BOTH_FAIL_CLASS] = 0.55
        output["outcome_probabilities"] = outcome
        return output

    model.decision_set_outputs = low_rescue
    selected, score = _select_action_row(
        model,
        rows,
        selection_threshold=0.70,
        rescue_threshold=0.85,
        harm_ceiling=0.05,
    )
    assert selected is None
    assert score is not None
    assert score["min_selection"] >= 0.779
    assert score["min_rescue"] < 0.85
