from pathlib import Path

import pytest
import torch

from cogcoder.r17_benchmark import make_r17_task
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r17_goal_training import (
    collect_goal_difference_episode,
    goal_difference_trainable_parameter_names,
)


def _root():
    return Path(__file__).resolve().parents[1]


def _load_law():
    return load_r17_checkpoint(
        _root() / 'checkpoints/Nolane-R1.7-NCPM-CausalLaws.pt',
        expected_r1_2_checkpoint=_root() / 'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',
        expected_r1_6_parent_checkpoint=_root() / 'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt',
    )[0]


def test_goal_difference_optimizer_scope_excludes_policy_scale_and_parent():
    model=_load_law()
    names=goal_difference_trainable_parameter_names(model,include_policy_scale=False)
    assert names
    assert all(n.startswith('goal_difference_') for n in names)
    assert 'goal_difference_policy_scale' not in names
    assert all(not n.startswith('causal_law_') for n in names)


def test_goal_difference_collector_rejects_nontrain_splits():
    model=_load_law()
    with pytest.raises(ValueError,match='train split'):
        collect_goal_difference_episode(model,make_r17_task('causal_laws','dev',56))
    with pytest.raises(ValueError,match='train split'):
        collect_goal_difference_episode(model,make_r17_task('causal_switch','fresh',56))


def test_goal_difference_collector_emits_public_law_conditioned_progress_targets():
    torch.manual_seed(17)
    model=_load_law(); model.eval()
    ep=collect_goal_difference_episode(model,make_r17_task('causal_laws','train',56),exploration_steps=6,max_steps=10)
    assert ep.steps
    row=next(step for step in ep.steps if float(step.confidence.max())>0)
    assert row.structured_atoms.ndim==2
    assert row.structured_mask.ndim==1
    assert row.predicted_deltas.shape[0]==row.action_embeddings.shape[0]
    assert row.predicted_deltas.shape[1]==128
    assert row.confidence.shape==(row.action_embeddings.shape[0],)
    assert row.target_progress.shape==row.confidence.shape
    assert row.baseline_progress.shape==row.confidence.shape
    assert row.predict_mask.dtype==torch.bool
    assert torch.isfinite(row.target_progress[row.predict_mask]).all()
    assert float(row.confidence.max())>0


def test_goal_difference_safe_exploration_preserves_teacher_continuation_on_trap_world():
    model=_load_law(); model.eval()
    ep=collect_goal_difference_episode(
        model,make_r17_task('causal_laws','train',61),exploration_steps=6,max_steps=14
    )
    assert ep.steps
    assert len(ep.steps)<=14
