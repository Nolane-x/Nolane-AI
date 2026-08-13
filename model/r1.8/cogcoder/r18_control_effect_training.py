from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import Tensor

from .neural_system2 import (
    NeuralSystem2Workspace,
    encode_action_descriptions,
    encode_structured_observation,
    project_causal_role_effects,
    structured_numeric_delta_sketch,
    structured_numeric_state_sketch,
)
from .r18_benchmark import R18Task, oracle_plan
from .r18_causal_memory import ConditionalEvidenceMemory, public_context_fingerprint
from .r18_control_state import infer_controllable_effect_projection


@dataclass(frozen=True)
class ControlEffectTrainingStep:
    hidden: Tensor
    target_effects: Tensor
    baseline_effects: Tensor
    predict_mask: Tensor


@dataclass(frozen=True)
class ControlEffectEpisode:
    task_id: str
    family: str
    steps: tuple[ControlEffectTrainingStep, ...]


def control_effect_trainable_parameter_names(model: NeuralSystem2Workspace) -> list[str]:
    allowed = {
        "conditional_control_effect_head.weight",
        "conditional_control_effect_head.bias",
    }
    names = [name for name, _ in model.named_parameters() if name in allowed]
    if set(names) != allowed:
        raise ValueError("model does not expose the expected conditional control-effect head")
    return names


def configure_control_effect_training(model: NeuralSystem2Workspace) -> list[str]:
    names = control_effect_trainable_parameter_names(model)
    allowed = set(names)
    for name, parameter in model.named_parameters():
        parameter.requires_grad_(name in allowed)
    return names


def _public_state(text: str, *, sketch_dim: int) -> tuple[Tensor, Tensor, Tensor]:
    ids, values = encode_structured_observation(text, max_atoms=96)
    ids_b = ids.unsqueeze(0)
    values_b = values.unsqueeze(0)
    state = structured_numeric_state_sketch(ids_b, values_b, sketch_dim=sketch_dim)
    return ids_b, values_b, state.squeeze(0)


