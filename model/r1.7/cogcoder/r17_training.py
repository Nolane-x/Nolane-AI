from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import torch
from torch import Tensor

from .neural_system2 import (
    NeuralSystem2Workspace,
    encode_action_descriptions,
    encode_structured_observation,
    structured_numeric_delta_sketch,
    structured_numeric_state_sketch,
    system2_parameter_count,
)
from .r17_benchmark import R17Task, oracle_plan

R1_2_EFFECTIVE_PARAMETERS = 49_528_677
R17_PARAMETER_CEILING = 96_000_000
R17_CHECKPOINT_FORMAT = "nolane-r1.7-ncpm-v1"


@dataclass(frozen=True)
class CausalLawTrainingStep:
    state_sketch: Tensor
    action_embeddings: Tensor
    target_deltas: Tensor
    baseline_deltas: Tensor
    predict_mask: Tensor
    executed_action: int
    observed_delta: Tensor


@dataclass(frozen=True)
class CausalLawEpisode:
    task_id: str
    family: str
    steps: tuple[CausalLawTrainingStep, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _architecture(model: NeuralSystem2Workspace) -> dict[str, int | float]:
    return {
        "d_model": model.d_model,
        "workspace_dim": model.workspace_dim,
        "slot_count": model.slot_count,
        "n_heads": model.n_heads,
        "ff_mult": model.ff_mult,
        "action_embedding_dim": model.action_embedding_dim,
        "action_gru_hidden": model.action_gru_hidden,
        "observation_embedding_dim": model.observation_embedding_dim,
        "observation_gru_hidden": model.observation_gru_hidden,
        "action_memory_dim": model.action_memory_dim,
        "feedback_dim": model.feedback_dim,
        "structured_atom_dim": model.structured_atom_dim,
        "structured_layers": model.structured_layers,
        "failure_penalty_weight": model.failure_penalty_weight,
        "max_refinement_steps": model.max_refinement_steps,
    }


def causal_law_trainable_parameter_names(
    model: NeuralSystem2Workspace, *, include_policy: bool = False
) -> list[str]:
    names: list[str] = []
    for name, _ in model.named_parameters():
        if not name.startswith("causal_law_"):
            continue
        if not include_policy and (
            name == "causal_law_policy_scale" or name.startswith("causal_law_policy_head.")
        ):
            continue
        names.append(name)
    if not names:
        raise ValueError("model exposes no causal_law_ parameters")
    return names


def _state_tensors(task: R17Task) -> tuple[Tensor, Tensor, Tensor]:
    ids, values = encode_structured_observation(task.render_observation(), max_atoms=96)
    ids = ids.unsqueeze(0)
    values = values.unsqueeze(0)
    sketch = structured_numeric_state_sketch(ids, values, sketch_dim=128).squeeze(0)
    return ids, values, sketch


def _counterfactual_delta(
    task: R17Task,
    action_index: int,
    previous_ids: Tensor,
    previous_values: Tensor,
) -> Tensor:
    branch = copy.deepcopy(task)
    branch.step(int(action_index))
    current_ids, current_values = encode_structured_observation(
        branch.render_observation(), max_atoms=96
    )
    return structured_numeric_delta_sketch(
        previous_ids,
        previous_values,
        current_ids.unsqueeze(0),
        current_values.unsqueeze(0),
        sketch_dim=128,
    ).squeeze(0)


def collect_causal_law_episode(
    model: NeuralSystem2Workspace,
    task: R17Task,
    *,
    exploration_steps: int = 6,
    max_steps: int | None = None,
) -> CausalLawEpisode:
    """Collect leakage-free train supervision from public transitions.

    Simulator internals are used only by ``oracle_plan`` to choose a teacher
    action after the exploration prefix. Every neural input/target tensor is
    constructed from public observations and public action descriptions.
    """
    if task.split != "train":
        raise ValueError("causal-law training collector only accepts train split tasks")
    if exploration_steps < 0:
        raise ValueError("exploration_steps must be non-negative")
    if max_steps is None:
        max_steps = max(1, min(18, int(task.observe()["budget_remaining"])))
    if max_steps < 1:
        raise ValueError("max_steps must be positive")

    model.eval()
    action_tokens = encode_action_descriptions(task.action_descriptions, max_bytes=64).unsqueeze(0)
    with torch.no_grad():
        action_embeddings = model.action_encoder(action_tokens).squeeze(0).detach().cpu()

    action_count = len(task.action_descriptions)
    non_submit = [
        i for i, description in enumerate(task.action_descriptions)
        if "submit" not in description.lower()
    ]
    last_effect = torch.zeros(action_count, 128, dtype=torch.float32)
    observed_counts = [0 for _ in range(action_count)]
    steps: list[CausalLawTrainingStep] = []

    while not task.done and len(steps) < int(max_steps):
        previous_ids, previous_values, state_sketch = _state_tensors(task)
        targets = torch.stack(
            [
                _counterfactual_delta(task, action_index, previous_ids, previous_values)
                for action_index in range(action_count)
            ],
            dim=0,
        ).detach().cpu()
        predict_mask = torch.tensor(
            ["submit" not in description.lower() for description in task.action_descriptions],
            dtype=torch.bool,
        )
        baseline = last_effect.clone()

        if len(steps) < exploration_steps and non_submit:
            executed = min(non_submit, key=lambda index: (observed_counts[index], index))
        else:
            plan = oracle_plan(copy.deepcopy(task))
            executed = int(plan[0])

        result = task.step(executed)
        observed_delta = targets[executed].clone()
        last_effect[executed] = observed_delta
        observed_counts[executed] += 1
        steps.append(
            CausalLawTrainingStep(
                state_sketch=state_sketch.detach().cpu(),
                action_embeddings=action_embeddings.clone(),
                target_deltas=targets,
                baseline_deltas=baseline,
                predict_mask=predict_mask,
                executed_action=executed,
                observed_delta=observed_delta,
            )
        )
        if result.done:
            break

    return CausalLawEpisode(task_id=task.task_id, family=task.family, steps=tuple(steps))


def save_r17_checkpoint(
    path: Path,
    model: NeuralSystem2Workspace,
    *,
    r1_2_checkpoint: Path,
    r1_6_parent_checkpoint: Path,
    report: Mapping[str, object] | None = None,
) -> dict[str, object]:
    r12 = Path(r1_2_checkpoint)
    r16 = Path(r1_6_parent_checkpoint)
    if not r12.is_file():
        raise FileNotFoundError(r12)
    if not r16.is_file():
        raise FileNotFoundError(r16)
    system2_parameters = system2_parameter_count(model)
    candidate = R1_2_EFFECTIVE_PARAMETERS + system2_parameters
    if candidate >= R17_PARAMETER_CEILING:
        raise RuntimeError(
            f"R1.7 candidate violates parameter ceiling: {candidate:,} >= {R17_PARAMETER_CEILING:,}"
        )
    payload = {
        "format": R17_CHECKPOINT_FORMAT,
        "architecture": _architecture(model),
        "r1_2_sha256": sha256_file(r12),
        "r1_6_parent_sha256": sha256_file(r16),
        "r1_2_effective_parameters": R1_2_EFFECTIVE_PARAMETERS,
        "system2_parameters": system2_parameters,
        "candidate_effective_parameters": candidate,
        "model_state": {name: value.detach().cpu() for name, value in model.state_dict().items()},
        "report": dict(report or {}),
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    meta = {key: value for key, value in payload.items() if key != "model_state"}
    meta.update({"sha256": sha256_file(path), "bytes": path.stat().st_size})
    return meta


def load_r17_checkpoint(
    path: Path,
    *,
    expected_r1_2_checkpoint: Path | None = None,
    expected_r1_6_parent_checkpoint: Path | None = None,
) -> tuple[NeuralSystem2Workspace, dict[str, object]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=False)
    if payload.get("format") != R17_CHECKPOINT_FORMAT:
        raise RuntimeError("unsupported R1.7 NCPM checkpoint")
    if expected_r1_2_checkpoint is not None:
        if sha256_file(Path(expected_r1_2_checkpoint)) != payload.get("r1_2_sha256"):
            raise RuntimeError("R1.2 parent checkpoint SHA-256 mismatch")
    if expected_r1_6_parent_checkpoint is not None:
        if sha256_file(Path(expected_r1_6_parent_checkpoint)) != payload.get("r1_6_parent_sha256"):
            raise RuntimeError("R1.6 parent checkpoint SHA-256 mismatch")
    architecture = payload["architecture"]
    model = NeuralSystem2Workspace(**architecture)
    model.load_state_dict(payload["model_state"], strict=True)
    meta = {key: value for key, value in payload.items() if key != "model_state"}
    return model, meta
