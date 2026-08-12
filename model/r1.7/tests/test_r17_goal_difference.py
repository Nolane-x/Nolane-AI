from pathlib import Path

import torch

from cogcoder.neural_system2 import NeuralSystem2Workspace, system2_parameter_count
from cogcoder.r17_training import load_r17_checkpoint


def _r12():
    return Path(__file__).resolve().parents[1] / 'checkpoints/Nolane-Rebuild-R1.2-ACE.pt'


def _r16():
    return Path(__file__).resolve().parents[1] / 'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt'


def _law():
    return Path(__file__).resolve().parents[1] / 'checkpoints/Nolane-R1.7-NCPM-CausalLaws.pt'


def test_goal_difference_workspace_is_zero_policy_neutral_at_initialization():
    torch.manual_seed(17)
    model=NeuralSystem2Workspace()
    atoms=torch.randn(2,12,model.structured_atom_dim)
    mask=torch.ones(2,12,dtype=torch.bool)
    deltas=torch.randn(2,4,model.psr_sketch_dim)
    actions=torch.randn(2,4,model.workspace_dim)
    confidence=torch.ones(2,4)
    out=model.goal_difference_scores(atoms,mask,deltas,actions,confidence)
    assert out['predicted_progress'].shape==(2,4)
    assert torch.count_nonzero(out['policy_bonus'])==0


def test_goal_difference_scores_are_action_permutation_equivariant():
    torch.manual_seed(23)
    model=NeuralSystem2Workspace()
    atoms=torch.randn(1,10,model.structured_atom_dim); mask=torch.ones(1,10,dtype=torch.bool)
    deltas=torch.randn(1,3,model.psr_sketch_dim); actions=torch.randn(1,3,model.workspace_dim); conf=torch.rand(1,3)
    base=model.goal_difference_scores(atoms,mask,deltas,actions,conf)
    perm=torch.tensor([2,0,1])
    moved=model.goal_difference_scores(atoms,mask,deltas[:,perm],actions[:,perm],conf[:,perm])
    assert torch.allclose(moved['predicted_progress'],base['predicted_progress'][:,perm],atol=1e-6)
    assert torch.allclose(moved['policy_bonus'],base['policy_bonus'][:,perm],atol=1e-6)


def test_goal_difference_exposes_distinct_learned_current_and_target_roles():
    torch.manual_seed(29)
    model=NeuralSystem2Workspace()
    atoms=torch.randn(1,7,model.structured_atom_dim); mask=torch.ones(1,7,dtype=torch.bool)
    out=model.goal_difference_scores(atoms,mask,torch.zeros(1,2,128),torch.randn(1,2,640),torch.ones(1,2))
    assert out['current_attention'].shape==(1,7)
    assert out['target_attention'].shape==(1,7)
    assert torch.allclose(out['current_attention'].sum(-1),torch.ones(1),atol=1e-6)
    assert torch.allclose(out['target_attention'].sum(-1),torch.ones(1),atol=1e-6)
    assert not torch.allclose(out['current_attention'],out['target_attention'])


def test_existing_causal_law_checkpoint_loads_with_goal_difference_neutral_and_budget():
    model,meta=load_r17_checkpoint(_law(),expected_r1_2_checkpoint=_r12(),expected_r1_6_parent_checkpoint=_r16())
    assert meta['candidate_effective_parameters']==73_642_371
    assert float(model.goal_difference_policy_scale.detach())==0.0
    effective=49_528_677+system2_parameter_count(model)
    assert effective<96_000_000
