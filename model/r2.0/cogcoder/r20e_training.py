from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import torch
import torch.nn.functional as F
from torch import Tensor

from .neural_system2 import (
    NeuralSystem2Workspace,
    encode_action_descriptions,
    encode_structured_observation,
    structured_numeric_delta_sketch,
)
from .r18_benchmark import R18Task, oracle_plan
from .r18_causal_memory import ConditionalEvidenceMemory, public_context_fingerprint
from .r18_training import _public_state
from .r19_frontier import FrontierRolloutHead
from .r20e_executive import EvidenceEffectExecutive, r20e_parameter_count
from .r20e_imagination import EvidenceConditionedImaginationPlanner

R19_EFFECTIVE_PARAMETERS = 78_214_173
R20E_EFFECTIVE_PARAMETERS = 78_779_253
R20E_CHECKPOINT_FORMAT = "nolane-r2.0e-evidence-effect-executive-v1"
_DEPTH_VALUES = EvidenceEffectExecutive.depth_values


@dataclass(frozen=True)
class EvidenceEffectStep:
    state: Tensor
    context: Tensor
    action_embeddings: Tensor
    parent_effects: Tensor
    imagined_effects: Tensor
    imagined_uncertainty: Tensor
    imagined_value: Tensor
    evidence_effects: Tensor
    evidence_meta: Tensor
    action_memory: Tensor
    progress: Tensor
    budget_fraction: Tensor
    previous_feedback: Tensor
    target_action: int
    target_depth_index: int
    stop_target: float
    success_target: float


@dataclass(frozen=True)
class EvidenceEffectEpisode:
    task_id: str
    family: str
    steps: tuple[EvidenceEffectStep, ...]


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _depth_index(plan_length: int) -> int:
    length = max(1, int(plan_length))
    for index, depth in enumerate(_DEPTH_VALUES):
        if length <= depth:
            return index
    return len(_DEPTH_VALUES) - 1


def _evidence_tensors(memory: ConditionalEvidenceMemory, context: Tensor, action_count: int) -> tuple[Tensor, Tensor, list[object]]:
    effects = []
    meta = []
    lookups = []
    for action in range(action_count):
        lookup = memory.retrieve(action, context)
        lookups.append(lookup)
        effects.append(lookup.effect)
        meta.append(torch.tensor([min(1.0, lookup.count / 4.0), lookup.consistency, lookup.context_similarity], dtype=torch.float32))
    return torch.stack(effects), torch.stack(meta), lookups


def _action_memory(
    lookups: Sequence[object],
    *,
    last_progress: list[float],
    progress_counts: list[int],
    last_information: list[float],
    failures: list[int],
    attempts: list[int],
) -> Tensor:
    rows = []
    for action, lookup in enumerate(lookups):
        rows.append(
            torch.tensor(
                [
                    min(1.0, float(lookup.count) / 4.0),
                    float(lookup.consistency),
                    float(lookup.context_similarity),
                    float(last_progress[action]),
                    min(1.0, float(progress_counts[action]) / 4.0),
                    float(last_information[action]),
                    float(failures[action]) / max(1.0, float(attempts[action])),
                ],
                dtype=torch.float32,
            )
        )
    return torch.stack(rows)


def _imagined_tensors(
    planner: EvidenceConditionedImaginationPlanner,
    *,
    state: Tensor,
    context: Tensor,
    action_embeddings: Tensor,
    evidence_effects: Tensor,
    evidence_meta: Tensor,
    depth: int,
) -> tuple[Tensor, Tensor, Tensor]:
    actions = tuple(range(action_embeddings.shape[0]))
    result = planner.imagine_actions(
        state=state,
        context=context,
        action_embeddings=action_embeddings,
        evidence_effects=evidence_effects,
        evidence_meta=evidence_meta,
        legal_actions=actions,
        depths=(int(depth),),
    )
    rows = sorted(result.by_depth[int(depth)], key=lambda row: row.first_action)
    effects = torch.tensor([row.effect for row in rows], dtype=torch.float32)
    uncertainty = torch.tensor([row.uncertainty for row in rows], dtype=torch.float32)
    value = torch.tensor([row.value for row in rows], dtype=torch.float32)
    return effects, uncertainty, value


