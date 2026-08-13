from pathlib import Path
import pytest
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r18_benchmark import make_r18_task
from cogcoder.r18_control_reliability import collect_control_reliability_rows,configure_control_reliability_training

def _model():
    root=Path(__file__).resolve().parents[1]
    return load_r17_checkpoint(root/'checkpoints/Nolane-R1.8-CCSM-ControlEffect.pt',expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]
def test_control_reliability_collector_is_train_only_and_emits_control_error_rows():
    model=_model();rows=collect_control_reliability_rows(model,make_r18_task('conditional_regimes','train',92),safe_mse=0.01,exploration_steps=6,max_steps=16);assert rows;row=rows[0];assert row.hidden.shape==(256,);assert row.evidence_meta.shape==(3,);assert row.prediction_mse>=0;assert row.safe in (0.0,1.0)
    with pytest.raises(ValueError,match='train split'):collect_control_reliability_rows(model,make_r18_task('conditional_regimes','dev',0),safe_mse=0.01)
def test_control_reliability_optimizer_scope_is_exactly_existing_257_confidence_params():
    model=_model();names=set(configure_control_reliability_training(model));assert names=={'conditional_law_confidence_head.weight','conditional_law_confidence_head.bias'};assert sum(p.numel() for p in model.parameters() if p.requires_grad)==257;assert not model.conditional_control_effect_head.weight.requires_grad
