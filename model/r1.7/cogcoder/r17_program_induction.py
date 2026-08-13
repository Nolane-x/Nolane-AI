from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


def _numeric_vector(value: Any) -> tuple[int, ...] | None:
    if not isinstance(value, list) or len(value) < 2:
        return None
    row: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        number = float(item)
        if not number.is_integer():
            return None
        row.append(int(number))
    return tuple(row)


def _parse(text: str) -> Any:
    payload = json.loads(text)
    if not isinstance(payload, (dict, list)):
        raise ValueError("public observation must decode to an object or list")
    return payload


def extract_shallow_numeric_vector(text: str) -> tuple[int, ...]:
    """Return the unique shallowest public numeric vector without using field names."""
    payload = _parse(text)
    candidates: list[tuple[int, tuple[int, ...]]] = []

    def visit(node: Any, depth: int) -> None:
        vector = _numeric_vector(node)
        if vector is not None:
            candidates.append((depth, vector))
            return
        if isinstance(node, Mapping):
            for value in node.values():
                visit(value, depth + 1)
        elif isinstance(node, list):
            for value in node:
                visit(value, depth + 1)

    visit(payload, 0)
    if not candidates:
        raise ValueError("no public numeric vector found")
    shallow = min(depth for depth, _ in candidates)
    rows = [vector for depth, vector in candidates if depth == shallow]
    if len(rows) != 1:
        raise ValueError("ambiguous shallow numeric vectors")
    return rows[0]


def extract_demonstration_vector_pairs(text: str) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    """Find same-length vector pairs co-located in public mapping nodes.

    Pair orientation is deliberately not interpreted here. Program search must
    evaluate both global orientations rather than reading literal field names.
    """
    payload = _parse(text)
    pairs: list[tuple[tuple[int, ...], tuple[int, ...]]] = []

    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            vectors = [vector for value in node.values() if (vector := _numeric_vector(value)) is not None]
            if len(vectors) == 2 and len(vectors[0]) == len(vectors[1]):
                pairs.append((vectors[0], vectors[1]))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            if _numeric_vector(node) is not None:
                return
            for value in node:
                visit(value)

    visit(payload)
    return pairs

from dataclasses import dataclass
from itertools import product

import torch

from .neural_system2 import encode_action_descriptions


@dataclass(frozen=True)
class FunctionalProgramHypothesis:
    sequence: tuple[int, ...]
    exact: bool
    horizon: int
    orientation: int = 0
    matched_elements: int = 0
    total_elements: int = 0


def _element_matches(predicted, targets) -> tuple[int, int]:
    matched = total = 0
    for pred, target in zip(predicted, targets):
        if len(pred) != len(target):
            raise ValueError("predicted and target vectors must share length")
        matched += sum(int(a == b) for a, b in zip(pred, target))
        total += len(target)
    return matched, total


def search_functional_program(
    demo_pairs,
    action_indices,
    step_fn,
    *,
    max_horizon: int = 4,
) -> FunctionalProgramHypothesis:
    """Search shortest exact program under an externally supplied transition model."""
    pairs = list(demo_pairs)
    actions = tuple(int(index) for index in action_indices)
    if not pairs:
        raise ValueError("functional program search requires at least one demonstration")
    if not actions:
        raise ValueError("functional program search requires at least one non-submit action")
    if max_horizon < 1:
        raise ValueError("max_horizon must be positive")
    inputs = [tuple(int(x) for x in left) for left, _ in pairs]
    targets = [tuple(int(x) for x in right) for _, right in pairs]
    best = FunctionalProgramHypothesis((), False, 0, 0, -1, sum(len(t) for t in targets))
    for horizon in range(1, max_horizon + 1):
        for sequence in product(actions, repeat=horizon):
            states = list(inputs)
            for action_index in sequence:
                states = list(step_fn(states, int(action_index)))
            matched, total = _element_matches(states, targets)
            exact = matched == total
            candidate = FunctionalProgramHypothesis(tuple(sequence), exact, horizon, 0, matched, total)
            if exact:
                return candidate
            if matched > best.matched_elements:
                best = candidate
    return best


