from pathlib import Path
import torch
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.neural_system2 import system2_parameter_count

def _model():
    root=Path(__file__).resolve().parents[1]
    return load_r17_checkpoint(root/'checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt',expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]
def test_control_effect_head_is_zero_neutral_and_exactly_16448_params():
    model=_model();hidden=torch.randn(2,5,model.conditional_law_dim);out=model.conditional_control_effect_scores(hidden);assert out.shape==(2,5,64);assert torch.count_nonzero(out)==0;assert model.conditional_control_effect_head.weight.numel()+model.conditional_control_effect_head.bias.numel()==16_448;assert 49_528_677+system2_parameter_count(model)==76_693_852
def test_control_effect_head_is_action_permutation_equivariant():
    model=_model();hidden=torch.randn(1,4,model.conditional_law_dim);perm=torch.tensor([2,0,3,1]);base=model.conditional_control_effect_scores(hidden);moved=model.conditional_control_effect_scores(hidden[:,perm]);assert torch.allclose(moved,base[:,perm],atol=1e-6)
