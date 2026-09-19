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

from nvnext.multidepth import (  # noqa: E402
    AdaptiveDepthCandidate,
    MultiDepthObjective,
    first_stable_correct_step,
    ponder_continue_targets,
)
from r23.ultra_core import ScaledRecursiveDistilledReasoner, r22_parameter_count  # noqa: E402


def _inputs(batch: int = 2, actions: int = 4) -> dict[str, torch.Tensor]:
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


def test_first_stable_correct_step_requires_persistent_repair() -> None:
    logits = torch.tensor(
        [
            [[5.0, 0.0], [0.0, 5.0], [0.0, 6.0], [7.0, 0.0]],
            [[5.0, 0.0], [5.0, 0.0], [5.0, 0.0], [5.0, 0.0]],
        ]
    )
    expert = torch.tensor([1, 1], dtype=torch.long)

    step = first_stable_correct_step(logits, expert, stability_steps=2)

    assert step.tolist() == [2, 4]
    target = ponder_continue_targets(logits, expert, stability_steps=2)
    assert target[0].tolist() == [1.0, 1.0, 0.0, 0.0]
    assert target[1].tolist() == [1.0, 1.0, 1.0, 1.0]


def test_multidepth_objective_backpropagates_into_recurrence_and_ponder() -> None:
    torch.manual_seed(3)
    model = ScaledRecursiveDistilledReasoner(latent_dim=192, n_heads=6, ff_mult=2)
    values = _inputs()
    output = model(**values, reasoning_steps=4)
    expert = torch.tensor([1, 2], dtype=torch.long)

    losses = MultiDepthObjective()(
        output,
        expert_actions=expert,
        base_action_logits=values["base_action_logits"],
    )
    losses["loss"].backward()

    assert torch.isfinite(losses["loss"])
    assert model.ponder_head.weight.grad is not None
    assert model.ponder_head.weight.grad.abs().sum().item() > 0.0
    recurrent_grads = [
        parameter.grad
        for parameter in model.reasoning_cell.parameters()
        if parameter.grad is not None
    ]
    assert recurrent_grads
    assert sum(grad.abs().sum().item() for grad in recurrent_grads) > 0.0


def test_adaptive_depth_adds_no_trainable_parameters() -> None:
    model = ScaledRecursiveDistilledReasoner(latent_dim=192, n_heads=6, ff_mult=2)
    before = r22_parameter_count(model)
    candidate = AdaptiveDepthCandidate(model, max_steps=4, min_steps=2)
    after = sum(parameter.numel() for parameter in candidate.parameters())

    assert before == after


class _ScriptedReasoner(torch.nn.Module):
    def forward(self, **kwargs):
        del kwargs
        trajectory = torch.tensor(
            [
                [[4.0, 0.0], [0.0, 4.0], [0.0, 5.0], [0.0, 6.0]],
                [[4.0, 0.0], [4.0, 0.0], [4.0, 0.0], [0.0, 5.0]],
            ]
        )
        ponder = torch.tensor(
            [
                [5.0, 1.0, -5.0, -5.0],
                [5.0, -5.0, -5.0, -5.0],
            ]
        )
        return {
            "action_logits_trajectory": trajectory,
            "ponder_logits_trajectory": ponder,
            "override_gate_trajectory": torch.zeros(2, 4),
            "proposal_action_logits": trajectory[:, -1],
            "action_logits": trajectory[:, -1],
        }


def test_adaptive_depth_uses_stability_and_learned_halt_signal() -> None:
    candidate = AdaptiveDepthCandidate(
        _ScriptedReasoner(),
        max_steps=4,
        min_steps=2,
        halt_threshold=0.8,
        stability_steps=2,
    )

    output = candidate()

    assert output["selected_depth"].tolist() == [3, 2]
    assert output["action_logits"][0].argmax().item() == 1
    assert output["action_logits"][1].argmax().item() == 0
