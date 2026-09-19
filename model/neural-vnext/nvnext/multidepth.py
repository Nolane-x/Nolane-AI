from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import torch
from torch import Tensor, nn
import torch.nn.functional as F


def _require_logits_trajectory(value: Tensor) -> tuple[int, int, int]:
    if not isinstance(value, Tensor) or value.ndim != 3:
        raise ValueError("action logits trajectory must be [batch, depth, actions]")
    batch, depth, actions = value.shape
    if batch < 1 or depth < 1 or actions < 1:
        raise ValueError("action logits trajectory dimensions must be non-empty")
    return batch, depth, actions


def first_stable_correct_step(
    logits_trajectory: Tensor,
    expert_actions: Tensor,
    *,
    stability_steps: int = 2,
) -> Tensor:
    """Return the first zero-based depth whose trailing window is all expert-correct.

    A return value equal to the trajectory depth is the explicit "not solved
    stably within budget" sentinel.
    """
    batch, depth, _actions = _require_logits_trajectory(logits_trajectory)
    if type(stability_steps) is not int or stability_steps < 1:
        raise ValueError("stability_steps must be a positive integer")
    if expert_actions.shape != (batch,) or expert_actions.dtype != torch.long:
        raise ValueError("expert_actions must be int64 [batch]")

    predicted = logits_trajectory.argmax(dim=-1)
    correct = predicted.eq(expert_actions[:, None])
    result = torch.full(
        (batch,),
        depth,
        dtype=torch.long,
        device=logits_trajectory.device,
    )
    if stability_steps > depth:
        return result

    for end in range(stability_steps - 1, depth):
        start = end - stability_steps + 1
        stable = correct[:, start : end + 1].all(dim=1)
        first = result.eq(depth) & stable
        result = torch.where(first, torch.full_like(result, end), result)
    return result


def ponder_continue_targets(
    logits_trajectory: Tensor,
    expert_actions: Tensor,
    *,
    stability_steps: int = 2,
) -> Tensor:
    """Target 1 while more recurrent computation is needed, then 0 after repair."""
    _batch, depth, _actions = _require_logits_trajectory(logits_trajectory)
    stable_step = first_stable_correct_step(
        logits_trajectory.detach(),
        expert_actions,
        stability_steps=stability_steps,
    )
    step = torch.arange(depth, device=logits_trajectory.device)[None, :]
    return step.lt(stable_step[:, None]).to(dtype=logits_trajectory.dtype)


@dataclass(frozen=True)
class MultiDepthLossConfig:
    action_weight: float = 1.0
    ponder_weight: float = 0.35
    delegation_weight: float = 0.5
    parent_preservation_weight: float = 0.25
    stability_steps: int = 2

    def __post_init__(self) -> None:
        for value in (
            self.action_weight,
            self.ponder_weight,
            self.delegation_weight,
            self.parent_preservation_weight,
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) < 0.0:
                raise ValueError("loss weights must be finite non-negative numbers")
            if not torch.isfinite(torch.tensor(float(value))):
                raise ValueError("loss weights must be finite non-negative numbers")
        if type(self.stability_steps) is not int or self.stability_steps < 1:
            raise ValueError("stability_steps must be a positive integer")