def _batched_orientation_search(
    model,
    pairs,
    action_indices: tuple[int, ...],
    action_embeddings: torch.Tensor,
    *,
    orientation: int,
    max_horizon: int,
) -> FunctionalProgramHypothesis:
    oriented = [(pair[orientation], pair[1 - orientation]) for pair in pairs]
    inputs = torch.tensor([left for left, _ in oriented], dtype=torch.long)
    targets = torch.tensor([right for _, right in oriented], dtype=torch.long)
    if inputs.ndim != 2 or targets.shape != inputs.shape:
        raise ValueError("all demonstration vectors must share one length")
    demo_count, vector_length = inputs.shape
    total_elements = int(targets.numel())
    sequences: list[tuple[int, ...]] = [()]
    states = inputs.unsqueeze(0)
    best = FunctionalProgramHypothesis((), False, 0, orientation, -1, total_elements)

    with torch.no_grad():
        for horizon in range(1, max_horizon + 1):
            prefix_count = states.shape[0]
            action_count = len(action_indices)
            vectors = (
                states[:, None, :, :]
                .expand(prefix_count, action_count, demo_count, vector_length)
                .reshape(prefix_count * action_count * demo_count, vector_length)
            )
            selected = action_embeddings[list(action_indices)]
            embedded = (
                selected[None, :, None, :]
                .expand(prefix_count, action_count, demo_count, selected.shape[-1])
                .reshape(prefix_count * action_count * demo_count, selected.shape[-1])
            )
            logits = model.program_execute_logits(vectors, embedded)
            next_states = logits.argmax(-1).reshape(prefix_count, action_count, demo_count, vector_length)
            expanded_sequences = [prefix + (int(action_index),) for prefix in sequences for action_index in action_indices]
            flat_states = next_states.reshape(prefix_count * action_count, demo_count, vector_length)
            matches = flat_states.eq(targets.unsqueeze(0)).sum(dim=(1, 2))
            exact_mask = matches.eq(total_elements)
            exact_indices = torch.nonzero(exact_mask, as_tuple=False).flatten()
            if exact_indices.numel():
                index = int(exact_indices[0].item())
                return FunctionalProgramHypothesis(expanded_sequences[index], True, horizon, orientation, total_elements, total_elements)
            max_matches = int(matches.max().item())
            if max_matches > best.matched_elements:
                index = int(matches.argmax().item())
                best = FunctionalProgramHypothesis(expanded_sequences[index], False, horizon, orientation, max_matches, total_elements)
            sequences = expanded_sequences
            states = flat_states
    return best


def infer_functional_program(
    model,
    observation_text: str,
    action_descriptions,
    *,
    max_horizon: int = 4,
) -> FunctionalProgramHypothesis:
    """Infer a short program solely from public demonstrations and learned operators."""
    pairs = extract_demonstration_vector_pairs(observation_text)
    if not pairs:
        raise ValueError("no public demonstration vector pairs found")
    descriptions = tuple(str(item) for item in action_descriptions)
    action_indices = tuple(index for index, description in enumerate(descriptions) if "submit" not in description.lower())
    if not action_indices:
        raise ValueError("no public non-submit actions found")
    tokens = encode_action_descriptions(descriptions, max_bytes=64).unsqueeze(0)
    with torch.no_grad():
        action_embeddings = model.action_encoder(tokens)[0]
    hypotheses = [
        _batched_orientation_search(model, pairs, action_indices, action_embeddings, orientation=orientation, max_horizon=max_horizon)
        for orientation in (0, 1)
    ]
    exact = [candidate for candidate in hypotheses if candidate.exact]
    if exact:
        return min(exact, key=lambda item: (item.horizon, item.sequence, item.orientation))
    return max(hypotheses, key=lambda item: (item.matched_elements, -item.horizon, tuple(-x for x in item.sequence)))


def execute_functional_program_hypothesis(task, hypothesis: FunctionalProgramHypothesis) -> dict[str, object]:
    """Execute an inferred public-action program, then submit via public action text."""
    descriptions = tuple(str(item) for item in task.action_descriptions)
    submit = [index for index, description in enumerate(descriptions) if "submit" in description.lower()]
    if len(submit) != 1:
        raise ValueError("functional program execution requires exactly one public submit action")
    used = 0
    solved = False
    done = False
    for action_index in hypothesis.sequence:
        result = task.step(int(action_index))
        used += 1
        done = bool(result.done)
        solved = bool(result.solved)
        if done:
            return {"solved": solved, "done": done, "used_actions": used, "pre_submit_actions": used}
    result = task.step(int(submit[0]))
    used += 1
    return {"solved": bool(result.solved), "done": bool(result.done), "used_actions": used, "pre_submit_actions": max(0, used - 1)}
