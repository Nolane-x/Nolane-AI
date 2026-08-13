from pathlib import Path

import torch

from cogcoder.neural_system2 import NeuralSystem2Workspace, system2_parameter_count
from cogcoder.r17_training import load_r17_checkpoint


def _root():
    return Path(__file__).resolve().parents[1]


def test_crgm_is_policy_neutral_at_initialization():
    torch.manual_seed(17071)
    model = NeuralSystem2Workspace()
    need = torch.randn(2, 64)
    role_conf = torch.ones(2)
    laws = torch.randn(2, 4, model.causal_law_dim)
    law_conf = torch.rand(2, 4)
    out = model.causal_role_goal_scores(need, role_conf, laws, law_conf)
    assert out["predicted_progress"].shape == (2, 4)
    assert out["policy_bonus"].shape == (2, 4)
    assert torch.count_nonzero(out["policy_bonus"]) == 0


def test_crgm_is_action_permutation_equivariant():
    torch.manual_seed(17072)
    model = NeuralSystem2Workspace()
    need = torch.randn(1, 64)
    role_conf = torch.ones(1)
    laws = torch.randn(1, 5, model.causal_law_dim)
    law_conf = torch.rand(1, 5)
    base = model.causal_role_goal_scores(need, role_conf, laws, law_conf)
    perm = torch.tensor([4, 1, 3, 0, 2])
    moved = model.causal_role_goal_scores(need, role_conf, laws[:, perm], law_conf[:, perm])
    assert torch.allclose(moved["predicted_progress"], base["predicted_progress"][:, perm], atol=1e-6)
    assert torch.allclose(moved["policy_bonus"], base["policy_bonus"][:, perm], atol=1e-6)


def test_crgm_refuses_role_or_law_without_confidence():
    model = NeuralSystem2Workspace()
    need = torch.randn(1, 64)
    laws = torch.randn(1, 3, model.causal_law_dim)
    out_role = model.causal_role_goal_scores(need, torch.zeros(1), laws, torch.ones(1, 3))
    out_law = model.causal_role_goal_scores(need, torch.ones(1), laws, torch.zeros(1, 3))
    assert torch.count_nonzero(out_role["predicted_progress"]) == 0
    assert torch.count_nonzero(out_law["predicted_progress"]) == 0


def test_goal_difference_checkpoint_loads_with_crgm_neutral_and_under_ceiling():
    root = _root()
    model, meta = load_r17_checkpoint(
        root / "checkpoints/Nolane-R1.7-NCPM-GoalDifference.pt",
        expected_r1_2_checkpoint=root / "checkpoints/Nolane-Rebuild-R1.2-ACE.pt",
        expected_r1_6_parent_checkpoint=root / "checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt",
    )
    assert float(model.causal_role_goal_policy_scale.detach()) == 0.0
    assert meta["candidate_effective_parameters"] == 74_660_997
    effective = 49_528_677 + system2_parameter_count(model)
    assert effective < 96_000_000
    assert effective > meta["candidate_effective_parameters"]
