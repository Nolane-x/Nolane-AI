from __future__ import annotations

import copy

import pytest
import torch

from native_core import (
    ACTION_FEATURE_DIM,
    GLOBAL_FEATURE_DIM,
    TARGET_VISIBLE_FEATURE_INDEX,
    NativeRecurrentPolicy,
)
from successor_core import NativeR2TransitionPolicy
from attributed_core import NativeR3AttributedBeliefPolicy
from goal_belief_core import (
    GOAL_BELIEF_FEATURE_DIM,
    NativeR4PublicGoalBeliefPolicy,
    PublicGoalConsistencyBelief,
)


def _parent() -> NativeR3AttributedBeliefPolicy:
    native = NativeRecurrentPolicy()
    r2 = NativeR2TransitionPolicy(native)
    return NativeR3AttributedBeliefPolicy(r2)


def _inputs(model: NativeR4PublicGoalBeliefPolicy, *, visible: bool):
    global_features = torch.zeros(1, GLOBAL_FEATURE_DIM)
    global_features[:, TARGET_VISIBLE_FEATURE_INDEX] = 1.0 if visible else 0.0
    actions = 4
    action_features = torch.zeros(1, actions, ACTION_FEATURE_DIM)
    valid = torch.ones(1, actions, dtype=torch.bool)
    hidden = model.init_parent_hidden(1)
    trace_features = torch.zeros(
        1,
        model.parent.parent.trace_length,
        model.parent.parent.trace_token_dim,
    )
    trace_valid = torch.zeros(
        1, model.parent.parent.trace_length, dtype=torch.bool
    )
    attribution_features = torch.zeros(
        1,
        model.parent.attribution_length,
        model.parent.attribution_token_dim,
    )
    attribution_valid = torch.zeros(
        1, model.parent.attribution_length, dtype=torch.bool
    )
    belief_features = torch.zeros(1, GOAL_BELIEF_FEATURE_DIM)
    return (
        global_features,
        action_features,
        valid,
        hidden,
        trace_features,
        trace_valid,
        attribution_features,
        attribution_valid,
        belief_features,
    )


def test_public_belief_intersects_progress_consistency_without_private_goal() -> None:
    belief = PublicGoalConsistencyBelief()
    true_goal = (1, 2, 3)
    belief.update({
        "state": [0, 0, 0],
        "progress_signal": 0.5,
        "actions": [],
    })
    first_count = belief.candidate_count
    assert first_count > 1
    assert belief.contains(true_goal)

    belief.update({
        "state": [1, 0, 0],
        "progress_signal": 0.583333,
        "actions": [],
    })
    assert belief.candidate_count <= first_count
    assert belief.contains(true_goal)
    encoded = belief.encode()
    assert encoded.shape == (GOAL_BELIEF_FEATURE_DIM,)
    assert torch.isclose(encoded[:125].sum(), torch.tensor(1.0))


def test_public_belief_rejects_impossible_progress_precision() -> None:
    belief = PublicGoalConsistencyBelief()
    with pytest.raises(ValueError, match="inconsistent"):
        belief.update({
            "state": [0, 0, 0],
            "progress_signal": 0.51,
            "actions": [],
        })


def test_visible_target_can_be_publicly_one_hot() -> None:
    belief = PublicGoalConsistencyBelief()
    belief.update({
        "state": [0, 0, 0],
        "target": [2, 3, 4],
        "progress_signal": 0.25,
        "actions": [],
    })
    assert belief.candidate_count == 1
    assert belief.contains((2, 3, 4))


def test_r4_initialization_is_exact_parent_equivalent() -> None:
    parent = _parent()
    model = NativeR4PublicGoalBeliefPolicy(copy.deepcopy(parent))
    args = _inputs(model, visible=False)
    with torch.no_grad():
        r4 = model.forward_step(*args)
        r3 = model.parent.forward_step(*args[:-1])
    assert torch.equal(r4["action_logits"], r3["action_logits"])
    assert torch.count_nonzero(r4["belief_residual_logits"]) == 0


def test_visible_target_path_remains_exact_after_residual_weights_change() -> None:
    parent = _parent()
    model = NativeR4PublicGoalBeliefPolicy(copy.deepcopy(parent))
    with torch.no_grad():
        for parameter in model.hidden_target_belief_score.parameters():
            parameter.fill_(0.125)
    args = _inputs(model, visible=True)
    with torch.no_grad():
        r4 = model.forward_step(*args)
        r3 = model.parent.forward_step(*args[:-1])
    assert torch.equal(r4["action_logits"], r3["action_logits"])
    assert torch.count_nonzero(r4["belief_residual_logits"]) == 0


def test_parent_is_frozen_and_successor_scope_is_nonempty() -> None:
    model = NativeR4PublicGoalBeliefPolicy(_parent())
    model.set_training_scope()
    assert all(not parameter.requires_grad for parameter in model.parent.parameters())
    assert model.successor_parameter_count() > 0
    assert all(parameter.requires_grad for parameter in model.successor_parameters())
