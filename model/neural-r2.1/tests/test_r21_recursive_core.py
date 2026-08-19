from __future__ import annotations

import pytest
import torch

from cogcoder.r21_recursive_core import (
    MAX_R21_DELTA_PARAMETERS,
    RecursiveLatentIntelligenceCore,
    r21_parameter_count,
)


def _inputs(batch: int = 2, actions: int = 5) -> dict[str, torch.Tensor]:
    g = torch.Generator().manual_seed(2101)
    return {
        "state": torch.randn(batch, 128, generator=g),
        "context": torch.randn(batch, 64, generator=g),
        "action_embeddings": torch.randn(batch, actions, 640, generator=g),
        "parent_effects": torch.randn(batch, actions, 128, generator=g),
        "imagined_effects": torch.randn(batch, actions, 128, generator=g),
        "evidence_effects": torch.randn(batch, actions, 128, generator=g),
        "action_memory": torch.randn(batch, actions, 7, generator=g),
        "imagined_uncertainty": torch.rand(batch, actions, generator=g),
        "imagined_value": torch.randn(batch, actions, generator=g),
        "base_action_logits": torch.randn(batch, actions, generator=g),
        "progress": torch.rand(batch, 1, generator=g),
        "budget_fraction": torch.rand(batch, 1, generator=g),
        "previous_feedback": torch.randn(batch, 3, generator=g),
        "base_stop_logit": torch.randn(batch, generator=g),
        "base_success_probability": torch.rand(batch, generator=g) * 0.8 + 0.1,
    }


def test_parameter_budget_and_shared_recursive_cell() -> None:
    model = RecursiveLatentIntelligenceCore()
    assert r21_parameter_count(model) <= MAX_R21_DELTA_PARAMETERS
    names = dict(model.named_modules())
    assert "reasoning_cell" in names
    assert not any(name.startswith("reasoning_cells.") for name in names)


def test_shapes_and_arbitrary_runtime_depth() -> None:
    torch.manual_seed(21)
    model = RecursiveLatentIntelligenceCore()
    x = _inputs()
    for steps in (1, 8, 12):
        out = model(reasoning_steps=steps, **x)
        assert out["action_logits"].shape == (2, 5)
        assert out["effect_residuals"].shape == (2, 5, 128)
        assert out["latent_state"].shape == (2, model.latent_dim)
        assert out["latent_trajectory"].shape == (2, steps, model.latent_dim)
        assert out["action_logits_trajectory"].shape == (2, steps, 5)
        for key in ("progress_prediction", "uncertainty", "stop_logit", "ponder_logit"):
            assert out[key].shape == (2,)
            assert torch.isfinite(out[key]).all()


def test_action_permutation_equivariance_and_global_invariance() -> None:
    torch.manual_seed(21)
    model = RecursiveLatentIntelligenceCore().eval()
    x = _inputs(batch=2, actions=6)
    a = model(reasoning_steps=4, **x)
    order = torch.tensor([4, 0, 5, 2, 1, 3])
    y = dict(x)
    for key in (
        "action_embeddings",
        "parent_effects",
        "imagined_effects",
        "evidence_effects",
        "action_memory",
        "imagined_uncertainty",
        "imagined_value",
        "base_action_logits",
    ):
        y[key] = x[key][:, order]
    b = model(reasoning_steps=4, **y)
    torch.testing.assert_close(b["action_logits"], a["action_logits"][:, order], rtol=1e-5, atol=1e-6)
    torch.testing.assert_close(b["effect_residuals"], a["effect_residuals"][:, order], rtol=1e-5, atol=1e-6)
    for key in ("latent_state", "progress_prediction", "uncertainty", "stop_logit", "ponder_logit"):
        torch.testing.assert_close(b[key], a[key], rtol=1e-5, atol=1e-6)


def test_zero_residual_initialization_preserves_upstream_action_policy() -> None:
    torch.manual_seed(21)
    model = RecursiveLatentIntelligenceCore().eval()
    x = _inputs()
    out = model(reasoning_steps=6, **x)
    torch.testing.assert_close(out["action_logits"], x["base_action_logits"], rtol=0, atol=0)
    torch.testing.assert_close(out["effect_residuals"], torch.zeros_like(out["effect_residuals"]), rtol=0, atol=0)
    torch.testing.assert_close(out["stop_logit"], x["base_stop_logit"], rtol=0, atol=0)
    torch.testing.assert_close(out["success_probability"], x["base_success_probability"], rtol=1e-6, atol=1e-7)


def test_gradients_flow_through_twelve_shared_reasoning_steps() -> None:
    torch.manual_seed(21)
    model = RecursiveLatentIntelligenceCore()
    x = _inputs(batch=2, actions=4)
    out = model(reasoning_steps=12, **x)
    loss = (
        out["latent_state"].square().mean()
        + out["progress_prediction"].mean()
        + out["uncertainty"].mean()
        + out["stop_logit"].mean()
        + out["ponder_logit"].mean()
    )
    loss.backward()
    grads = [p.grad for p in model.parameters() if p.requires_grad and p.grad is not None]
    assert grads
    assert all(torch.isfinite(g).all() for g in grads)
    assert any(float(g.abs().sum()) > 0.0 for g in grads)


def test_invalid_shapes_and_depth_fail_closed() -> None:
    model = RecursiveLatentIntelligenceCore()
    x = _inputs()
    with pytest.raises(ValueError):
        model(reasoning_steps=0, **x)
    bad = dict(x)
    bad["state"] = torch.randn(2, 127)
    with pytest.raises(ValueError):
        model(reasoning_steps=1, **bad)