def collect_evidence_effect_episode(
    parent: NeuralSystem2Workspace,
    planner: EvidenceConditionedImaginationPlanner,
    task: R18Task,
    *,
    max_states: int = 16,
    training_depth: int = 2,
) -> EvidenceEffectEpisode:
    """Collect full-trajectory train supervision from public tensors only.

    The oracle chooses the teacher action but is never serialized into a row.
    Memory/evidence is updated only from the public transition produced after a
    real teacher action.
    """
    if task.split != "train":
        raise ValueError("R2.0e collector accepts train split only")
    if max_states < 1:
        raise ValueError("max_states must be positive")
    if training_depth not in _DEPTH_VALUES:
        raise ValueError("training_depth must be one of the locked depths")

    parent.eval()
    descriptions = tuple(str(x) for x in task.action_descriptions)
    action_tokens = encode_action_descriptions(descriptions, max_bytes=64).unsqueeze(0)
    with torch.no_grad():
        action_embeddings = parent.action_encoder(action_tokens)[0].detach().cpu()
    action_count = len(descriptions)
    evidence_memory = ConditionalEvidenceMemory(action_count=action_count, effect_dim=parent.psr_sketch_dim)
    last_progress = [0.0] * action_count
    progress_counts = [0] * action_count
    last_information = [0.0] * action_count
    failures = [0] * action_count
    attempts = [0] * action_count
    previous_feedback = torch.zeros(3, dtype=torch.float32)
    initial_budget = max(1.0, float(task.observe()["budget_remaining"]))
    steps: list[EvidenceEffectStep] = []

    while not task.done and len(steps) < int(max_states):
        obs = task.observe()
        before_text = task.render_observation()
        before_ids, before_values, state = _public_state(before_text, sketch_dim=parent.psr_sketch_dim)
        context = public_context_fingerprint(before_text, dims=parent.conditional_law_context_dim)
        evidence_effects, evidence_meta, lookups = _evidence_tensors(evidence_memory, context, action_count)
        parent_effects = planner.parent_effects(state, context, action_embeddings, evidence_effects, evidence_meta).detach().cpu()
        imagined_effects, imagined_uncertainty, imagined_value = _imagined_tensors(
            planner,
            state=state,
            context=context,
            action_embeddings=action_embeddings,
            evidence_effects=evidence_effects,
            evidence_meta=evidence_meta,
            depth=training_depth,
        )
        memory_features = _action_memory(
            lookups,
            last_progress=last_progress,
            progress_counts=progress_counts,
            last_information=last_information,
            failures=failures,
            attempts=attempts,
        )
        plan = oracle_plan(copy.deepcopy(task))
        if not plan:
            break
        target_action = int(plan[0])
        target_depth_index = _DEPTH_VALUES.index(int(training_depth))
        stop_target = 1.0 if "submit" in descriptions[target_action].lower() else 0.0
        success_target = 1.0 if stop_target > 0.5 else 0.0
        steps.append(
            EvidenceEffectStep(
                state=state.detach().cpu(),
                context=context.detach().cpu(),
                action_embeddings=action_embeddings.clone(),
                parent_effects=parent_effects.clone(),
                imagined_effects=imagined_effects.clone(),
                imagined_uncertainty=imagined_uncertainty.clone(),
                imagined_value=imagined_value.clone(),
                evidence_effects=evidence_effects.clone(),
                evidence_meta=evidence_meta.clone(),
                action_memory=memory_features.clone(),
                progress=torch.tensor([float(obs["progress_signal"])], dtype=torch.float32),
                budget_fraction=torch.tensor([float(obs["budget_remaining"]) / initial_budget], dtype=torch.float32),
                previous_feedback=previous_feedback.clone(),
                target_action=target_action,
                target_depth_index=target_depth_index,
                stop_target=stop_target,
                success_target=success_target,
            )
        )

        result = task.step(target_action)
        after_ids, after_values = encode_structured_observation(task.render_observation(), max_atoms=96)
        observed = structured_numeric_delta_sketch(
            before_ids,
            before_values,
            after_ids.unsqueeze(0),
            after_values.unsqueeze(0),
            sketch_dim=parent.psr_sketch_dim,
        ).squeeze(0).detach().cpu()
        evidence_memory.update(target_action, context, state, observed)
        attempts[target_action] += 1
        last_progress[target_action] = float(result.progress_delta)
        progress_counts[target_action] += 1
        last_information[target_action] = float(result.information_gain)
        failures[target_action] += int(result.failed)
        previous_feedback = torch.tensor(
            [float(result.progress_delta), float(result.information_gain), float(result.failed)],
            dtype=torch.float32,
        )
        if result.done:
            break

    return EvidenceEffectEpisode(task_id=task.task_id, family=task.family, steps=tuple(steps))


