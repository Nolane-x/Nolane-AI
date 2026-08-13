from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass

import torch
import torch.nn.functional as F

from .neural_system2 import NeuralSystem2Workspace, encode_action_descriptions
from .r17_benchmark import R17Task
from .r17_program_induction import extract_shallow_numeric_vector


@dataclass(frozen=True)
class OperatorTransition:
    before: tuple[int, ...]
    action_description: str
    after: tuple[int, ...]


def collect_operator_transitions(task: R17Task) -> list[OperatorTransition]:
    if task.split != 'train':
        raise ValueError('operator transition collector only accepts train split tasks')
    if task.family != 'composition_holdout':
        raise ValueError('operator transition collector requires composition_holdout family')
    before = extract_shallow_numeric_vector(task.render_observation())
    rows: list[OperatorTransition] = []
    for index, description in enumerate(task.action_descriptions):
        if 'submit' in description.lower():
            continue
        branch = copy.deepcopy(task)
        result = branch.step(index)
        if result.done:
            raise RuntimeError('non-submit composition action unexpectedly ended task')
        after = extract_shallow_numeric_vector(branch.render_observation())
        rows.append(OperatorTransition(before=before, action_description=description, after=after))
    return rows


def snapshot_trainable_state(model: NeuralSystem2Workspace, names) -> dict[str, torch.Tensor]:
    selected = set(names)
    return {
        name: parameter.detach().cpu().clone()
        for name, parameter in model.named_parameters()
        if name in selected
    }


def restore_trainable_state(model: NeuralSystem2Workspace, state: dict[str, torch.Tensor]) -> None:
    parameters = dict(model.named_parameters())
    missing = [name for name in state if name not in parameters]
    if missing:
        raise KeyError(f"unknown trainable parameters: {missing}")
    with torch.no_grad():
        for name, value in state.items():
            parameters[name].copy_(value.to(parameters[name].device, dtype=parameters[name].dtype))


def operator_executor_trainable_parameter_names(model: NeuralSystem2Workspace) -> list[str]:
    names = [name for name, _ in model.named_parameters() if name.startswith('program_executor_')]
    if not names:
        raise ValueError('model exposes no program_executor_ parameters')
    return names


def _batch_tensors(model: NeuralSystem2Workspace, rows: list[OperatorTransition]):
    if not rows:
        raise ValueError('operator transition batch must not be empty')
    lengths = {len(row.before) for row in rows} | {len(row.after) for row in rows}
    if len(lengths) != 1:
        raise ValueError('operator transition batch requires one vector length')
    before = torch.tensor([row.before for row in rows], dtype=torch.long)
    after = torch.tensor([row.after for row in rows], dtype=torch.long)
    action_tokens = encode_action_descriptions([row.action_description for row in rows], max_bytes=64)
    with torch.no_grad():
        action_embeddings = model.action_encoder(action_tokens.unsqueeze(1)).squeeze(1).detach()
    return before, after, action_embeddings


def evaluate_operator_transitions(model: NeuralSystem2Workspace, rows: list[OperatorTransition]) -> dict[str, object]:
    model.eval()
    grouped: dict[int, list[OperatorTransition]] = defaultdict(list)
    for row in rows:
        grouped[len(row.before)].append(row)
    exact = elements = correct_elements = total = 0
    per_operator = defaultdict(lambda: [0, 0])
    with torch.no_grad():
        for items in grouped.values():
            before, after, actions = _batch_tensors(model, items)
            logits = model.program_execute_logits(before, actions)
            pred = logits.argmax(-1)
            row_exact = pred.eq(after).all(dim=-1)
            exact += int(row_exact.sum())
            correct_elements += int(pred.eq(after).sum())
            elements += int(after.numel())
            total += len(items)
            for i, row in enumerate(items):
                slot = per_operator[row.action_description]
                slot[0] += int(row_exact[i].item())
                slot[1] += 1
    operators = {
        name: {'exact_vector_accuracy': c / max(1, n), 'rows': n}
        for name, (c, n) in per_operator.items()
    }
    return {
        'exact_vector_accuracy': exact / max(1, total),
        'element_accuracy': correct_elements / max(1, elements),
        'rows': total,
        'elements': elements,
        'operators': operators,
    }


def train_operator_epoch(model: NeuralSystem2Workspace, rows: list[OperatorTransition], optimizer: torch.optim.Optimizer, *, batch_size: int = 128) -> float:
    model.train()
    total_loss = 0.0
    batches = 0
    order = torch.randperm(len(rows)).tolist()
    for start in range(0, len(order), batch_size):
        items = [rows[i] for i in order[start:start + batch_size]]
        optimizer.zero_grad(set_to_none=True)
        before, after, actions = _batch_tensors(model, items)
        logits = model.program_execute_logits(before, actions)
        loss = F.cross_entropy(logits.reshape(-1, model.program_executor_value_vocab), after.reshape(-1))
        loss.backward()
        params = [parameter for parameter in model.parameters() if parameter.requires_grad]
        if params:
            torch.nn.utils.clip_grad_norm_(params, 1.0)
        optimizer.step()
        total_loss += float(loss.detach())
        batches += 1
    return total_loss / max(1, batches)


def operator_executor_internal_gate(metrics: dict[str, object]) -> bool:
    if float(metrics['exact_vector_accuracy']) < 0.98:
        return False
    if float(metrics['element_accuracy']) < 0.995:
        return False
    operators = metrics.get('operators', {})
    if not isinstance(operators, dict) or not operators:
        return False
    return all(float(row['exact_vector_accuracy']) >= 0.95 for row in operators.values())
