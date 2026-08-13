from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import Tensor

from .neural_system2 import NeuralSystem2Workspace


@dataclass(frozen=True)
class ProgramTrainingRow:
    template_id: int
    program_step: float
    base_logits: Tensor
    policy_features: Tensor
    label: int
    is_submit: bool


def build_program_rows(episodes, cached_rows, template_ids) -> list[ProgramTrainingRow]:
    """Align frozen cached policy features with raw program episodes exactly."""
    if len(episodes) != len(template_ids):
        raise ValueError("template_ids must align one-to-one with episodes")
    expected = sum(len(episode.steps) for episode in episodes)
    if len(cached_rows) != expected:
        raise ValueError("cached rows do not align with raw program steps")
    rows: list[ProgramTrainingRow] = []
    cursor = 0
    for episode, template_id in zip(episodes, template_ids):
        for program_step, step in enumerate(episode.steps):
            cached = cached_rows[cursor]
            cursor += 1
            if int(cached.label) != int(step.label):
                raise ValueError("cached teacher label does not align with raw program step")
            description = step.descriptions[int(step.label)]
            rows.append(
                ProgramTrainingRow(
                    template_id=int(template_id),
                    program_step=float(program_step),
                    base_logits=cached.base_logits.clone(),
                    policy_features=cached.policy_features.clone(),
                    label=int(step.label),
                    is_submit="submit" in description.lower(),
                )
            )
    return rows


def latent_program_trainable_parameter_names(model: NeuralSystem2Workspace) -> list[str]:
    names = [name for name, _ in model.named_parameters() if name.startswith("latent_program_ranker.")]
    if not names:
        raise ValueError("model exposes no latent_program_ranker parameters")
    return names


def _safe_accuracy(correct: int, total: int) -> float:
    return correct / max(1, total)


def evaluate_program_rows(
    model: NeuralSystem2Workspace,
    rows: list[ProgramTrainingRow] | tuple[ProgramTrainingRow, ...],
) -> dict[str, object]:
    """Compare standalone program ranking against frozen full-parent logits."""
    model.eval()
    candidate_operation_correct = baseline_operation_correct = 0
    candidate_operation_total = 0
    candidate_submit_correct = baseline_submit_correct = 0
    candidate_submit_total = 0
    template = defaultdict(lambda: [0, 0, 0])

    with torch.no_grad():
        for row in rows:
            scores = model.latent_program_rank_scores(
                row.policy_features.unsqueeze(0),
                torch.tensor([float(row.program_step)], dtype=torch.float32),
            )[0]
            candidate = int(scores.argmax().item())
            baseline = int(row.base_logits.argmax().item())
            if row.is_submit:
                candidate_submit_correct += int(candidate == row.label)
                baseline_submit_correct += int(baseline == row.label)
                candidate_submit_total += 1
            else:
                candidate_operation_correct += int(candidate == row.label)
                baseline_operation_correct += int(baseline == row.label)
                candidate_operation_total += 1
                slot = template[str(int(row.template_id))]
                slot[0] += int(candidate == row.label)
                slot[1] += int(baseline == row.label)
                slot[2] += 1

    templates = {
        name: {
            "candidate_operation_accuracy": _safe_accuracy(values[0], values[2]),
            "baseline_operation_accuracy": _safe_accuracy(values[1], values[2]),
            "operation_rows": values[2],
        }
        for name, values in template.items()
    }
    return {
        "candidate_operation_accuracy": _safe_accuracy(candidate_operation_correct, candidate_operation_total),
        "baseline_operation_accuracy": _safe_accuracy(baseline_operation_correct, candidate_operation_total),
        "candidate_submit_accuracy": _safe_accuracy(candidate_submit_correct, candidate_submit_total),
        "baseline_submit_accuracy": _safe_accuracy(baseline_submit_correct, candidate_submit_total),
        "operation_rows": candidate_operation_total,
        "submit_rows": candidate_submit_total,
        "templates": templates,
    }


def train_program_epoch(
    model: NeuralSystem2Workspace,
    rows: list[ProgramTrainingRow] | tuple[ProgramTrainingRow, ...],
    optimizer: torch.optim.Optimizer,
) -> float:
    """Train standalone next-action program ranking over frozen relational features."""
    model.train()
    grouped: dict[int, list[ProgramTrainingRow]] = defaultdict(list)
    for row in rows:
        grouped[int(row.base_logits.shape[0])].append(row)
    optimizer.zero_grad(set_to_none=True)
    losses = []
    for items in grouped.values():
        features = torch.stack([row.policy_features for row in items])
        steps = torch.tensor([float(row.program_step) for row in items], dtype=torch.float32)
        labels = torch.tensor([int(row.label) for row in items], dtype=torch.long)
        scores = model.latent_program_rank_scores(features, steps)
        losses.append(F.cross_entropy(scores, labels))
    if not losses:
        return 0.0
    loss = torch.stack(losses).mean()
    loss.backward()
    params = [parameter for parameter in model.parameters() if parameter.requires_grad]
    if params:
        torch.nn.utils.clip_grad_norm_(params, 1.0)
    optimizer.step()
    return float(loss.detach())


def latent_program_internal_gate(metrics: dict[str, object]) -> bool:
    if not float(metrics["candidate_operation_accuracy"]) > float(metrics["baseline_operation_accuracy"]):
        return False
    if float(metrics["candidate_submit_accuracy"]) < float(metrics["baseline_submit_accuracy"]):
        return False
    templates = metrics.get("templates", {})
    if not isinstance(templates, dict) or set(templates) != {"6", "7"}:
        return False
    for row in templates.values():
        if float(row["candidate_operation_accuracy"]) < float(row["baseline_operation_accuracy"]):
            return False
    return True
