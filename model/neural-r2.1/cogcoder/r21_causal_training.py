from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch
from torch import Tensor, nn
import torch.nn.functional as F

from .r21_causal_router import CausalEvidenceRouter


@dataclass(frozen=True)
class CausalRouterTargets:
    """Teacher targets for evidence-conditioned neural routing.

    allowed_action_mask is intentionally set-valued. Before public evidence has
    broken an action symmetry, all equivalent legal experiments may be marked
    valid instead of leaking an arbitrary hidden action identity into training.

    role_targets are auxiliary training-only labels. role_supervision_mask must
    exclude hidden roles until they are recoverable from public evidence.
    """

    allowed_action_mask: Tensor
    causal_activation_target: Tensor
    role_targets: Tensor
    role_supervision_mask: Tensor


def set_valued_policy_loss(logits: Tensor, allowed_action_mask: Tensor) -> Tensor:
    if logits.ndim != 2 or allowed_action_mask.shape != logits.shape:
        raise ValueError("allowed_action_mask must match [batch, actions] logits")
    if allowed_action_mask.dtype != torch.bool:
        raise ValueError("allowed_action_mask must be bool")
    if torch.any(~allowed_action_mask.any(dim=-1)):
        raise ValueError("every sample must allow at least one action")
    neg = torch.finfo(logits.dtype).min
    log_all = torch.logsumexp(logits, dim=-1)
    log_allowed = torch.logsumexp(logits.masked_fill(~allowed_action_mask, neg), dim=-1)
    return log_all - log_allowed


def causal_router_loss(
    output: dict[str, Tensor],
    targets: CausalRouterTargets,
    *,
    base_action_logits: Tensor,
    policy_weight: float = 1.25,
    preservation_weight: float = 2.0,
    gate_weight: float = 0.35,
    role_weight: float = 0.25,
    residual_weight: float = 2e-4,
) -> dict[str, Tensor]:
    logits = output["action_logits"]
    residual = output["action_logit_residual"]
    activation = output["router_activation"]
    role_logits = output["role_logits"]
    if logits.shape != base_action_logits.shape or residual.shape != logits.shape:
        raise ValueError("router policy output shape mismatch")
    batch, actions = logits.shape
    causal = targets.causal_activation_target.to(logits.device, logits.dtype)
    allowed = targets.allowed_action_mask.to(logits.device)
    roles = targets.role_targets.to(logits.device, torch.long)
    role_mask = targets.role_supervision_mask.to(logits.device)
    if causal.shape != (batch,):
        raise ValueError("causal_activation_target must be [batch]")
    if roles.shape != (batch, actions) or role_mask.shape != (batch, actions):
        raise ValueError("role targets and mask must be [batch, actions]")
    if role_mask.dtype != torch.bool:
        raise ValueError("role_supervision_mask must be bool")
    if torch.any((causal < 0) | (causal > 1)):
        raise ValueError("causal_activation_target must lie in [0, 1]")

    per_sample_policy = set_valued_policy_loss(logits, allowed)
    causal_mask = causal > 0.5
    noncausal_mask = ~causal_mask
    policy_loss = per_sample_policy[causal_mask].mean() if causal_mask.any() else logits.new_zeros(())
    preservation_loss = (
        (logits[noncausal_mask] - base_action_logits[noncausal_mask]).square().mean()
        if noncausal_mask.any()
        else logits.new_zeros(())
    )
    gate_loss = F.binary_cross_entropy(activation, causal)
    role_loss = (
        F.cross_entropy(role_logits[role_mask], roles[role_mask])
        if role_mask.any()
        else logits.new_zeros(())
    )
    residual_loss = residual.square().mean()
    loss = (
        policy_weight * policy_loss
        + preservation_weight * preservation_loss
        + gate_weight * gate_loss
        + role_weight * role_loss
        + residual_weight * residual_loss
    )
    return {
        "loss": loss,
        "policy_loss": policy_loss,
        "preservation_loss": preservation_loss,
        "gate_loss": gate_loss,
        "role_loss": role_loss,
        "residual_loss": residual_loss,
    }


def configure_causal_router_training(
    router: CausalEvidenceRouter,
    *,
    upstream_modules: Sequence[nn.Module] = (),
) -> dict[str, int]:
    """Freeze the accepted parent and train only the tiny neural delta."""
    for module in upstream_modules:
        for parameter in module.parameters():
            parameter.requires_grad_(False)
    for parameter in router.parameters():
        parameter.requires_grad_(True)
    return {
        "router_trainable_parameters": sum(p.numel() for p in router.parameters() if p.requires_grad),
        "upstream_trainable_parameters": sum(
            p.numel() for module in upstream_modules for p in module.parameters() if p.requires_grad
        ),
    }


def make_causal_router_optimizer(
    router: CausalEvidenceRouter,
    *,
    lr: float = 1.5e-3,
    weight_decay: float = 5e-4,
) -> torch.optim.Optimizer:
    if lr <= 0 or weight_decay < 0:
        raise ValueError("invalid optimizer hyperparameters")
    return torch.optim.AdamW(router.parameters(), lr=float(lr), weight_decay=float(weight_decay))


def train_causal_router_step(
    router: CausalEvidenceRouter,
    inputs: dict[str, Tensor],
    targets: CausalRouterTargets,
    optimizer: torch.optim.Optimizer,
    *,
    max_grad_norm: float = 1.0,
) -> dict[str, float]:
    if max_grad_norm <= 0:
        raise ValueError("max_grad_norm must be positive")
    router.train()
    optimizer.zero_grad(set_to_none=True)
    output = router(**inputs)
    losses = causal_router_loss(output, targets, base_action_logits=inputs["base_action_logits"])
    losses["loss"].backward()
    grad_norm = torch.nn.utils.clip_grad_norm_(router.parameters(), max_norm=float(max_grad_norm))
    optimizer.step()
    result = {key: float(value.detach().cpu()) for key, value in losses.items()}
    result["grad_norm"] = float(torch.as_tensor(grad_norm).detach().cpu())
    return result
