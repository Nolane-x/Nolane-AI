from __future__ import annotations

import copy

import torch

from native_core import (
    ACTION_FEATURE_DIM,
    GLOBAL_FEATURE_DIM,
    TARGET_VISIBLE_FEATURE_INDEX,
    NativeRecurrentPolicy,
)
from successor_core import TRACE_TOKEN_DIM, NativeR2TransitionPolicy
from attributed_core import ATTRIBUTION_TOKEN_DIM, NativeR3AttributedBeliefPolicy
from latent_goal_core import NativeR4LatentGoalBeliefPolicy
from belief_correction_core import (
    GOAL_HYPOTHESIS_COUNT,
    NativeR8BeliefCorrectionPolicy,
    PublicGoalConsistencyBelief,
)


def _r4_parent() -> NativeR4LatentGoalBeliefPolicy:
    torch.manual_seed(17)
    native = NativeRecurrentPolicy(
        global_dim=GLOBAL_FEATURE_DIM,
        action_dim=ACTION_FEATURE_DIM,
        hidden_dim=32,
        attention_heads=4,
    )
    r2 = NativeR2TransitionPolicy(
        native,
        trace_token_dim=TRACE_TOKEN_DIM,
        trace_hidden_dim=24,
        trace_length=8,
    )
    r3 = NativeR3AttributedBeliefPolicy(
        r2,
        attribution_hidden_dim=24,
        attribution_length=12,
    )
    return NativeR4LatentGoalBeliefPolicy(
        r3,
        belief_hidden_dim=20,
        goal_embedding_dim=12,
    )


def _inputs(actions: int = 4) -> tuple[torch.Tensor, ...]:
    return (
        torch.zeros(1, GLOBAL_FEATURE_DIM),
        torch.randn(1, actions, ACTION_FEATURE_DIM),
        torch.ones(1, actions, dtype=torch.bool),
        torch.zeros(1, 32),
        torch.zeros(1, 8, TRACE_TOKEN_DIM),
        torch.zeros(1, 8, dtype=torch.bool),
        torch.zeros(1, 12, ATTRIBUTION_TOKEN_DIM),
        torch.zeros(1, 12, dtype=torch.bool),
    )


def test_public_belief_uses_public_state_progress_only() -> None:
    belief = PublicGoalConsistencyBelief()
    belief.update({"state":[0,0,0],"progress_signal":0.75})
    first = belief.support_size()
    assert 1 < first < GOAL_HYPOTHESIS_COUNT
    belief.update({"state":[1,0,0],"progress_signal":0.833333})
    assert 0 < belief.support_size() <= first
    assert torch.isclose(belief.encode().sum(), torch.tensor(1.0))


def test_broad_public_evidence_is_exact_parent_fallback() -> None:
    parent = _r4_parent()
    model = NativeR8BeliefCorrectionPolicy(copy.deepcopy(parent),max_support=1,correction_strength=1.0)
    posterior = torch.full((1,GOAL_HYPOTHESIS_COUNT),1.0/GOAL_HYPOTHESIS_COUNT)
    inputs = _inputs()
    with torch.no_grad():
        expected = parent.forward_step(*inputs)["action_logits"]
        out = model.forward_step(*inputs,posterior)
    assert torch.equal(out["action_logits"],expected)
    assert not bool(out["correction_active"].item())


def test_visible_target_is_exact_parent_fallback() -> None:
    parent = _r4_parent()
    model = NativeR8BeliefCorrectionPolicy(copy.deepcopy(parent),max_support=125,correction_strength=1.0)
    posterior = torch.zeros(1,GOAL_HYPOTHESIS_COUNT)
    posterior[:,0]=1.0
    inputs=list(_inputs())
    inputs[0][:,TARGET_VISIBLE_FEATURE_INDEX]=1.0
    with torch.no_grad():
        expected=parent.forward_step(*inputs)["action_logits"]
        out=model.forward_step(*inputs,posterior)
    assert torch.equal(out["action_logits"],expected)
    assert not bool(out["correction_active"].item())


def test_singleton_public_belief_activates_correction() -> None:
    model=NativeR8BeliefCorrectionPolicy(_r4_parent(),max_support=1,correction_strength=1.0)
    posterior=torch.zeros(1,GOAL_HYPOTHESIS_COUNT)
    posterior[:,0]=1.0
    with torch.no_grad():
        out=model.forward_step(*_inputs(),posterior)
    assert bool(out["correction_active"].item())
    assert torch.equal(out["corrected_goal_probabilities"],out["public_goal_marginals"])


def test_r8_adds_no_trainable_parameters() -> None:
    model=NativeR8BeliefCorrectionPolicy(_r4_parent(),max_support=3,correction_strength=0.5)
    assert model.successor_parameter_count()==0
    assert model.successor_parameters()==[]
    assert all(not p.requires_grad for p in model.parent.parameters())
