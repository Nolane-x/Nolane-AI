from pathlib import Path
import torch
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.neural_system2 import system2_parameter_count

def _model():
    root=Path(__file__).resolve().parents[1]
    return load_r17_checkpoint(root/'checkpoints/Nolane-R1.8-CCSM-ControlEffect.pt',expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]
def test_nonlinear_certificate_is_neutral_on_parent_and_exactly_57985_params():
    model=_model();batch,actions=2,4;out=model.conditional_reliability_scores(torch.randn(batch,actions,256),torch.randn(batch,actions,64),torch.randn(batch,actions,64),torch.zeros(batch,actions,3));assert out['logits'].shape==(batch,actions);assert torch.count_nonzero(out['logits'])==0;assert torch.count_nonzero(out['score'])==0;assert sum(p.numel() for p in model.conditional_reliability_head.parameters())==57_985;assert 49_528_677+system2_parameter_count(model)==76_693_852
def test_nonlinear_certificate_is_action_permutation_equivariant():
    model=_model();hidden=torch.randn(1,5,256);pred=torch.randn(1,5,64);evidence=torch.randn(1,5,64);meta=torch.rand(1,5,3);meta[...,0]=.25;base=model.conditional_reliability_scores(hidden,pred,evidence,meta);perm=torch.tensor([3,0,4,1,2]);moved=model.conditional_reliability_scores(hidden[:,perm],pred[:,perm],evidence[:,perm],meta[:,perm]);assert torch.allclose(moved['logits'],base['logits'][:,perm],atol=1e-6);assert torch.allclose(moved['score'],base['score'][:,perm],atol=1e-6)
