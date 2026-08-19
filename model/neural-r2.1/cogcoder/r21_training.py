from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch
from torch import Tensor, nn
import torch.nn.functional as F

from .r21_recursive_core import RecursiveLatentIntelligenceCore


@dataclass(frozen=True)
class R21DistillationTargets:
    """Proof-weighted teacher targets for neuralizing external reasoning.

    proof_weight is deliberately explicit. Unverified or heuristic trajectories
    can be assigned zero weight, preventing them from silently becoming neural
    authority merely because they were emitted by a runtime teacher.
    """

    target_action: Tensor
    teacher_action_logits: Tensor
    proof_weight: Tensor
    required_reasoning_steps: Tensor
    effect_residual_target: Tensor | None = None
    progress_target: Tensor | None = None
    uncertainty_target: Tensor | None = None
    stop_target: Tensor | None = None
    success_target: Tensor | None = None


def sample_reasoning_steps(
    *,
    generator: torch.Generator | None = None,
    min_steps: int = 1,
    max_steps: int = 6,
) -> int:
    if min_steps < 1 or max_steps < min_steps:
        raise ValueError("invalid reasoning-depth range")
    return int(torch.randint(min_steps, max_steps + 1, (1,), generator=generator).item())


def configure_r21_training(
    core: RecursiveLatentIntelligenceCore,
    *,
    upstream_modules: Sequence[nn.Module] = (),
    stage: str = "warmup",
) -> dict[str, int | str]:
    """Two-stage training: learn the delta first, then permit joint adaptation.

    The joint stage is intentionally explicit instead of assuming the old
    ~79M neural stack is permanently frozen. This allows the recursive core to
    reshape upstream representations once the residual path is stable.
    """

    if stage not in {"warmup", "joint"}:
        raise ValueError("stage must be 'warmup' or 'joint'")
    for parameter in core.parameters():
        parameter.requires_grad_(True)
    upstream_trainable = stage == "joint"
    for module in upstream_modules:
        for parameter in module.parameters():
            parameter.requires_grad_(upstream_trainable)
    return {
        "stage": stage,
        "core_trainable_parameters": sum(p.numel() for p in core.parameters() if p.requires_grad),
        "upstream_trainable_parameters": sum(
            p.numel() for module in upstream_modules for p in module.parameters() if p.requires_grad
        ),
    }


def _weighted_mean(values: Tensor, weights: Tensor) -> Tensor:
    if values.ndim < 1 or values.shape[0] != weights.shape[0]:
        raise ValueError("weighted values must have batch as first dimension")
    if weights.ndim != 1 or torch.any(weights < 0):
        raise ValueError("proof_weight must be a non-negative batch vector")
    total = weights.sum()
    if not bool(total > 0):
        raise ValueError("at least one sample must carry positive proof weight")
    per_sample = values.reshape(values.shape[0], -1).mean(dim=1)
    return (per_sample * weights).sum() / total


def _optional_probability_loss(prediction: Tensor, target: Tensor | None, weights: Tensor) -> Tensor:
    if target is None:
        return prediction.new_zeros(())
    if target.shape != prediction.shape:
        raise ValueError("probability target shape mismatch")
    target = target.to(device=prediction.device, dtype=prediction.dtype)
    values = F.binary_cross_entropy(prediction.clamp(1e-6, 1 - 1e-6), target, reduction="none")
    return _weighted_mean(values, weights)


