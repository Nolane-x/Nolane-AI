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
class RolloutRow:
    task_id: str
    family: str
    state_sketch: Tensor
    context_fingerprint: Tensor
    program_action_embeddings: Tensor
    parent_effects: Tensor
    target_effect: Tensor
    program_indices: tuple[int, int]
    submit_index: int


def _public_state(text: str, sketch_dim: int) -> tuple[Tensor, Tensor, Tensor]:
    ids, values = encode_structured_observation(text, max_atoms=96)
    ids_b = ids.unsqueeze(0)
    values_b = values.unsqueeze(0)
    state = structured_numeric_state_sketch(ids_b, values_b, sketch_dim=sketch_dim)
    return ids_b, values_b, state.squeeze(0)


def _delta(before_ids: Tensor, before_values: Tensor, after_text: str, sketch_dim: int) -> Tensor:
    after_ids, after_values = encode_structured_observation(after_text, max_atoms=96)
    return structured_numeric_delta_sketch(
        before_ids,
        before_values,
        after_ids.unsqueeze(0),
        after_values.unsqueeze(0),
        sketch_dim=sketch_dim,
    ).squeeze(0)


def _memory_tensors(memory: ConditionalEvidenceMemory, context: Tensor, action_count: int) -> tuple[Tensor, Tensor]:
    evidence_rows: list[Tensor] = []
    meta_rows: list[Tensor] = []
    for action_index in range(action_count):
        lookup = memory.retrieve(action_index, context)
        evidence_rows.append(lookup.effect)
        meta_rows.append(
            torch.tensor(
                [min(1.0, lookup.count / 4.0), lookup.consistency, lookup.context_similarity],
                dtype=torch.float32,
            )
        )
    return torch.stack(evidence_rows), torch.stack(meta_rows)


def _parent_effects(
    model: NeuralSystem2Workspace,
    state_sketch: Tensor,
    context: Tensor,
    action_embeddings: Tensor,
    memory: ConditionalEvidenceMemory,
) -> Tensor:
    evidence, meta = _memory_tensors(memory, context, action_embeddings.shape[0])
    with torch.no_grad():
        out = model.conditional_law_scores(
            state_sketch.unsqueeze(0),
            context.unsqueeze(0),
            action_embeddings.unsqueeze(0),
            evidence.unsqueeze(0),
            meta.unsqueeze(0),
        )
    return out["predicted_effect"].squeeze(0).detach().cpu()


def collect_rollout_rows(
    model: NeuralSystem2Workspace,
    task: R18Task,
    *,
    max_states: int = 3,
) -> tuple[RolloutRow, ...]:
    """Training collector: exact rows from public FIGG-18 train worlds only."""
    if task.split != "train":
        raise ValueError("FIGG-19 rollout collection accepts train split only")
    return _collect_rollout_rows(model, task, max_states=max_states)


def collect_rollout_eval_rows(
    model: NeuralSystem2Workspace,
    task: R18Task,
    *,
    max_states: int = 3,
) -> tuple[RolloutRow, ...]:
    """Evaluation-only collector for locked dev/fresh worlds; never used by trainers."""
    return _collect_rollout_rows(model, task, max_states=max_states)


def _collect_rollout_rows(
    model: NeuralSystem2Workspace,
    task: R18Task,
    *,
    max_states: int,
) -> tuple[RolloutRow, ...]:
    if max_states < 1:
        raise ValueError("max_states must be positive")

    model.eval()
    action_tokens = encode_action_descriptions(task.action_descriptions, max_bytes=64).unsqueeze(0)
    with torch.no_grad():
        action_embeddings = model.action_encoder(action_tokens)[0].detach().cpu()
    descriptions = tuple(task.action_descriptions)
    submit_indices = [i for i, text in enumerate(descriptions) if "submit" in text.lower()]
    if len(submit_indices) != 1:
        raise ValueError("expected exactly one submit action")
    submit_index = submit_indices[0]
    action_indices = [i for i in range(len(descriptions)) if i != submit_index]
    memory = ConditionalEvidenceMemory(action_count=len(descriptions), effect_dim=model.psr_sketch_dim)
    rows: list[RolloutRow] = []

    for _ in range(max_states):
        if task.done:
            break
        before_text = task.render_observation()
        before_ids, before_values, state = _public_state(before_text, model.psr_sketch_dim)
        context = public_context_fingerprint(before_text, dims=model.conditional_law_context_dim)
        first_parent = _parent_effects(model, state, context, action_embeddings, memory)

        for first in action_indices:
            branch = copy.deepcopy(task)
            branch_memory = copy.deepcopy(memory)
            first_result = branch.step(first)
            first_observed = _delta(before_ids, before_values, branch.render_observation(), model.psr_sketch_dim)
            branch_memory.update(first, context, state, first_observed)
            if first_result.done:
                continue
            mid_text = branch.render_observation()
            mid_ids, mid_values, mid_state = _public_state(mid_text, model.psr_sketch_dim)
            mid_context = public_context_fingerprint(mid_text, dims=model.conditional_law_context_dim)
            second_parent = _parent_effects(model, mid_state, mid_context, action_embeddings, branch_memory)

            for second in action_indices:
                final_branch = copy.deepcopy(branch)
                final_branch.step(second)
                target = _delta(before_ids, before_values, final_branch.render_observation(), model.psr_sketch_dim)
                rows.append(
                    RolloutRow(
                        task_id=task.task_id,
                        family=task.family,
                        state_sketch=state.detach().cpu(),
                        context_fingerprint=context.detach().cpu(),
                        program_action_embeddings=torch.stack((action_embeddings[first], action_embeddings[second])),
                        parent_effects=torch.stack((first_parent[first], second_parent[second])),
                        target_effect=target.detach().cpu(),
                        program_indices=(int(first), int(second)),
                        submit_index=int(submit_index),
                    )
                )

        # Advance the real public trajectory deterministically using the benchmark oracle,
        # but do not store the oracle action in any training row.
        plan = oracle_plan(copy.deepcopy(task))
        if not plan:
            break
        executed = int(plan[0])
        if executed == submit_index:
            break
        result = task.step(executed)
        after_text = task.render_observation()
        observed = _delta(before_ids, before_values, after_text, model.psr_sketch_dim)
        memory.update(executed, context, state, observed)
        if result.done:
            break

    return tuple(rows)


def additive_parent_baseline(row: RolloutRow) -> Tensor:
    return row.parent_effects.sum(dim=0)
