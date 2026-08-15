import torch

from cogcoder.r27_codeworld_curriculum import (
    build_curriculum,
    split_by_language_task_pair,
)
from cogcoder.r27_codeworld_controller import CodeWorldControllerConfig


def test_curriculum_covers_languages_task_types_and_has_holdout_pairs():
    cfg = CodeWorldControllerConfig()
    rows = build_curriculum(seed=27, episodes_per_pair=5, config=cfg)
    assert len(rows) > 200
    assert len({row.language_id for row in rows}) >= 8
    assert len({row.task_type_id for row in rows}) >= 6
    train, heldout = split_by_language_task_pair(rows)
    assert train and heldout
    train_pairs = {(r.language_id, r.task_type_id) for r in train}
    heldout_pairs = {(r.language_id, r.task_type_id) for r in heldout}
    assert train_pairs.isdisjoint(heldout_pairs)
    sample = rows[0]
    assert sample.state_features.shape == (cfg.state_dim,)
    assert sample.action_features.shape == (len(sample.action_kinds), cfg.action_feature_dim)
    assert sample.history_features.ndim == 2
    assert sample.target_action in sample.action_kinds
    assert torch.isfinite(sample.state_features).all()
