from __future__ import annotations

import copy
from dataclasses import dataclass

import torch
from torch import Tensor

from .neural_system2 import (
    NeuralSystem2Workspace,
    encode_action_descriptions,
    encode_structured_observation,
    structured_numeric_delta_sketch,
    structured_numeric_state_sketch,
)
from .r17_benchmark import R17Task, oracle_plan


@dataclass(frozen=True)
class GoalDifferenceTrainingStep:
    structured_atoms: Tensor
    structured_mask: Tensor
    action_embeddings: Tensor
    predicted_deltas: Tensor
    confidence: Tensor
    target_progress: Tensor
    baseline_progress: Tensor
    predict_mask: Tensor
    executed_action: int
    observed_delta: Tensor
    observed_progress: float


@dataclass(frozen=True)
class GoalDifferenceEpisode:
    task_id: str
    family: str
    steps: tuple[GoalDifferenceTrainingStep, ...]


def goal_difference_trainable_parameter_names(
    model: NeuralSystem2Workspace, *, include_policy_scale: bool = False
) -> list[str]:
    names: list[str] = []
    for name, _ in model.named_parameters():
        if not name.startswith("goal_difference_"):
            continue
        if not include_policy_scale and name == "goal_difference_policy_scale":
            continue
        names.append(name)
    if not names:
        raise ValueError("model exposes no goal_difference_ parameters")
    return names


def _public_tensors(
    model: NeuralSystem2Workspace, task: R17Task
) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor]:
    ids, values = encode_structured_observation(task.render_observation(), max_atoms=96)
    ids_b = ids.unsqueeze(0)
    values_b = values.unsqueeze(0)
    with torch.no_grad():
        atoms, mask = model.structured_observation_encoder.encode_atoms(ids_b, values_b)
        state_sketch = structured_numeric_state_sketch(
            ids_b, values_b, sketch_dim=model.psr_sketch_dim
        )
    return ids_b, values_b, atoms.squeeze(0).detach().cpu(), mask.squeeze(0).detach().cpu(), state_sketch


def _counterfactual_progress(task: R17Task, action_index: int) -> float:
    branch = copy.deepcopy(task)
    result = branch.step(int(action_index))
    return float(result.progress_delta)


def collect_goal_difference_episode(
    model: NeuralSystem2Workspace,
    task: R17Task,
    *,
    exploration_steps: int = 6,
    max_steps: int = 14,
) -> GoalDifferenceEpisode:
    """Collect train-only progress supervision from public-derived representations."""
    if task.split != "train":
        raise ValueError("goal-difference training collector only accepts train split tasks")
    if exploration_steps < 0:
        raise ValueError("exploration_steps must be non-negative")
    if max_steps < 1:
        raise ValueError("max_steps must be positive")

    model.eval()
    action_tokens = encode_action_descriptions(task.action_descriptions, max_bytes=64).unsqueeze(0)
    with torch.no_grad():
        action_embeddings = model.action_encoder(action_tokens).detach()
    action_count = action_embeddings.shape[1]
    non_submit = [
        i for i, description in enumerate(task.action_descriptions)
        if "submit" not in description.lower()
    ]
    observed_counts = [0 for _ in range(action_count)]
    last_progress = torch.zeros(action_count, dtype=torch.float32)
    law_state = model.init_causal_law_state(batch_size=1, device=torch.device("cpu"))
    rows: list[GoalDifferenceTrainingStep] = []

    while not task.done and len(rows) < int(max_steps):
        before_ids, before_values, atoms, atom_mask, state_sketch = _public_tensors(model, task)
        with torch.no_grad():
            law_scores = model.causal_law_scores(state_sketch, action_embeddings, law_state)
        predicted_deltas = law_scores["predicted_delta"].squeeze(0).detach().cpu()
        confidence = law_scores["confidence"].squeeze(0).detach().cpu()
        target_progress = torch.tensor(
            [_counterfactual_progress(task, i) for i in range(action_count)],
            dtype=torch.float32,
        )
        non_submit_mask = torch.tensor(
            ["submit" not in d.lower() for d in task.action_descriptions], dtype=torch.bool
        )
        predict_mask = non_submit_mask & confidence.gt(1e-6)

        if len(rows) < exploration_steps and non_submit:
            executed = min(non_submit, key=lambda i: (observed_counts[i], i))
        else:
            plan = oracle_plan(copy.deepcopy(task))
            executed = int(plan[0])

        baseline = last_progress.clone()
        result = task.step(executed)
        after_ids, after_values = encode_structured_observation(task.render_observation(), max_atoms=96)
        observed_delta = structured_numeric_delta_sketch(
            before_ids,
            before_values,
            after_ids.unsqueeze(0),
            after_values.unsqueeze(0),
            sketch_dim=model.psr_sketch_dim,
        ).detach()
        with torch.no_grad():
            law_state = model.update_causal_laws(
                state_sketch,
                action_embeddings,
                executed,
                observed_delta,
                law_state,
            )
        last_progress[executed] = float(result.progress_delta)
        observed_counts[executed] += 1
        rows.append(
            GoalDifferenceTrainingStep(
                structured_atoms=atoms,
                structured_mask=atom_mask,
                action_embeddings=action_embeddings.squeeze(0).detach().cpu(),
                predicted_deltas=predicted_deltas,
                confidence=confidence,
                target_progress=target_progress,
                baseline_progress=baseline,
                predict_mask=predict_mask,
                executed_action=executed,
                observed_delta=observed_delta.squeeze(0).detach().cpu(),
                observed_progress=float(result.progress_delta),
            )
        )
        if result.done:
            break

    return GoalDifferenceEpisode(task_id=task.task_id, family=task.family, steps=tuple(rows))
