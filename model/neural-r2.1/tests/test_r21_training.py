from __future__ import annotations

import math
from pathlib import Path

import pytest
import torch
from torch import nn

from cogcoder.r21_recursive_core import RecursiveLatentIntelligenceCore
from cogcoder.r21_training import (
    R21DistillationTargets,
    configure_r21_training,
    r21_distillation_loss,
    sample_reasoning_steps,
)


def _inputs(batch: int = 3, actions: int = 5) -> dict[str, torch.Tensor]:
    g = torch.Generator().manual_seed(2102)
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


def test_reasoning_depth_sampler_is_bounded_and_reproducible() -> None:
    g1 = torch.Generator().manual_seed(1)
    g2 = torch.Generator().manual_seed(1)
    a = [sample_reasoning_steps(generator=g1) for _ in range(50)]
    b = [sample_reasoning_steps(generator=g2) for _ in range(50)]
    assert a == b
    assert min(a) >= 1 and max(a) <= 6
    assert len(set(a)) > 1


def test_proof_weighted_distillation_loss_is_finite_and_backpropagates() -> None:
    torch.manual_seed(21)
    model = RecursiveLatentIntelligenceCore()
    x = _inputs()
    out = model(reasoning_steps=6, **x)
    teacher = x["base_action_logits"] + torch.tensor([[2.,0,0,0,0],[0,2.,0,0,0],[0,0,2.,0,0]])
    targets = R21DistillationTargets(
        target_action=torch.tensor([0, 1, 2]),
        teacher_action_logits=teacher,
        proof_weight=torch.tensor([1.0, 0.5, 0.8]),
        progress_target=torch.tensor([0.9, 0.5, 0.2]),
        uncertainty_target=torch.tensor([0.1, 0.3, 0.7]),
        stop_target=torch.tensor([1.0, 0.0, 0.0]),
        required_reasoning_steps=torch.tensor([2, 4, 6]),
    )
    result = r21_distillation_loss(out, targets)
    assert torch.isfinite(result["loss"])
    assert float(result["loss"].detach()) > 0.0
    assert float(result["monotonic_depth_loss"].detach()) >= 0.0
    result["loss"].backward()
    grads = [p.grad for p in model.parameters() if p.grad is not None]
    assert grads and all(torch.isfinite(g).all() for g in grads)


def test_zero_proof_weight_removes_sample_from_policy_supervision() -> None:
    model = RecursiveLatentIntelligenceCore()
    x = _inputs(batch=2, actions=3)
    out = model(reasoning_steps=2, **x)
    targets_a = R21DistillationTargets(
        target_action=torch.tensor([0, 1]),
        teacher_action_logits=torch.randn(2, 3),
        proof_weight=torch.tensor([1.0, 0.0]),
        required_reasoning_steps=torch.tensor([1, 2]),
    )
    targets_b = R21DistillationTargets(
        target_action=torch.tensor([0, 2]),
        teacher_action_logits=torch.randn(2, 3) * 100,
        proof_weight=torch.tensor([1.0, 0.0]),
        required_reasoning_steps=torch.tensor([1, 2]),
    )
    # First sample teacher differs too, so compare hard-label component only.
    a = r21_distillation_loss(out, targets_a, teacher_kl_weight=0.0)
    b = r21_distillation_loss(out, targets_b, teacher_kl_weight=0.0)
    torch.testing.assert_close(a["hard_policy_loss"], b["hard_policy_loss"])


def test_training_stages_freeze_then_release_upstream_weights() -> None:
    core = RecursiveLatentIntelligenceCore()
    upstream = nn.Sequential(nn.Linear(4, 4), nn.Linear(4, 4))
    warm = configure_r21_training(core, upstream_modules=(upstream,), stage="warmup")
    assert warm["core_trainable_parameters"] > 0
    assert warm["upstream_trainable_parameters"] == 0
    assert all(p.requires_grad for p in core.parameters())
    assert not any(p.requires_grad for p in upstream.parameters())
    joint = configure_r21_training(core, upstream_modules=(upstream,), stage="joint")
    assert joint["upstream_trainable_parameters"] > 0
    assert all(p.requires_grad for p in upstream.parameters())


def test_invalid_required_depth_fails_closed() -> None:
    model = RecursiveLatentIntelligenceCore()
    out = model(reasoning_steps=3, **_inputs(batch=1, actions=3))
    targets = R21DistillationTargets(
        target_action=torch.tensor([0]),
        teacher_action_logits=torch.zeros(1, 3),
        proof_weight=torch.ones(1),
        required_reasoning_steps=torch.tensor([4]),
    )
    with pytest.raises(ValueError):
        r21_distillation_loss(out, targets)


def test_train_step_earns_nonzero_residual_policy_update() -> None:
    from cogcoder.r21_training import make_r21_optimizer, train_r21_step

    torch.manual_seed(21)
    model = RecursiveLatentIntelligenceCore()
    x = _inputs(batch=2, actions=4)
    targets = R21DistillationTargets(
        target_action=torch.tensor([1, 2]),
        teacher_action_logits=torch.tensor([[0.0, 3.0, 0.0, 0.0], [0.0, 0.0, 3.0, 0.0]]),
        proof_weight=torch.ones(2),
        required_reasoning_steps=torch.tensor([2, 3]),
    )
    before = model.action_residual_head.weight.detach().clone()
    optimizer = make_r21_optimizer(model, stage="warmup", core_lr=1e-3)
    metrics = train_r21_step(model, x, targets, optimizer, reasoning_steps=3)
    assert math.isfinite(metrics["loss"]) and math.isfinite(metrics["grad_norm"])
    assert not torch.equal(before, model.action_residual_head.weight.detach())
