from __future__ import annotations

import torch

from native_core import ACTION_FEATURE_DIM, GLOBAL_FEATURE_DIM, NativeRecurrentPolicy, TARGET_VISIBLE_FEATURE_INDEX
from successor_core import TRACE_TOKEN_DIM, NativeR2TransitionPolicy
from attributed_core import ATTRIBUTION_TOKEN_DIM, NativeR3AttributedBeliefPolicy
from latent_goal_core import NativeR4LatentGoalBeliefPolicy
from neural_causal_core import CAUSAL_FEATURE_DIM, NativeR12NeuralCausalResidualPolicy


def _r4()->NativeR4LatentGoalBeliefPolicy:
    torch.manual_seed(17)
    native=NativeRecurrentPolicy(global_dim=GLOBAL_FEATURE_DIM,action_dim=ACTION_FEATURE_DIM,hidden_dim=32,attention_heads=4)
    r2=NativeR2TransitionPolicy(native,trace_token_dim=TRACE_TOKEN_DIM,trace_hidden_dim=24,trace_length=8)
    r3=NativeR3AttributedBeliefPolicy(r2,attribution_hidden_dim=24,attribution_length=12)
    return NativeR4LatentGoalBeliefPolicy(r3,belief_hidden_dim=20,goal_embedding_dim=12)


def _parent_output(parent,global_features,action_features,valid):
    return parent.forward_step(
        global_features,
        action_features,
        valid,
        torch.zeros(1,32),
        torch.zeros(1,8,TRACE_TOKEN_DIM),
        torch.zeros(1,8,dtype=torch.bool),
        torch.zeros(1,12,ATTRIBUTION_TOKEN_DIM),
        torch.zeros(1,12,dtype=torch.bool),
    )


def test_zero_init_hidden_action_matches_r11_anchor() -> None:
    parent=_r4()
    model=NativeR12NeuralCausalResidualPolicy(parent,posterior_embedding_dim=16,residual_hidden_dim=24,max_support=6,parent_margin=1.0)
    g=torch.zeros(1,GLOBAL_FEATURE_DIM)
    a=torch.randn(1,4,ACTION_FEATURE_DIM)
    valid=torch.ones(1,4,dtype=torch.bool)
    with torch.no_grad():
        po=_parent_output(parent,g,a,valid)
        out=model.forward_from_parent(
            global_features=g,
            action_features=a,
            valid_actions=valid,
            parent_output=po,
            consistency_posterior=torch.nn.functional.one_hot(torch.tensor([0]),125).float(),
            causal_action_features=torch.zeros(1,4,CAUSAL_FEATURE_DIM),
            r11_actions=torch.tensor([2]),
        )
    assert int(out["action_logits"].argmax(-1).item())==2
    assert torch.equal(out["causal_residual_logits"],torch.zeros_like(out["causal_residual_logits"]))


def test_visible_target_returns_exact_r4_logits() -> None:
    parent=_r4()
    model=NativeR12NeuralCausalResidualPolicy(parent,posterior_embedding_dim=16,residual_hidden_dim=24,max_support=125,parent_margin=1.0)
    with torch.no_grad():
        model.residual_score[-1].bias.fill_(10.0)
    g=torch.zeros(1,GLOBAL_FEATURE_DIM)
    g[:,TARGET_VISIBLE_FEATURE_INDEX]=1.0
    a=torch.randn(1,4,ACTION_FEATURE_DIM)
    valid=torch.ones(1,4,dtype=torch.bool)
    with torch.no_grad():
        po=_parent_output(parent,g,a,valid)
        out=model.forward_from_parent(
            global_features=g,
            action_features=a,
            valid_actions=valid,
            parent_output=po,
            consistency_posterior=torch.nn.functional.one_hot(torch.tensor([0]),125).float(),
            causal_action_features=torch.zeros(1,4,CAUSAL_FEATURE_DIM),
            r11_actions=torch.tensor([2]),
        )
    assert torch.equal(out["action_logits"],po["action_logits"])


def test_broad_support_disables_residual() -> None:
    parent=_r4()
    model=NativeR12NeuralCausalResidualPolicy(parent,posterior_embedding_dim=16,residual_hidden_dim=24,max_support=3,parent_margin=1.0)
    with torch.no_grad():
        model.residual_score[-1].bias.fill_(10.0)
    g=torch.zeros(1,GLOBAL_FEATURE_DIM)
    a=torch.randn(1,4,ACTION_FEATURE_DIM)
    valid=torch.ones(1,4,dtype=torch.bool)
    posterior=torch.full((1,125),1.0/125.0)
    with torch.no_grad():
        po=_parent_output(parent,g,a,valid)
        out=model.forward_from_parent(
            global_features=g,
            action_features=a,
            valid_actions=valid,
            parent_output=po,
            consistency_posterior=posterior,
            causal_action_features=torch.zeros(1,4,CAUSAL_FEATURE_DIM),
            r11_actions=torch.tensor([1]),
        )
    assert torch.equal(out["causal_residual_logits"],torch.zeros_like(out["causal_residual_logits"]))
    assert int(out["action_logits"].argmax(-1).item())==1


def test_only_r12_modules_are_trainable() -> None:
    model=NativeR12NeuralCausalResidualPolicy(_r4(),posterior_embedding_dim=16,residual_hidden_dim=24,max_support=3,parent_margin=1.0)
    model.set_training_scope()
    assert all(not p.requires_grad for p in model.parent.parameters())
    assert model.successor_parameter_count()>0
    assert all(p.requires_grad for p in model.successor_parameters())