def configure_r20e_training(parent: NeuralSystem2Workspace, rollout: FrontierRolloutHead, executive: EvidenceEffectExecutive) -> list[str]:
    for parameter in parent.parameters():
        parameter.requires_grad_(False)
    for parameter in rollout.parameters():
        parameter.requires_grad_(False)
    names = []
    for name, parameter in executive.named_parameters():
        parameter.requires_grad_(True)
        names.append(name)
    return names


def _step_forward(executive: EvidenceEffectExecutive, row: EvidenceEffectStep, recurrent: Tensor) -> dict[str, Tensor]:
    return executive(
        state=row.state.unsqueeze(0),
        context=row.context.unsqueeze(0),
        action_embeddings=row.action_embeddings.unsqueeze(0),
        parent_effects=row.parent_effects.unsqueeze(0),
        imagined_effects=row.imagined_effects.unsqueeze(0),
        imagined_uncertainty=row.imagined_uncertainty.unsqueeze(0),
        imagined_value=row.imagined_value.unsqueeze(0),
        evidence_effects=row.evidence_effects.unsqueeze(0),
        action_memory=row.action_memory.unsqueeze(0),
        progress=row.progress.unsqueeze(0),
        budget_fraction=row.budget_fraction.unsqueeze(0),
        previous_feedback=row.previous_feedback.unsqueeze(0),
        recurrent_state=recurrent,
    )


def _losses(out: dict[str, Tensor], row: EvidenceEffectStep) -> tuple[Tensor, dict[str, float]]:
    action = F.cross_entropy(out["action_logits"], torch.tensor([row.target_action], dtype=torch.long))
    depth = F.cross_entropy(out["depth_logits"], torch.tensor([row.target_depth_index], dtype=torch.long))
    stop = F.binary_cross_entropy_with_logits(out["stop_logit"], torch.tensor([row.stop_target], dtype=torch.float32))
    success = F.binary_cross_entropy(out["success_probability"].clamp(1e-6, 1 - 1e-6), torch.tensor([row.success_target], dtype=torch.float32))
    total = action + 0.2 * depth + 0.1 * stop + 0.05 * success
    return total, {"action": float(action.detach()), "depth": float(depth.detach()), "stop": float(stop.detach()), "success": float(success.detach())}


def train_r20e_epoch(
    executive: EvidenceEffectExecutive,
    episodes: Sequence[EvidenceEffectEpisode],
    optimizer: torch.optim.Optimizer,
    *,
    generator: torch.Generator,
) -> dict[str, float]:
    executive.train()
    order = torch.randperm(len(episodes), generator=generator).tolist()
    totals = {"loss": 0.0, "rows": 0, "action_correct": 0, "depth_correct": 0}
    for index in order:
        episode = episodes[index]
        if not episode.steps:
            continue
        recurrent = executive.init_state(batch_size=1)
        optimizer.zero_grad(set_to_none=True)
        losses = []
        for row in episode.steps:
            out = _step_forward(executive, row, recurrent)
            recurrent = out["next_state"]
            loss, _ = _losses(out, row)
            losses.append(loss)
            totals["rows"] += 1
            totals["action_correct"] += int(out["action_logits"].argmax(-1).item() == row.target_action)
            totals["depth_correct"] += int(out["depth_logits"].argmax(-1).item() == row.target_depth_index)
        episode_loss = torch.stack(losses).mean()
        episode_loss.backward()
        torch.nn.utils.clip_grad_norm_(executive.parameters(), max_norm=1.0)
        optimizer.step()
        totals["loss"] += float(episode_loss.detach()) * len(episode.steps)
    rows = max(1, int(totals["rows"]))
    return {
        "loss": float(totals["loss"]) / rows,
        "rows": int(totals["rows"]),
        "action_accuracy": float(totals["action_correct"]) / rows,
        "depth_accuracy": float(totals["depth_correct"]) / rows,
    }


