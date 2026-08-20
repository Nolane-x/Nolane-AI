from __future__ import annotations

import torch
from torch import nn

from cogcoder.r21_adapter import R20iRecursiveLatentPolicy
from cogcoder.r21_recursive_core import RecursiveLatentIntelligenceCore


class FakeR20eExecutive(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.bias = nn.Parameter(torch.tensor(0.25))

    def forward(self, *, state, action_embeddings, recurrent_state, **kwargs):
        batch, actions, _ = action_embeddings.shape
        logits = action_embeddings[..., 0] + self.bias
        stop = state[:, 0] + self.bias
        success = torch.sigmoid(state[:, 1] + self.bias)
        return {
            "action_logits": logits,
            "next_state": recurrent_state + 1.0,
            "stop_logit": stop,
            "success_probability": success,
            "depth_logits": torch.zeros(batch, 5, device=state.device, dtype=state.dtype),
        }


def _inputs(batch=2, actions=4):
    g = torch.Generator().manual_seed(2103)
    return {
        "state": torch.randn(batch, 128, generator=g),
        "context": torch.randn(batch, 64, generator=g),
        "action_embeddings": torch.randn(batch, actions, 640, generator=g),
        "parent_effects": torch.randn(batch, actions, 128, generator=g),
        "imagined_effects": torch.randn(batch, actions, 128, generator=g),
        "imagined_uncertainty": torch.rand(batch, actions, generator=g),
        "imagined_value": torch.randn(batch, actions, generator=g),
        "evidence_effects": torch.randn(batch, actions, 128, generator=g),
        "action_memory": torch.randn(batch, actions, 7, generator=g),
        "progress": torch.rand(batch, 1, generator=g),
        "budget_fraction": torch.rand(batch, 1, generator=g),
        "previous_feedback": torch.randn(batch, 3, generator=g),
        "recurrent_state": torch.zeros(batch, 192),
    }


def test_adapter_is_exact_r20e_policy_noop_at_initialization() -> None:
    torch.manual_seed(21)
    base = FakeR20eExecutive()
    policy = R20iRecursiveLatentPolicy(base, RecursiveLatentIntelligenceCore()).eval()
    x = _inputs()
    with torch.no_grad():
        parent = base(**x)
        out = policy(reasoning_steps=8, **x)
    torch.testing.assert_close(out["action_logits"], parent["action_logits"], rtol=0, atol=0)
    torch.testing.assert_close(out["stop_logit"], parent["stop_logit"], rtol=0, atol=0)
    torch.testing.assert_close(out["success_probability"], parent["success_probability"], rtol=1e-6, atol=1e-7)
    torch.testing.assert_close(out["next_state"], parent["next_state"])
    assert out["reasoning_steps"] == 8


def test_adapter_joint_gradient_can_reach_base_and_recursive_core() -> None:
    torch.manual_seed(21)
    base = FakeR20eExecutive()
    core = RecursiveLatentIntelligenceCore()
    policy = R20iRecursiveLatentPolicy(base, core)
    out = policy(reasoning_steps=3, **_inputs())
    loss = out["latent_state"].square().mean() + out["action_logits"].sum()
    loss.backward()
    assert base.bias.grad is not None and torch.isfinite(base.bias.grad)
    assert any(p.grad is not None and torch.isfinite(p.grad).all() for p in core.parameters())
