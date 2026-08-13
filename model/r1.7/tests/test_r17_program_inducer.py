from pathlib import Path
import torch
from cogcoder.neural_system2 import NeuralSystem2Workspace,system2_parameter_count
from cogcoder.r17_training import load_r17_checkpoint

def _root(): return Path(__file__).resolve().parents[1]

def test_program_ranker_zero_neutral_permutation_and_phase_sensitive():
    torch.manual_seed(1781);m=NeuralSystem2Workspace();features=torch.randn(2,6,384);steps=torch.tensor([0.,2.]);base=m.latent_program_rank_scores(features,steps);assert base.shape==(2,6);assert torch.count_nonzero(base)==0
    perm=torch.tensor([5,2,0,4,1,3]);moved=m.latent_program_rank_scores(features[:,perm],steps);assert torch.allclose(moved,base[:,perm],atol=1e-7)
    enc0=m.latent_program_phase_encoding(torch.tensor([0.]));enc2=m.latent_program_phase_encoding(torch.tensor([2.]));assert enc0.shape==(1,32);assert not torch.allclose(enc0,enc2)

def test_goal_difference_checkpoint_loads_program_ranker_neutral_under_ceiling():
    r=_root();m,_=load_r17_checkpoint(r/'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt',expected_r1_2_checkpoint=r/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=r/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt');assert torch.count_nonzero(m.latent_program_rank_scores(torch.zeros(1,6,384),torch.zeros(1)))==0;assert 49_528_677+system2_parameter_count(m)<96_000_000