def r21_distillation_loss(
    output: dict[str, Tensor],
    targets: R21DistillationTargets,
    *,
    hard_policy_weight: float = 1.0,
    teacher_kl_weight: float = 0.8,
    anytime_policy_weight: float = 0.35,
    monotonic_depth_weight: float = 0.25,
    ponder_weight: float = 0.20,
    effect_weight: float = 0.35,
    auxiliary_weight: float = 0.20,
    temperature: float = 1.5,
) -> dict[str, Tensor]:
    """Distill verified runtime reasoning while rewarding anytime improvement.

    The loss does not pretend deeper inference is automatically better. It
    explicitly penalizes depth regressions on the supervised action target and
    teaches a ponder head to predict how many recursive iterations the teacher
    evidence says are required.
    """

    logits = output["action_logits"]
    trajectory = output["action_logits_trajectory"]
    if logits.ndim != 2 or trajectory.ndim != 3 or trajectory.shape[0] != logits.shape[0] or trajectory.shape[2] != logits.shape[1]:
        raise ValueError("invalid action-logit output shapes")
    batch, actions = logits.shape
    steps = trajectory.shape[1]
    target_action = targets.target_action.to(device=logits.device, dtype=torch.long)
    teacher_logits = targets.teacher_action_logits.to(device=logits.device, dtype=logits.dtype)
    weights = targets.proof_weight.to(device=logits.device, dtype=logits.dtype)
    required = targets.required_reasoning_steps.to(device=logits.device, dtype=torch.long)
    if target_action.shape != (batch,) or teacher_logits.shape != (batch, actions) or weights.shape != (batch,) or required.shape != (batch,):
        raise ValueError("distillation target shape mismatch")
    if torch.any(required < 1) or torch.any(required > steps):
        raise ValueError("required_reasoning_steps must fall inside emitted trajectory")
    if temperature <= 0:
        raise ValueError("temperature must be positive")

    hard_values = F.cross_entropy(logits, target_action, reduction="none")
    hard_loss = _weighted_mean(hard_values, weights)

    t = float(temperature)
    teacher_prob = torch.softmax(teacher_logits / t, dim=-1)
    student_log_prob = torch.log_softmax(logits / t, dim=-1)
    teacher_kl_values = F.kl_div(student_log_prob, teacher_prob, reduction="none").sum(dim=-1) * (t * t)
    teacher_kl_loss = _weighted_mean(teacher_kl_values, weights)

    repeated_target = target_action[:, None].expand(batch, steps).reshape(-1)
    depth_ce = F.cross_entropy(trajectory.reshape(batch * steps, actions), repeated_target, reduction="none").view(batch, steps)
    anytime_loss = _weighted_mean(depth_ce, weights)
    if steps > 1:
        monotonic_values = F.relu(depth_ce[:, 1:] - depth_ce[:, :-1])
        monotonic_loss = _weighted_mean(monotonic_values, weights)
    else:
        monotonic_loss = logits.new_zeros(())

    ponder_logits = output["ponder_logits_trajectory"]
    if ponder_logits.shape != (batch, steps):
        raise ValueError("ponder trajectory shape mismatch")
    step_numbers = torch.arange(1, steps + 1, device=logits.device).unsqueeze(0)
    ponder_target = (step_numbers < required.unsqueeze(1)).to(dtype=logits.dtype)
    ponder_values = F.binary_cross_entropy_with_logits(ponder_logits, ponder_target, reduction="none")
    ponder_loss = _weighted_mean(ponder_values, weights)

    effect_loss = logits.new_zeros(())
    if targets.effect_residual_target is not None:
        effect_target = targets.effect_residual_target.to(
            device=logits.device, dtype=output["effect_residuals"].dtype
        )
        if effect_target.shape != output["effect_residuals"].shape:
            raise ValueError("effect_residual_target shape mismatch")
        effect_loss = _weighted_mean((output["effect_residuals"] - effect_target).square(), weights)

    progress_loss = _optional_probability_loss(output["progress_prediction"], targets.progress_target, weights)
    uncertainty_loss = _optional_probability_loss(output["uncertainty"], targets.uncertainty_target, weights)
    success_loss = _optional_probability_loss(output["success_probability"], targets.success_target, weights)
    stop_loss = logits.new_zeros(())
    if targets.stop_target is not None:
        stop_target = targets.stop_target.to(device=logits.device, dtype=logits.dtype)
        if stop_target.shape != output["stop_logit"].shape:
            raise ValueError("stop_target shape mismatch")
        stop_values = F.binary_cross_entropy_with_logits(output["stop_logit"], stop_target, reduction="none")
        stop_loss = _weighted_mean(stop_values, weights)
    auxiliary_loss = progress_loss + uncertainty_loss + success_loss + stop_loss

    total = (
        hard_policy_weight * hard_loss
        + teacher_kl_weight * teacher_kl_loss
        + anytime_policy_weight * anytime_loss
        + monotonic_depth_weight * monotonic_loss
        + ponder_weight * ponder_loss
        + effect_weight * effect_loss
        + auxiliary_weight * auxiliary_loss
    )
    return {
        "loss": total,
        "hard_policy_loss": hard_loss,
        "teacher_kl_loss": teacher_kl_loss,
        "anytime_policy_loss": anytime_loss,
        "monotonic_depth_loss": monotonic_loss,
        "ponder_loss": ponder_loss,
        "effect_loss": effect_loss,
        "auxiliary_loss": auxiliary_loss,
    }


def make_r21_optimizer(
    core: RecursiveLatentIntelligenceCore,
    *,
    upstream_modules: Sequence[nn.Module] = (),
    stage: str = "warmup",
    core_lr: float = 3e-4,
    upstream_lr: float = 3e-5,
    weight_decay: float = 0.01,
) -> torch.optim.Optimizer:
    """Build parameter groups with a deliberately slower joint upstream rate."""
    if core_lr <= 0 or upstream_lr <= 0 or weight_decay < 0:
        raise ValueError("invalid optimizer hyperparameters")
    configure_r21_training(core, upstream_modules=upstream_modules, stage=stage)
    groups: list[dict[str, object]] = [
        {"params": [p for p in core.parameters() if p.requires_grad], "lr": float(core_lr)}
    ]
    if stage == "joint":
        upstream = [p for module in upstream_modules for p in module.parameters() if p.requires_grad]
        if upstream:
            groups.append({"params": upstream, "lr": float(upstream_lr)})
    return torch.optim.AdamW(groups, weight_decay=float(weight_decay))


def train_r21_step(
    core: RecursiveLatentIntelligenceCore,
    inputs: dict[str, Tensor],
    targets: R21DistillationTargets,
    optimizer: torch.optim.Optimizer,
    *,
    reasoning_steps: int,
    max_grad_norm: float = 1.0,
) -> dict[str, float]:
    if max_grad_norm <= 0:
        raise ValueError("max_grad_norm must be positive")
    core.train()
    optimizer.zero_grad(set_to_none=True)
    output = core(reasoning_steps=reasoning_steps, **inputs)
    losses = r21_distillation_loss(output, targets)
    losses["loss"].backward()
    grad_norm = torch.nn.utils.clip_grad_norm_(
        [p for p in core.parameters() if p.requires_grad and p.grad is not None],
        max_norm=float(max_grad_norm),
    )
    optimizer.step()
    metrics = {name: float(value.detach().cpu()) for name, value in losses.items()}
    metrics["grad_norm"] = float(torch.as_tensor(grad_norm).detach().cpu())
    metrics["reasoning_steps"] = float(reasoning_steps)
    return metrics
