from pathlib import Path

import pytest
import torch

from cogcoder.neural_system2 import NeuralSystem2Workspace, system2_parameter_count
from cogcoder.r17_training import load_r17_checkpoint
from cogcoder.r18_benchmark import make_r18_task
from cogcoder.r18_training import (
    collect_conditional_law_episode,
    conditional_law_trainable_parameter_names,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _model():
    root = _root()
    return load_r17_checkpoint(
        root / "checkpoints/Nolane-R1.7-NCPM-OperatorExecutor.pt",
        expected_r1_2_checkpoint=root / "checkpoints/Nolane-Rebuild-R1.2-ACE.pt",
        expected_r1_6_parent_checkpoint=root / "checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt",
    )[0]


def test_phase_c_checkpoint_loads_with_conditional_law_prior_neutral_and_under_budget():
    model = _model()
    names = conditional_law_trainable_parameter_names(model)
    assert names and all(name.startswith("conditional_law_") for name in names)
    old_effective = 75_387_546
    new_effective = 49_528_677 + system2_parameter_count(model)
    assert old_effective < new_effective < old_effective + 4_000_000
    assert new_effective < 96_000_000

    batch, actions = 2, 4
    out = model.conditional_law_scores(
        torch.randn(batch, 128),
        torch.randn(batch, 64),
        torch.randn(batch, actions, 640),
        torch.zeros(batch, actions, 128),
        torch.zeros(batch, actions, 3),
    )
    assert out["predicted_effect"].shape == (batch, actions, 128)
    assert out["confidence"].shape == (batch, actions)
    assert torch.count_nonzero(out["predicted_effect"]) == 0


def test_conditional_law_scores_are_action_permutation_equivariant():
    torch.manual_seed(18)
    model = _model().eval()
    state = torch.randn(1, 128)
    context = torch.randn(1, 64)
    actions = torch.randn(1, 5, 640)
    evidence = torch.randn(1, 5, 128)
    meta = torch.rand(1, 5, 3)
    base = model.conditional_law_scores(state, context, actions, evidence, meta)
    perm = torch.tensor([3, 0, 4, 1, 2])
    moved = model.conditional_law_scores(state, context, actions[:, perm], evidence[:, perm], meta[:, perm])
    assert torch.allclose(moved["predicted_effect"], base["predicted_effect"][:, perm], atol=1e-6)
    assert torch.allclose(moved["confidence"], base["confidence"][:, perm], atol=1e-6)


def test_conditional_law_collector_is_train_only_and_emits_counterfactual_public_targets():
    model = _model().eval()
    episode = collect_conditional_law_episode(
        model,
        make_r18_task("conditional_regimes", "train", 0),
        exploration_steps=4,
        max_steps=10,
    )
    assert episode.steps
    row = episode.steps[0]
    assert row.state_sketch.shape == (128,)
    assert row.context_fingerprint.shape == (64,)
    assert row.action_embeddings.ndim == 2 and row.action_embeddings.shape[-1] == 640
    assert row.evidence_effects.shape == row.target_effects.shape
    assert row.evidence_meta.shape == (row.action_embeddings.shape[0], 3)
    assert row.predict_mask.dtype == torch.bool
    assert row.predict_mask.sum() >= 3
    assert torch.isfinite(row.target_effects[row.predict_mask]).all()

    with pytest.raises(ValueError, match="train split"):
        collect_conditional_law_episode(model, make_r18_task("conditional_regimes", "dev", 0))
    with pytest.raises(ValueError, match="train split"):
        collect_conditional_law_episode(model, make_r18_task("regime_switch", "fresh", 0))
