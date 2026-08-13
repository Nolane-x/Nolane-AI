from pathlib import Path
import pytest
import torch
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r18_benchmark import make_r18_task
from cogcoder.r18_executive_training import collect_executive_episode,configure_executive_training,executive_trainable_parameter_names

def _model():
    root=Path(__file__).resolve().parents[1]
    return load_r17_checkpoint(root/'checkpoints/Nolane-R1.8-CCSM-ControlEffect.pt',expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]
def test_executive_collector_is_train_only_and_emits_public_frozen_features():
    m=_model().eval();ep=collect_executive_episode(m,make_r18_task('conditional_regimes','train',200),max_steps=16);assert ep.steps;r=ep.steps[0];assert r.state_sketch.shape==(128,);assert r.context_fingerprint.shape==(64,);assert r.progress.shape==(1,);assert r.budget_fraction.shape==(1,);assert r.previous_feedback.shape==(3,);assert r.conditional_hidden.ndim==2 and r.conditional_hidden.shape[-1]==256;assert r.control_effect.shape==(r.conditional_hidden.shape[0],64);assert r.evidence_meta.shape==(r.conditional_hidden.shape[0],3);assert r.progress_memory.shape==(r.conditional_hidden.shape[0],2);assert 0<=r.label<r.conditional_hidden.shape[0];assert torch.isfinite(r.progress_memory).all()
    with pytest.raises(ValueError,match='train split'):collect_executive_episode(m,make_r18_task('conditional_regimes','dev',0))
    with pytest.raises(ValueError,match='train split'):collect_executive_episode(m,make_r18_task('conditional_regimes','fresh',0))
def test_executive_scope_is_exactly_857857_parameters():
    m=_model();names=set(configure_executive_training(m));assert names==set(executive_trainable_parameter_names(m));assert all(n.startswith('r18_executive_') for n in names);assert sum(p.numel() for p in m.parameters() if p.requires_grad)==857_857;assert not m.conditional_control_effect_head.weight.requires_grad
def test_regime_switch_collector_keeps_context_specific_progress_memory():
    m=_model().eval();ep=collect_executive_episode(m,make_r18_task('regime_switch','train',200),max_steps=16);assert len(ep.steps)>=6;assert torch.count_nonzero(ep.steps[0].progress_memory)==0;assert any(torch.count_nonzero(step.progress_memory)>0 for step in ep.steps[1:])
