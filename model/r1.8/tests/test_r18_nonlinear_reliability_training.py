from pathlib import Path
import pytest
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r18_benchmark import make_r18_task
from cogcoder.r18_nonlinear_reliability_training import collect_nonlinear_reliability_rows,configure_nonlinear_reliability_training

def _model():
    root=Path(__file__).resolve().parents[1]
    return load_r17_checkpoint(root/'checkpoints/Nolane-R1.8-CCSM-ControlEffect.pt',expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]
def test_nonlinear_reliability_collector_is_train_only_and_caches_production_features():
    m=_model();rows=collect_nonlinear_reliability_rows(m,make_r18_task('regime_switch','train',112),safe_mse=.01,exploration_steps=6,max_steps=16);assert rows;r=rows[0];assert r.features.shape==(451,);assert r.prediction_mse>=0;assert r.safe in (0.,1.);assert r.seen in (0.,1.)
    with pytest.raises(ValueError,match='train split'):collect_nonlinear_reliability_rows(m,make_r18_task('regime_switch','dev',0),safe_mse=.01)
def test_nonlinear_reliability_scope_is_only_new_57985_parameter_head():
    m=_model();names=set(configure_nonlinear_reliability_training(m));assert all(n.startswith('conditional_reliability_head.') for n in names);assert sum(p.numel() for p in m.parameters() if p.requires_grad)==57_985;assert not m.conditional_control_effect_head.weight.requires_grad