def evaluate_r20e(executive: EvidenceEffectExecutive, episodes: Sequence[EvidenceEffectEpisode]) -> dict[str, float]:
    executive.eval()
    total_loss = 0.0
    rows = 0
    action_correct = 0
    depth_correct = 0
    family = {}
    with torch.no_grad():
        for episode in episodes:
            recurrent = executive.init_state(batch_size=1)
            fam = family.setdefault(episode.family, {"rows": 0, "action_correct": 0, "loss": 0.0})
            for row in episode.steps:
                out = _step_forward(executive, row, recurrent)
                recurrent = out["next_state"]
                loss, _ = _losses(out, row)
                value = float(loss.item())
                total_loss += value
                rows += 1
                correct = int(out["action_logits"].argmax(-1).item() == row.target_action)
                action_correct += correct
                depth_correct += int(out["depth_logits"].argmax(-1).item() == row.target_depth_index)
                fam["rows"] += 1
                fam["action_correct"] += correct
                fam["loss"] += value
    denom = max(1, rows)
    return {
        "loss": total_loss / denom,
        "rows": rows,
        "action_accuracy": action_correct / denom,
        "depth_accuracy": depth_correct / denom,
        "families": {
            name: {
                "rows": int(data["rows"]),
                "loss": float(data["loss"]) / max(1, int(data["rows"])),
                "action_accuracy": float(data["action_correct"]) / max(1, int(data["rows"])),
            }
            for name, data in sorted(family.items())
        },
    }


def _architecture(executive: EvidenceEffectExecutive) -> dict[str, int]:
    return {
        "state_dim": executive.state_dim,
        "context_dim": executive.context_dim,
        "action_dim": executive.action_dim,
        "effect_dim": executive.effect_dim,
        "hidden_dim": executive.hidden_dim,
        "action_memory_dim": executive.action_memory_dim,
    }


def save_r20e_checkpoint(
    path: str | Path,
    executive: EvidenceEffectExecutive,
    *,
    parent_path: str | Path,
    report: dict[str, object],
) -> dict[str, object]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    parameter_count = r20e_parameter_count(executive)
    if parameter_count != 565_080:
        raise ValueError("unexpected R2.0e parameter count")
    payload = {
        "format": R20E_CHECKPOINT_FORMAT,
        "architecture": _architecture(executive),
        "parent_sha256": sha256_file(parent_path),
        "parent_effective_parameters": R19_EFFECTIVE_PARAMETERS,
        "executive_parameters": parameter_count,
        "candidate_effective_parameters": R19_EFFECTIVE_PARAMETERS + parameter_count,
        "executive_state": {name: value.detach().cpu() for name, value in executive.state_dict().items()},
        "report": report,
    }
    torch.save(payload, path)
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "parent_sha256": payload["parent_sha256"],
        "executive_parameters": parameter_count,
        "candidate_effective_parameters": payload["candidate_effective_parameters"],
    }


def load_r20e_checkpoint(path: str | Path, *, expected_parent_path: str | Path) -> tuple[EvidenceEffectExecutive, dict[str, object]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != R20E_CHECKPOINT_FORMAT:
        raise ValueError("unsupported R2.0e checkpoint format")
    if payload.get("parent_sha256") != sha256_file(expected_parent_path):
        raise ValueError("parent SHA-256 mismatch")
    executive = EvidenceEffectExecutive(**dict(payload["architecture"]))
    executive.load_state_dict(payload["executive_state"], strict=True)
    return executive, {key: value for key, value in payload.items() if key != "executive_state"}
