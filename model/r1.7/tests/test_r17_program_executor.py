from pathlib import Path
import pytest
import torch

from cogcoder.neural_system2 import NeuralSystem2Workspace, system2_parameter_count
from cogcoder.r17_training import load_r17_checkpoint


def _root(): return Path(__file__).resolve().parents[1]


def test_program_executor_shapes_variable_length_and_action_conditioning():
    torch.manual_seed(1791)
    model=NeuralSystem2Workspace()
    vectors=torch.tensor([[0,1,2,3],[3,2,1,0]],dtype=torch.long)
    actions=torch.randn(2,model.workspace_dim)
    logits=model.program_execute_logits(vectors,actions)
    assert logits.shape==(2,4,model.program_executor_value_vocab)
    logits2=model.program_execute_logits(vectors,actions+0.5)
    assert not torch.allclose(logits,logits2)
    short=model.program_execute_logits(torch.tensor([[1,2]],dtype=torch.long),torch.randn(1,model.workspace_dim))
    assert short.shape==(1,2,model.program_executor_value_vocab)


def test_program_executor_rejects_out_of_vocab_and_too_long_vectors():
    model=NeuralSystem2Workspace()
    with pytest.raises(ValueError,match='value'):
        model.program_execute_logits(torch.tensor([[0,16]]),torch.zeros(1,model.workspace_dim))
    with pytest.raises(ValueError,match='length'):
        model.program_execute_logits(torch.zeros(1,17,dtype=torch.long),torch.zeros(1,model.workspace_dim))


def test_goal_difference_checkpoint_loads_program_executor_under_ceiling():
    r=_root();m,_=load_r17_checkpoint(r/'checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt',expected_r1_2_checkpoint=r/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=r/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')
    logits=m.program_execute_logits(torch.tensor([[0,1,2,3]]),torch.zeros(1,m.workspace_dim))
    assert logits.shape==(1,4,16)
    assert 49_528_677+system2_parameter_count(m)<96_000_000
