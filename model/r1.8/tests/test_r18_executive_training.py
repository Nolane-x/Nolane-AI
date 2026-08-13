from pathlib import Path
import pytest
import torch
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r18_benchmark import make_r18_task
from cogcoder.r18_executive_training import collect_executive_episode,configure_executive_training,evaluate_executive_episodes,executive_trainable_parameter_names,train_executive_epoch

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
def test_executive_sequence_training_and_evaluation_are_recurrent_and_parent_frozen():
    m=_model();episodes=[collect_executive_episode(m,make_r18_task('conditional_regimes','train',200+i),max_steps=10) for i in range(2)];configure_executive_training(m);parent_before=m.conditional_control_effect_head.weight.detach().clone();exec_before=m.r18_executive_action_scorer[0].weight.detach().clone();optimizer=torch.optim.AdamW([p for p in m.parameters() if p.requires_grad],lr=1e-3);before=evaluate_executive_episodes(m,episodes);loss=train_executive_epoch(m,episodes,optimizer);after=evaluate_executive_episodes(m,episodes);reset=evaluate_executive_episodes(m,episodes,reset_state_each_step=True);assert before['steps']>0 and after['steps']==before['steps'] and reset['steps']==before['steps'];assert loss>=0 and torch.isfinite(torch.tensor(loss));assert torch.equal(m.conditional_control_effect_head.weight,parent_before);assert not torch.equal(m.r18_executive_action_scorer[0].weight,exec_before);assert 0.0<=after['accuracy']<=1.0 and after['cross_entropy']>=0.0
