from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import torch
from torch import Tensor, nn

from .multidepth import MultiDepthObjective


@dataclass(frozen=True)
class VerifiedMultiDepthTargets:
    expert_actions: Tensor
    proof_weight: Tensor

    def validate(self, *, batch: int) -> None:
        if self.expert_actions.shape != (batch,) or self.expert_actions.dtype != torch.long:
            raise ValueError("expert_actions must be int64 [batch]")
        if self.proof_weight.shape != (batch,):
            raise ValueError("proof_weight must be [batch]")
        if not torch.is_floating_point(self.proof_weight):
            raise ValueError("proof_weight must be floating point")
        if torch.any(~torch.isfinite(self.proof_weight)) or torch.any(self.proof_weight < 0):
            raise ValueError("proof_weight must be finite and non-negative")
        if not bool((self.proof_weight > 0).any()):
            raise ValueError("at least one sample must carry positive proof weight")


def sample_multidepth_steps(
    *,
    generator: torch.Generator | None = None,
    min_steps: int = 2,
    max_steps: int = 4,
) -> int:
    if type(min_steps) is not int or type(max_steps) is not int:
        raise ValueError("reasoning-depth bounds must be exact integers")
    if min_steps < 2 or max_steps < min_steps:
        raise ValueError("vNext multi-depth curriculum requires 2 <= min_steps <= max_steps")
    return int(torch.randint(min_steps, max_steps + 1, (1,), generator=generator).item())


def configure_vnext_training(reasoner: nn.Module, *, stage: str = "depth_warmup") -> dict[str, int | str]:
    if stage not in {"depth_warmup", "joint_reasoner"}:
        raise ValueError("stage must be 'depth_warmup' or 'joint_reasoner'")

    for parameter in reasoner.parameters():
        parameter.requires_grad_(stage == "joint_reasoner")

    if stage == "depth_warmup":
        trainable_prefixes = (
            "reasoning_cell.",
            "action_residual_head.",
            "action_value_head.",
            "repair_gate_head.",
            "parent_correct_head.",
            "action_compatibility_head.",
            "ponder_head.",
            "progress_head.",
            "uncertainty_head.",
            "stop_head.",
            "success_head.",
        )
        for name, parameter in reasoner.named_parameters():
            if name.startswith(trainable_prefixes):
                parameter.requires_grad_(True)

    trainable = sum(parameter.numel() for parameter in reasoner.parameters() if parameter.requires_grad)
    frozen = sum(parameter.numel() for parameter in reasoner.parameters() if not parameter.requires_grad)
    if trainable < 1:
        raise ValueError("training stage selected no trainable neural parameters")
    return {
        "stage": stage,
        "trainable_parameters": trainable,
        "frozen_parameters": frozen,
    }


def make_vnext_optimizer(
    reasoner: nn.Module,
    *,
    stage: str = "depth_warmup",
    learning_rate: float = 2e-4,
    weight_decay: float = 0.01,
) -> torch.optim.Optimizer:
    if not isinstance(learning_rate, (int, float)) or isinstance(learning_rate, bool) or float(learning_rate) <= 0:
        raise ValueError("learning_rate must be positive")
    if not isinstance(weight_decay, (int, float)) or isinstance(weight_decay, bool) or float(weight_decay) < 0:
        raise ValueError("weight_decay must be non-negative")
    configure_vnext_training(reasoner, stage=stage)
    parameters = [parameter for parameter in reasoner.parameters() if parameter.requires_grad]
    return torch.optim.AdamW(parameters, lr=float(learning_rate), weight_decay=float(weight_decay))


def _slice_verified_inputs(
    inputs: Mapping[str, Tensor],
    verified: Tensor,
    *,
    batch: int,
) -> dict[str, Tensor]:
    result: dict[str, Tensor] = {}
    for name, value in inputs.items():
        if not isinstance(value, Tensor):
            raise ValueError(f"{name} must be a tensor")
        if value.ndim < 1 or value.shape[0] != batch:
            raise ValueError(f"{name} must carry batch as its first dimension")
        result[name] = value[verified]
    return result


def train_vnext_step(
    reasoner: nn.Module,
    inputs: Mapping[str, Tensor],
    targets: VerifiedMultiDepthTargets,
    optimizer: torch.optim.Optimizer,
    *,
    reasoning_steps: int,
    objective: MultiDepthObjective | None = None,
    max_grad_norm: float = 1.0,
) -> dict[str, float]:
    if type(reasoning_steps) is not int or reasoning_steps < 2:
        raise ValueError("vNext training requires at least two reasoning steps")
    if not isinstance(max_grad_norm, (int, float)) or isinstance(max_grad_norm, bool) or float(max_grad_norm) <= 0:
        raise ValueError("max_grad_norm must be positive")
    if "state" not in inputs:
        raise ValueError("training inputs require state")
    batch = int(inputs["state"].shape[0])
    targets.validate(batch=batch)

    verified = targets.proof_weight > 0
    filtered_inputs = _slice_verified_inputs(inputs, verified, batch=batch)
    filtered_actions = targets.expert_actions[verified]
    filtered_weights = targets.proof_weight[verified]
    if not bool(torch.all(filtered_weights.eq(filtered_weights[0]))):
        raise ValueError(
            "current vNext trainer accepts only equal positive proof weights; "
            "pre-normalize or stratify batches instead of silently changing evidence authority"
        )

    reasoner.train()
    optimizer.zero_grad(set_to_none=True)
    output = reasoner(**filtered_inputs, reasoning_steps=reasoning_steps)
    losses = (objective or MultiDepthObjective())(
        output,
        expert_actions=filtered_actions,
        base_action_logits=filtered_inputs["base_action_logits"],
    )
    losses["loss"].backward()
    trainable = [
        parameter
        for parameter in reasoner.parameters()
        if parameter.requires_grad and parameter.grad is not None
    ]
    grad_norm = torch.nn.utils.clip_grad_norm_(trainable, max_norm=float(max_grad_norm))
    optimizer.step()

    metrics = {
        name: float(value.detach().cpu())
        for name, value in losses.items()
        if value.ndim == 0
    }
    metrics["grad_norm"] = float(torch.as_tensor(grad_norm).detach().cpu())
    metrics["reasoning_steps"] = float(reasoning_steps)
    metrics["verified_samples"] = float(verified.sum().item())
    return metrics
