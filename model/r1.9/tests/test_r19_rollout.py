from __future__ import annotations

import torch
import pytest

from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r18_benchmark import make_r18_task
from cogcoder.r19_rollout import collect_rollout_eval_rows, collect_rollout_rows


def _parent(tmp_path=None):
    root = __import__('pathlib').Path(__file__).resolve().parents[1]
    model, _ = load_r17_checkpoint(
        root / 'checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt',
        expected_r1_2_checkpoint=root / 'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',
        expected_r1_6_parent_checkpoint=root / 'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt',
    )
    model.eval()
    return model


def test_rollout_collector_is_train_only():
    model = _parent()
    with pytest.raises(ValueError, match='train split'):
        collect_rollout_rows(model, make_r18_task('conditional_regimes', 'dev', 0), max_states=1)


def test_rollout_rows_are_public_and_exact_two_step_targets():
    model = _parent()
    task = make_r18_task('conditional_regimes', 'train', 77)
    rows = collect_rollout_rows(model, task, max_states=1)
    assert rows
    row = rows[0]
    assert row.state_sketch.shape == (128,)
    assert row.context_fingerprint.shape == (64,)
    assert row.program_action_embeddings.shape == (2, model.workspace_dim)
    assert row.parent_effects.shape == (2, 128)
    assert row.target_effect.shape == (128,)
    assert row.program_indices[0] != row.submit_index
    assert row.program_indices[1] != row.submit_index
    assert not hasattr(row, 'private_state')
    assert not hasattr(row, 'oracle_plan')
    assert torch.isfinite(row.target_effect).all()
    assert not torch.equal(row.target_effect, row.parent_effects.sum(dim=0))


def test_rollout_collection_is_deterministic_for_locked_seed():
    model = _parent()
    rows_a = collect_rollout_rows(model, make_r18_task('causal_prerequisites', 'train', 91), max_states=2)
    rows_b = collect_rollout_rows(model, make_r18_task('causal_prerequisites', 'train', 91), max_states=2)
    assert len(rows_a) == len(rows_b)
    for a, b in zip(rows_a, rows_b):
        assert a.task_id == b.task_id
        assert a.program_indices == b.program_indices
        torch.testing.assert_close(a.state_sketch, b.state_sketch)
        torch.testing.assert_close(a.context_fingerprint, b.context_fingerprint)
        torch.testing.assert_close(a.parent_effects, b.parent_effects)
        torch.testing.assert_close(a.target_effect, b.target_effect)


def test_eval_collector_can_open_dev_without_weakening_train_only_collector():
    model = _parent()
    rows = collect_rollout_eval_rows(model, make_r18_task('conditional_regimes', 'dev', 3), max_states=1)
    assert rows
    assert all(row.family == 'conditional_regimes' for row in rows)
