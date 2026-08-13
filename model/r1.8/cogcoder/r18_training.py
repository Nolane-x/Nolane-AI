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
from .r18_benchmark import R18Task, oracle_plan
from .r18_causal_memory import ConditionalEvidenceMemory, public_context_fingerprint


@dataclass(frozen=True)
class ConditionalLawTrainingStep:
    state_sketch: Tensor
    context_fingerprint: Tensor
    action_embeddings: Tensor
    evidence_effects: Tensor
    evidence_meta: Tensor
    target_effects: Tensor
    predict_mask: Tensor
    executed_action: int
    observed_effect: Tensor


@dataclass(frozen=True)
class ConditionalLawEpisode:
    task_id: str
    family: str
    steps: tuple[ConditionalLawTrainingStep, ...]


def conditional_law_trainable_parameter_names(model: NeuralSystem2Workspace) -> list[str]:
    names = [name for name, _ in model.named_parameters() if name.startswith("conditional_law_")]
    if not names:
        raise ValueError("model exposes no conditional_law_ parameters")
    return names


def _public_state(text: str, *, sketch_dim: int) -> tuple[Tensor, Tensor, Tensor]:
    ids, values = encode_structured_observation(text, max_atoms=96)
    ids_b = ids.unsqueeze(0)
    values_b = values.unsqueeze(0)
    state = structured_numeric_state_sketch(ids_b, values_b, sketch_dim=sketch_dim)
    return ids_b, values_b, state.squeeze(0)


def _counterfactual_effects(task: R18Task, before_ids: Tensor, before_values: Tensor, action_count: int, sketch_dim: int) -> Tensor:
    rows: list[Tensor] = []
    for action_index in range(action_count):
        branch = copy.deepcopy(task)
        result = branch.step(action_index)
        after_ids, after_values = encode_structured_observation(
            result.observation and branch.render_observation(), max_atoms=96
        )
        delta = structured_numeric_delta_sketch(
            before_ids,
            before_values,
            after_ids.unsqueeze(0),
            after_values.unsqueeze(0),
            sketch_dim=sketch_dim,
        ).squeeze(0)
        rows.append(delta)
    return torch.stack(rows)


def _safe_exploration_action(task: R18Task, actions: list[int], counts: list[int]) -> int:
    for action_index in sorted(actions, key=lambda index: (counts[index], index)):
        branch = copy.deepcopy(task)
        result = branch.step(action_index)
        if result.done:
            continue
        try:
            oracle_plan(branch)
        except RuntimeError:
            continue
        return int(action_index)
    return int(oracle_plan(copy.deepcopy(task))[0])


def collect_conditional_law_episode(
    model: NeuralSystem2Workspace,
    task: R18Task,
    *,
    exploration_steps: int = 6,
    max_steps: int = 16,
) -> ConditionalLawEpisode:
    """Collect FIGG-18 train-only counterfactual public transition supervision."""
    if task.split != "train":
        raise ValueError("conditional-law collector only accepts train split tasks")
    if exploration_steps < 0 or max_steps < 1:
        raise ValueError("invalid exploration/max_steps")
    model.eval()
    action_tokens = encode_action_descriptions(task.action_descriptions, max_bytes=64).unsqueeze(0)
    with torch.no_grad():
        action_embeddings = model.action_encoder(action_tokens)[0].detach().cpu()
    action_count = action_embeddings.shape[0]
    non_submit = [
        index for index, description in enumerate(task.action_descriptions)
        if "submit" not in description.lower()
    ]
    counts = [0 for _ in range(action_count)]
    memory = ConditionalEvidenceMemory(action_count=action_count, effect_dim=model.psr_sketch_dim)
    steps: list[ConditionalLawTrainingStep] = []

    while not task.done and len(steps) < max_steps:
        before_text = task.render_observation()
        before_ids, before_values, state_sketch = _public_state(
            before_text, sketch_dim=model.psr_sketch_dim
        )
        context = public_context_fingerprint(
            before_text, dims=model.conditional_law_context_dim
        )
        evidence_rows = []
        meta_rows = []
        for action_index in range(action_count):
            lookup = memory.retrieve(action_index, context)
            evidence_rows.append(lookup.effect)
            meta_rows.append(
                torch.tensor(
                    [
                        min(1.0, lookup.count / 4.0),
                        lookup.consistency,
                        lookup.context_similarity,
                    ],
                    dtype=torch.float32,
                )
            )
        evidence_effects = torch.stack(evidence_rows)
        evidence_meta = torch.stack(meta_rows)
        target_effects = _counterfactual_effects(
            task, before_ids, before_values, action_count, model.psr_sketch_dim
        )
        predict_mask = torch.tensor(
            ["submit" not in description.lower() for description in task.action_descriptions],
            dtype=torch.bool,
        )

        if len(steps) < exploration_steps and non_submit:
            executed = _safe_exploration_action(task, non_submit, counts)
        else:
            executed = int(oracle_plan(copy.deepcopy(task))[0])

        result = task.step(executed)
        after_ids, after_values = encode_structured_observation(
            task.render_observation(), max_atoms=96
        )
        observed_effect = structured_numeric_delta_sketch(
            before_ids,
            before_values,
            after_ids.unsqueeze(0),
            after_values.unsqueeze(0),
            sketch_dim=model.psr_sketch_dim,
        ).squeeze(0).detach().cpu()
        memory.update(executed, context, state_sketch, observed_effect)
        counts[executed] += 1
        steps.append(
            ConditionalLawTrainingStep(
                state_sketch=state_sketch.detach().cpu(),
                context_fingerprint=context.detach().cpu(),
                action_embeddings=action_embeddings,
                evidence_effects=evidence_effects.detach().cpu(),
                evidence_meta=evidence_meta.detach().cpu(),
                target_effects=target_effects.detach().cpu(),
                predict_mask=predict_mask,
                executed_action=executed,
                observed_effect=observed_effect,
            )
        )
        if result.done:
            break

    return ConditionalLawEpisode(task_id=task.task_id, family=task.family, steps=tuple(steps))
