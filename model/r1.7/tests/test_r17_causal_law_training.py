from pathlib import Path

import pytest
import torch

from cogcoder.neural_system2 import NeuralSystem2Workspace
from cogcoder.r17_benchmark import make_r17_task
from cogcoder.r17_training import (
    R17_PARAMETER_CEILING,
    causal_law_trainable_parameter_names,
    collect_causal_law_episode,
    load_r17_checkpoint,
    save_r17_checkpoint,
)


def _r12_checkpoint() -> Path:
    return Path(__file__).resolve().parents[1] / "checkpoints" / "Nolane-Rebuild-R1.2-ACE.pt"


def _r16_parent() -> Path:
    return Path(__file__).resolve().parents[1] / "checkpoints" / "Nolane-R1.6-NS2-EffectProgressCritic.pt"


def test_r17_causal_law_optimizer_scope_excludes_parent_policy_and_policy_residual():
    model = NeuralSystem2Workspace()
    names = causal_law_trainable_parameter_names(model, include_policy=False)
    assert names
    assert all(name.startswith("causal_law_") for name in names)
    assert "causal_law_policy_scale" not in names
    assert all(not name.startswith("causal_law_policy_head.") for name in names)
    assert all("effect_progress" not in name for name in names)


def test_causal_law_collector_rejects_nontrain_splits():
    model = NeuralSystem2Workspace()
    with pytest.raises(ValueError, match="train split"):
        collect_causal_law_episode(model, make_r17_task("causal_laws", "dev", 0))
    with pytest.raises(ValueError, match="train split"):
        collect_causal_law_episode(model, make_r17_task("causal_switch", "fresh", 0))


def test_causal_law_collector_emits_public_counterfactual_targets():
    torch.manual_seed(17)
    model = NeuralSystem2Workspace()
    episode = collect_causal_law_episode(
        model,
        make_r17_task("causal_laws", "train", 0),
        exploration_steps=4,
    )
    assert episode.steps
    first = episode.steps[0]
    assert first.state_sketch.shape == (128,)
    assert first.action_embeddings.ndim == 2
    assert first.target_deltas.shape[0] == first.action_embeddings.shape[0]
    assert first.target_deltas.shape[1] == 128
    assert first.predict_mask.dtype == torch.bool
    assert first.predict_mask.sum().item() >= 3
    assert 0 <= first.executed_action < first.action_embeddings.shape[0]
    assert torch.count_nonzero(first.baseline_deltas) == 0


def test_r17_checkpoint_roundtrip_binds_r16_parent_and_ceiling(tmp_path: Path):
    torch.manual_seed(29)
    model = NeuralSystem2Workspace()
    path = tmp_path / "r17.pt"
    meta = save_r17_checkpoint(
        path,
        model,
        r1_2_checkpoint=_r12_checkpoint(),
        r1_6_parent_checkpoint=_r16_parent(),
        report={"internal": "test"},
    )
    loaded, loaded_meta = load_r17_checkpoint(
        path,
        expected_r1_2_checkpoint=_r12_checkpoint(),
        expected_r1_6_parent_checkpoint=_r16_parent(),
    )
    assert loaded_meta["candidate_effective_parameters"] < R17_PARAMETER_CEILING
    assert loaded_meta["r1_6_parent_sha256"] == meta["r1_6_parent_sha256"]
    for name, value in model.state_dict().items():
        assert torch.equal(value, loaded.state_dict()[name])