class MultiDepthObjective(nn.Module):
    """Neural-only objective for training the R2.3 recurrence beyond one step.

    Positive ponder logits mean "continue thinking". Delegation is supervised to
    open only when a recurrent proposal repairs a parent error.
    """

    def __init__(self, config: MultiDepthLossConfig | None = None) -> None:
        super().__init__()
        self.config = config or MultiDepthLossConfig()

    def forward(
        self,
        output: Mapping[str, Tensor],
        *,
        expert_actions: Tensor,
        base_action_logits: Tensor,
    ) -> dict[str, Tensor]:
        trajectory = output["action_logits_trajectory"]
        ponder_logits = output["ponder_logits_trajectory"]
        gate = output["override_gate_trajectory"]

        batch, depth, actions = _require_logits_trajectory(trajectory)
        if expert_actions.shape != (batch,) or expert_actions.dtype != torch.long:
            raise ValueError("expert_actions must be int64 [batch]")
        if base_action_logits.shape != (batch, actions):
            raise ValueError("base_action_logits must be [batch, actions]")
        if ponder_logits.shape != (batch, depth):
            raise ValueError("ponder logits trajectory must be [batch, depth]")
        if gate.shape != (batch, depth):
            raise ValueError("override gate trajectory must be [batch, depth]")

        repeated_targets = expert_actions[:, None].expand(batch, depth)
        action_ce = F.cross_entropy(
            trajectory.reshape(batch * depth, actions),
            repeated_targets.reshape(batch * depth),
            reduction="none",
        ).reshape(batch, depth)
        depth_weights = torch.linspace(
            1.0,
            2.0,
            depth,
            device=trajectory.device,
            dtype=trajectory.dtype,
        )
        depth_weights = depth_weights / depth_weights.mean()
        action_loss = (action_ce * depth_weights[None, :]).mean()

        continue_target = ponder_continue_targets(
            trajectory,
            expert_actions,
            stability_steps=self.config.stability_steps,
        )
        ponder_loss = F.binary_cross_entropy_with_logits(
            ponder_logits,
            continue_target,
        )

        parent_action = base_action_logits.argmax(dim=-1)
        parent_correct = parent_action.eq(expert_actions)
        recurrent_action = trajectory.argmax(dim=-1)
        repair_target = (
            (~parent_correct[:, None])
            & recurrent_action.eq(expert_actions[:, None])
            & recurrent_action.ne(parent_action[:, None])
        ).to(dtype=trajectory.dtype)
        delegation_loss = F.binary_cross_entropy(
            gate.clamp(1e-6, 1.0 - 1e-6),
            repair_target,
        )

        parent_prob = torch.softmax(base_action_logits.detach(), dim=-1)
        candidate_log_prob = torch.log_softmax(trajectory, dim=-1)
        preservation_per_step = F.kl_div(
            candidate_log_prob,
            parent_prob[:, None, :].expand(batch, depth, actions),
            reduction="none",
        ).sum(dim=-1)
        parent_mask = parent_correct.to(dtype=trajectory.dtype)[:, None]
        parent_count = parent_mask.sum() * depth
        if bool(parent_correct.any()):
            preservation_loss = (preservation_per_step * parent_mask).sum() / parent_count.clamp_min(1.0)
        else:
            preservation_loss = trajectory.new_zeros(())

        total = (
            float(self.config.action_weight) * action_loss
            + float(self.config.ponder_weight) * ponder_loss
            + float(self.config.delegation_weight) * delegation_loss
            + float(self.config.parent_preservation_weight) * preservation_loss
        )
        stable_step = first_stable_correct_step(
            trajectory.detach(),
            expert_actions,
            stability_steps=self.config.stability_steps,
        )
        return {
            "loss": total,
            "action_loss": action_loss,
            "ponder_loss": ponder_loss,
            "delegation_loss": delegation_loss,
            "parent_preservation_loss": preservation_loss,
            "stable_correct_step": stable_step,
        }


class AdaptiveDepthCandidate(nn.Module):
    """Parameter-neutral adaptive-depth successor around the frozen R2.3 reasoner.

    The wrapped reasoner owns every trainable tensor. This wrapper only chooses
    which recurrent depth becomes the candidate neural decision.
    """

    def __init__(
        self,
        reasoner: nn.Module,
        *,
        max_steps: int = 4,
        min_steps: int = 2,
        halt_threshold: float = 0.5,
        stability_steps: int = 2,
    ) -> None:
        super().__init__()
        if type(max_steps) is not int or max_steps < 1:
            raise ValueError("max_steps must be a positive integer")
        if type(min_steps) is not int or not 1 <= min_steps <= max_steps:
            raise ValueError("min_steps must be within [1, max_steps]")
        if type(stability_steps) is not int or stability_steps < 1:
            raise ValueError("stability_steps must be a positive integer")
        if not isinstance(halt_threshold, (int, float)) or isinstance(halt_threshold, bool):
            raise ValueError("halt_threshold must be numeric")
        threshold = float(halt_threshold)
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("halt_threshold must lie in [0, 1]")
        self.reasoner = reasoner
        self.max_steps = max_steps
        self.min_steps = min_steps
        self.halt_threshold = threshold
        self.stability_steps = stability_steps

    def forward(self, **kwargs) -> dict[str, Tensor]:
        if "reasoning_steps" in kwargs:
            raise ValueError("AdaptiveDepthCandidate owns reasoning_steps")
        output = self.reasoner(**kwargs, reasoning_steps=self.max_steps)
        trajectory = output["action_logits_trajectory"]
        ponder_logits = output["ponder_logits_trajectory"]
        batch, depth, actions = _require_logits_trajectory(trajectory)
        if depth != self.max_steps or ponder_logits.shape != (batch, depth):
            raise ValueError("wrapped reasoner returned an incompatible depth trajectory")

        predicted = trajectory.argmax(dim=-1)
        halt_probability = torch.sigmoid(-ponder_logits)
        selected = torch.full(
            (batch,),
            depth - 1,
            dtype=torch.long,
            device=trajectory.device,
        )
        unresolved = torch.ones(batch, dtype=torch.bool, device=trajectory.device)

        for index in range(depth):
            if index + 1 < self.min_steps:
                continue
            start = max(0, index - self.stability_steps + 1)
            window = predicted[:, start : index + 1]
            stable = window.eq(window[:, -1:]).all(dim=1) & (window.shape[1] >= self.stability_steps)
            ready = stable & halt_probability[:, index].ge(self.halt_threshold)
            choose = unresolved & ready
            selected = torch.where(choose, torch.full_like(selected, index), selected)
            unresolved = unresolved & ~choose

        gather_index = selected[:, None, None].expand(batch, 1, actions)
        selected_logits = trajectory.gather(1, gather_index).squeeze(1)
        selected_halt = halt_probability.gather(1, selected[:, None]).squeeze(1)

        result = dict(output)
        result["action_logits"] = selected_logits
        result["adaptive_action_logits"] = selected_logits
        result["selected_depth"] = selected + 1
        result["selected_halt_probability"] = selected_halt
        return result
