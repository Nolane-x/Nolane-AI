from pathlib import Path
import pytest
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r18_benchmark import make_r18_task
from cogcoder.r18_control_effect_training import collect_control_effect_episode, control_effect_internal_gate, control_effect_trainable_parameter_names

def _model():
    root=Path(__file__).resolve().parents[1]
    return load_r17_checkpoint(root/'checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt',expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]

def test_control_effect_collector_is_train_only_and_emits_role_aligned_rows():
    model=_model();ep=collect_control_effect_episode(model,make_r18_task('conditional_regimes','train',68),exploration_steps=6,max_steps=16)
    assert ep.steps
    row=ep.steps[0];assert row.hidden.ndim==2 and row.hidden.shape[-1]==256;assert row.target_effects.shape[-1]==64;assert row.baseline_effects.shape==row.target_effects.shape;assert row.predict_mask.shape==(row.hidden.shape[0],)
    with pytest.raises(ValueError,match='train split'):collect_control_effect_episode(model,make_r18_task('conditional_regimes','dev',0))

def test_control_effect_scope_is_only_new_head():
    names=control_effect_trainable_parameter_names(_model());assert set(names)=={'conditional_control_effect_head.weight','conditional_control_effect_head.bias'}

def test_control_effect_gate_requires_each_family_non_regression_and_min_rows():
    good={'candidate_mse':.01,'baseline_mse':.02,'families':{f:{'candidate_mse':.01,'baseline_mse':.02,'rows':100} for f in ('conditional_regimes','regime_switch','implicit_goal_regimes','causal_prerequisites')}}
    assert control_effect_internal_gate(good,min_rows_per_family=64)
    bad={**good,'families':{**good['families'],'regime_switch':{'candidate_mse':.021,'baseline_mse':.02,'rows':100}}};assert not control_effect_internal_gate(bad,min_rows_per_family=64)
