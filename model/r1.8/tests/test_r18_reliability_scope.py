from pathlib import Path
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r18_reliability_training import configure_reliability_training

def test_actual_reliability_training_scope_is_exactly_257_confidence_parameters():
    root=Path(__file__).resolve().parents[1]
    model=load_r17_checkpoint(root/'checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt',expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]
    names=set(configure_reliability_training(model))
    assert names=={'conditional_law_confidence_head.weight','conditional_law_confidence_head.bias'}
    assert sum(p.numel() for p in model.parameters() if p.requires_grad)==257
    assert not model.conditional_law_effect_head.weight.requires_grad
