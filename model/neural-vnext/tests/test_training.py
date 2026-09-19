from __future__ import annotations

import sys
from pathlib import Path

import torch

HERE = Path(__file__).resolve()
VNEXT_ROOT = HERE.parents[1]
MODEL_ROOT = HERE.parents[2]
R23_ROOT = MODEL_ROOT / "neural-r2.3"
for path in (VNEXT_ROOT, R23_ROOT):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from nvnext.training import (  # noqa: E402
    VerifiedMultiDepthTargets,
    configure_vnext_training,
    make_vnext_optimizer,
    sample_multidepth_steps,
    train_vnext_step,
)
from r23.ultra_core import ScaledRecursiveDistilledReasoner  # noqa: E402


def _inputs(batch: int = 3, actions: int = 4) -> dict[str, torch.Tensor]:
    return dict(
        state=torch.randn(batch, 128),
        context=torch.randn(batch, 64),
        action_embeddings=torch.randn(batch, actions, 640),
        parent_effects=torch.randn(batch, actions, 128),
        imagined_effects=torch.randn(batch, actions, 128),
        evidence_effects=torch.randn(batch, actions, 128),
        action_memory=torch.randn(batch, actions, 7),
        imagined_uncertainty=torch.rand(batch, actions),
        imagined_value=torch.randn(batch, actions),
        base_action_logits=torch.randn(batch, actions),
        progress=torch.rand(batch, 1),
        budget_fraction=torch.rand(batch, 1),
        previous_feedback=torch.randn(batch, 3),
        base_stop_logit=torch.zeros(batch),
        base_success_probability=torch.full((batch,), 0.5),
    )


def test_multidepth_curriculum_sampling_is_bounded_and_reproducible() -> None:
    a = torch.Generator().manual_seed(17)
    b = torch.Generator().manual_seed(17)
    left = [sample_multidepth_steps(generator=a) for _ in range(12)]
    right = [sample_multidepth_steps(generator=b) for _ in range(12)]

    assert left == right
    assert set(left).issubset({2, 3, 4})
    assert len(set(left)) > 1


def test_depth_warmup_trains_recurrence_and_ponder_without_unfreezing_input_projections() -> None:
    model = ScaledRecursiveDistilledReasoner(latent_dim=192, n_heads=6, ff_mult=2)

    state = configure_vnext_training(model, stage="depth_warmup")

    assert state["trainable_parameters"] > 0
    assert state["frozen_parameters"] > 0
    assert model.reasoning_cell.query.weight.requires_grad
    assert model.ponder_head.weight.requires_grad
    assert not model.state_projection.weight.requires_grad
    assert not model.action_projection.weight.requires_grad


def test_train_step_updates_recurrent_parameters_from_verified_examples_only() -> None:
    torch.manual_seed(23)
    model = ScaledRecursiveDistilledReasoner(latent_dim=192, n_heads=6, ff_mult=2)
    optimizer = make_vnext_optimizer(
        model,
        stage="depth_warmup",
        learning_rate=5e-4,
        weight_decay=0.0,
    )
    values = _inputs()
    targets = VerifiedMultiDepthTargets(
        expert_actions=torch.tensor([1, 2, 0], dtype=torch.long),
        proof_weight=torch.tensor([1.0, 1.0, 0.0]),
    )
    before = model.reasoning_cell.query.weight.detach().clone()

    metrics = train_vnext_step(
        model,
        values,
        targets,
        optimizer,
        reasoning_steps=3,
    )

    after = model.reasoning_cell.query.weight.detach()
    assert metrics["verified_samples"] == 2.0
    assert metrics["reasoning_steps"] == 3.0
    assert metrics["grad_norm"] > 0.0
    assert not torch.equal(before, after)


def test_train_step_rejects_batch_without_verified_neural_teacher_evidence() -> None:
    model = ScaledRecursiveDistilledReasoner(latent_dim=192, n_heads=6, ff_mult=2)
    optimizer = make_vnext_optimizer(model, stage="depth_warmup")
    targets = VerifiedMultiDepthTargets(
        expert_actions=torch.tensor([1, 2, 0], dtype=torch.long),
        proof_weight=torch.zeros(3),
    )

    try:
        train_vnext_step(model, _inputs(), targets, optimizer, reasoning_steps=3)
    except ValueError as exc:
        assert "positive proof weight" in str(exc)
    else:
        raise AssertionError("unverified batches must not train the Neural Core")
