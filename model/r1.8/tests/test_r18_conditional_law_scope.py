from pathlib import Path

from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r18_training import configure_conditional_law_training, conditional_law_trainable_parameter_names


def test_conditional_law_optimizer_scope_freezes_every_parent_parameter():
    root=Path(__file__).resolve().parents[1]
    model=load_r17_checkpoint(root/'checkpoints/Nolane-R1.7-NCPM-OperatorExecutor.pt',expected_r1_2_checkpoint=root/'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',expected_r1_6_parent_checkpoint=root/'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt')[0]
    names=set(configure_conditional_law_training(model))
    assert names==set(conditional_law_trainable_parameter_names(model))
    for name,parameter in model.named_parameters():
        assert parameter.requires_grad is (name in names)