def _counterfactual_structured_effects(
    task: R18Task,
    before_ids: Tensor,
    before_values: Tensor,
    action_count: int,
    sketch_dim: int,
) -> Tensor:
    rows: list[Tensor] = []
    for action_index in range(action_count):
        branch = copy.deepcopy(task)
        branch.step(action_index)
        after_ids, after_values = encode_structured_observation(
            branch.render_observation(), max_atoms=96
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


def _safe_exploration_action(task: R18Task, candidates: list[int], counts: list[int]) -> int:
    for action_index in sorted(candidates, key=lambda index: (counts[index], index)):
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


def collect_control_effect_episode(
    model: NeuralSystem2Workspace,
    task: R18Task,
    *,
    exploration_steps: int = 6,
    max_steps: int = 16,
) -> ControlEffectEpisode:
    """Collect train-only control-relevant successor-effect supervision.

    A role projection is inferred only from an actually observed public transition.
    Once discovered, the structural projection is reused within the episode so
    every legal train-only counterfactual action can be scored in the same 64D
    controllable coordinates. Ambiguous/no-change transitions do not invent a role.
    """
    if task.split != "train":
        raise ValueError("control-effect collector only accepts train split tasks")
    if exploration_steps < 0 or max_steps < 1:
        raise ValueError("invalid exploration/max_steps")

    model.eval()
    action_tokens = encode_action_descriptions(task.action_descriptions, max_bytes=64).unsqueeze(0)
    with torch.no_grad():
        action_embeddings = model.action_encoder(action_tokens)[0].detach().cpu()
    action_count = int(action_embeddings.shape[0])
    non_submit = [
        index
        for index, description in enumerate(task.action_descriptions)
        if "submit" not in description.lower()
    ]
    predict_mask = torch.tensor(
        ["submit" not in description.lower() for description in task.action_descriptions],
        dtype=torch.bool,
    )
    counts = [0 for _ in range(action_count)]
    memory = ConditionalEvidenceMemory(
        action_count=action_count,
        effect_dim=model.psr_sketch_dim,
    )
    projection: Tensor | None = None
    rows: list[ControlEffectTrainingStep] = []

    while not task.done and sum(counts) < max_steps:
        before_text = task.render_observation()
        before_ids, before_values, state_sketch = _public_state(
            before_text, sketch_dim=model.psr_sketch_dim
        )
        context = public_context_fingerprint(
            before_text, dims=model.conditional_law_context_dim
        )
        evidence_rows: list[Tensor] = []
        meta_rows: list[Tensor] = []
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
        target_structured = _counterfactual_structured_effects(
            task,
            before_ids,
            before_values,
            action_count,
            model.psr_sketch_dim,
        )
        with torch.no_grad():
            law = model.conditional_law_scores(
                state_sketch.unsqueeze(0),
                context.unsqueeze(0),
                action_embeddings.unsqueeze(0),
                evidence_effects.unsqueeze(0),
                evidence_meta.unsqueeze(0),
            )
            hidden = law["hidden"][0].detach().cpu()

        executed = (
            _safe_exploration_action(task, non_submit, counts)
            if sum(counts) < exploration_steps and non_submit
            else int(oracle_plan(copy.deepcopy(task))[0])
        )
        result = task.step(executed)
        after_ids, after_values = encode_structured_observation(
            task.render_observation(), max_atoms=96
        )
        observed_structured = structured_numeric_delta_sketch(
            before_ids,
            before_values,
            after_ids.unsqueeze(0),
            after_values.unsqueeze(0),
            sketch_dim=model.psr_sketch_dim,
        ).squeeze(0).detach().cpu()

        inferred = infer_controllable_effect_projection(
            before_ids,
            before_values,
            after_ids.unsqueeze(0),
            after_values.unsqueeze(0),
            role_dim=64,
            source_dim=model.psr_sketch_dim,
        )
        if float(inferred["confidence"][0].item()) > 0.5:
            projection = inferred["effect_projection"].detach().cpu()

        if projection is not None:
            target_role = project_causal_role_effects(
                target_structured.unsqueeze(0), projection
            )[0].detach().cpu()
            baseline_role = project_causal_role_effects(
                evidence_effects.unsqueeze(0), projection
            )[0].detach().cpu()
            rows.append(
                ControlEffectTrainingStep(
                    hidden=hidden,
                    target_effects=target_role,
                    baseline_effects=baseline_role,
                    predict_mask=predict_mask.clone(),
                )
            )

        memory.update(executed, context, state_sketch, observed_structured)
        counts[executed] += 1
        if result.done:
            break

    return ControlEffectEpisode(task_id=task.task_id, family=task.family, steps=tuple(rows))


def _flatten_rows(episodes):
    for episode in episodes:
        for step in episode.steps:
            for action_index in torch.nonzero(step.predict_mask, as_tuple=False).flatten().tolist():
                yield episode.family, step.hidden[action_index], step.target_effects[action_index], step.baseline_effects[action_index]


def evaluate_control_effect_episodes(
    model: NeuralSystem2Workspace,
    episodes,
    *,
    batch_size: int = 256,
) -> dict[str, object]:
    model.eval()
    family_rows: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"candidate_sq": 0.0, "baseline_sq": 0.0, "elements": 0, "rows": 0}
    )
    rows = list(_flatten_rows(episodes))
    with torch.no_grad():
        for start in range(0, len(rows), batch_size):
            items = rows[start : start + batch_size]
            hidden = torch.stack([item[1] for item in items]).unsqueeze(1)
            target = torch.stack([item[2] for item in items])
            baseline = torch.stack([item[3] for item in items])
            predicted = model.conditional_control_effect_scores(hidden).squeeze(1)
            for index, (family, _, _, _) in enumerate(items):
                pd = predicted[index] - target[index]
                bd = baseline[index] - target[index]
                slot = family_rows[family]
                slot["candidate_sq"] += float((pd * pd).sum().item())
                slot["baseline_sq"] += float((bd * bd).sum().item())
                slot["elements"] += int(pd.numel())
                slot["rows"] += 1

    def summarize(slot):
        denom = max(1, int(slot["elements"]))
        candidate = float(slot["candidate_sq"]) / denom
        baseline = float(slot["baseline_sq"]) / denom
        return {
            "candidate_mse": candidate,
            "baseline_mse": baseline,
            "relative_improvement": 1.0 - candidate / max(baseline, 1e-12),
            "elements": int(slot["elements"]),
            "rows": int(slot["rows"]),
        }

    families = {name: summarize(slot) for name, slot in sorted(family_rows.items())}
    total_candidate = sum(float(slot["candidate_sq"]) for slot in family_rows.values())
    total_baseline = sum(float(slot["baseline_sq"]) for slot in family_rows.values())
    total_elements = sum(int(slot["elements"]) for slot in family_rows.values())
    total_rows = sum(int(slot["rows"]) for slot in family_rows.values())
    candidate = total_candidate / max(1, total_elements)
    baseline = total_baseline / max(1, total_elements)
    return {
        "candidate_mse": candidate,
        "baseline_mse": baseline,
        "relative_improvement": 1.0 - candidate / max(baseline, 1e-12),
        "elements": total_elements,
        "rows": total_rows,
        "families": families,
    }


def train_control_effect_epoch(
    model: NeuralSystem2Workspace,
    episodes,
    optimizer: torch.optim.Optimizer,
    *,
    batch_size: int = 256,
) -> float:
    model.train()
    rows = list(_flatten_rows(episodes))
    if not rows:
        return 0.0
    order = torch.randperm(len(rows)).tolist()
    total = 0.0
    batches = 0
    for start in range(0, len(order), batch_size):
        items = [rows[index] for index in order[start : start + batch_size]]
        hidden = torch.stack([item[1] for item in items]).unsqueeze(1)
        target = torch.stack([item[2] for item in items])
        optimizer.zero_grad(set_to_none=True)
        predicted = model.conditional_control_effect_scores(hidden).squeeze(1)
        loss = F.mse_loss(predicted, target)
        loss.backward()
        params = [parameter for parameter in model.parameters() if parameter.requires_grad]
        if params:
            torch.nn.utils.clip_grad_norm_(params, 1.0)
        optimizer.step()
        total += float(loss.detach().item())
        batches += 1
    return total / max(1, batches)


def control_effect_internal_gate(
    metrics: dict[str, object],
    *,
    min_rows_per_family: int = 64,
) -> bool:
    if not float(metrics["candidate_mse"]) < float(metrics["baseline_mse"]):
        return False
    required = {
        "conditional_regimes",
        "regime_switch",
        "implicit_goal_regimes",
        "causal_prerequisites",
    }
    families = metrics.get("families", {})
    if not isinstance(families, dict) or set(families) != required:
        return False
    for row in families.values():
        if int(row.get("rows", 0)) < int(min_rows_per_family):
            return False
        if float(row["candidate_mse"]) > float(row["baseline_mse"]):
            return False
    return True
