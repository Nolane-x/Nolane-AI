from __future__ import annotations

from pathlib import Path

import pytest
import torch

from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r18_benchmark import make_r18_task
from cogcoder.r19_frontier import FrontierRolloutHead
from cogcoder.r19_rollout import collect_rollout_rows
from cogcoder.r19_training import (
    configure_r19_training,
    evaluate_r19_rows,
    load_r19_delta,
    r19_internal_gate,
    save_r19_delta,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _parent():
    root = _root()
    return load_r17_checkpoint(
        root / 'checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt',
        expected_r1_2_checkpoint=root / 'checkpoints/Nolane-Rebuild-R1.2-ACE.pt',
        expected_r1_6_parent_checkpoint=root / 'checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt',
    )[0]


def test_configure_training_freezes_parent_and_exposes_only_delta():
    parent = _parent()
    head = FrontierRolloutHead()
    names = configure_r19_training(parent, head)
    assert names
    assert not any(p.requires_grad for p in parent.parameters())
    assert all(p.requires_grad for p in head.parameters())
    assert sum(p.numel() for p in head.parameters() if p.requires_grad) < 2_000_000


def test_initial_evaluator_matches_additive_parent_baseline():
    parent = _parent()
    head = FrontierRolloutHead()
    rows = collect_rollout_rows(parent, make_r18_task('regime_switch', 'train', 101), max_states=1)
    metrics = evaluate_r19_rows(head, rows, batch_size=64)
    assert metrics['candidate_mse'] == pytest.approx(metrics['baseline_mse'], abs=1e-12)
    assert metrics['relative_improvement'] == pytest.approx(0.0, abs=1e-12)


def test_internal_gate_requires_every_family_to_improve():
    metrics = {
        'candidate_mse': 0.4,
        'baseline_mse': 1.0,
        'relative_improvement': 0.6,
        'families': {
            name: {'candidate_mse': 0.4, 'baseline_mse': 1.0, 'relative_improvement': 0.6}
            for name in ('a', 'b', 'c', 'd')
        },
    }
    assert r19_internal_gate(metrics)
    metrics['families']['c']['candidate_mse'] = 1.1
    metrics['families']['c']['relative_improvement'] = -0.1
    assert not r19_internal_gate(metrics)


def test_delta_checkpoint_binds_parent_sha(tmp_path):
    root = _root()
    parent_path = root / 'checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt'
    head = FrontierRolloutHead()
    path = tmp_path / 'delta.pt'
    meta = save_r19_delta(
        path,
        head,
        parent_checkpoint=parent_path,
        parent_effective_parameters=76_619_419,
        report={'gate': 'unit'},
    )
    assert meta['candidate_effective_parameters'] < 79_000_000
    loaded, loaded_meta = load_r19_delta(path, expected_parent_checkpoint=parent_path)
    assert loaded_meta['parent_sha256'] == meta['parent_sha256']
    for key, value in head.state_dict().items():
        torch.testing.assert_close(loaded.state_dict()[key], value)

    wrong_parent = tmp_path / 'wrong.pt'
    wrong_parent.write_bytes(b'not the parent')
    with pytest.raises(ValueError, match='parent checkpoint SHA-256 mismatch'):
        load_r19_delta(path, expected_parent_checkpoint=wrong_parent)
