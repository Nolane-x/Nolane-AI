from pathlib import Path
import torch
from cogcoder.neural_system2 import NeuralSystem2Workspace, system2_parameter_count
from cogcoder.r17_training import load_r17_checkpoint

def _root(): return Path(__file__).resolve().parents[1]

def test_role_effect_ranker_zero_init_and_permutation_equivariance():
    torch.manual_seed(17171); model=NeuralSystem2Workspace(); need=torch.randn(2,64); effects=torch.randn(2,5,64); role_conf=torch.ones(2); law_conf=torch.rand(2,5)
    base=model.causal_role_effect_rank_scores(need,role_conf,effects,law_conf); assert base.shape==(2,5); assert torch.count_nonzero(base)==0
    perm=torch.tensor([4,1,3,0,2]); moved=model.causal_role_effect_rank_scores(need,role_conf,effects[:,perm],law_conf[:,perm]); assert torch.allclose(moved,base[:,perm],atol=1e-7)

def test_role_effect_ranker_checkpoint_compatibility_and_budget():
    root=_root(); model,meta=load_r17_checkpoint(root/'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt',expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')
    scores=model.causal_role_effect_rank_scores(torch.zeros(1,64),torch.ones(1),torch.zeros(1,3,64),torch.ones(1,3)); assert torch.count_nonzero(scores)==0
    assert 49_528_677+system2_parameter_count(model)<96_000_000
