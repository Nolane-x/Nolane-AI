from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor
import torch.nn.functional as F

from native_core import PublicActionMemory, encode_public_state, state_dict_sha256
from successor_core import PublicTransitionTrace
from attributed_core import PublicActionAttributedTrace
from public_planner import GOAL_HYPOTHESIS_COUNT, PublicGoalConsistencyBelief
from causal_version_space import PublicCausalRuleMemory, choose_public_causal_action
from goal_belief_core import (
    NativeR21GoalBeliefEnsemble,
    encode_public_goal_features,
    fuse_public_and_neural_posterior,
    goal_index,
)

R11_HORIZON = 1
CHECKPOINT_FORMAT = "nolane-neural-vnext-native-r21-supervised-goal-belief-v1"


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class PublicEpisodeState:
    exact_memory: PublicActionMemory
    causal_memory: PublicCausalRuleMemory
    trace: PublicTransitionTrace
    attributed: PublicActionAttributedTrace
    belief: PublicGoalConsistencyBelief
    hidden: Tensor
    previous_feedback: list[float]


def _new_state(parent: Any, task: Any) -> PublicEpisodeState:
    return PublicEpisodeState(
        exact_memory=PublicActionMemory(len(task.action_descriptions)),
        causal_memory=PublicCausalRuleMemory(),
        trace=PublicTransitionTrace(max_length=parent.parent.parent.trace_length),
        attributed=PublicActionAttributedTrace(max_length=parent.parent.attribution_length),
        belief=PublicGoalConsistencyBelief(),
        hidden=parent.init_parent_hidden(1),
        previous_feedback=[0.0, 0.0, 0.0],
    )


def _public_step_context(parent: Any, state: PublicEpisodeState, observation: Mapping[str, Any]):
    state.belief.update(observation)
    global_features, action_features, valid = encode_public_state(
        observation,
        state.exact_memory,
        previous_feedback=state.previous_feedback,
    )
    trace_features, trace_valid = state.trace.encode()
    attribution_features, attribution_valid = state.attributed.encode()
    with torch.no_grad():
        parent_output = parent.forward_step(
            global_features.unsqueeze(0),
            action_features.unsqueeze(0),
            valid.unsqueeze(0),
            state.hidden,
            trace_features.unsqueeze(0),
            trace_valid.unsqueeze(0),
            attribution_features.unsqueeze(0),
            attribution_valid.unsqueeze(0),
        )
    state.hidden = parent_output["next_parent_hidden"].detach()
    public_posterior = state.belief.encode()
    action, decision = choose_public_causal_action(
        observation=observation,
        exact_memory=state.exact_memory,
        causal_memory=state.causal_memory,
        posterior=public_posterior,
        parent_logits=parent_output["action_logits"][0],
        horizon=R11_HORIZON,
    )
    return global_features, action_features, valid, parent_output, public_posterior, int(action), decision


def _advance(state: PublicEpisodeState, task: Any, observation: Mapping[str, Any], action_features: Tensor, action: int) -> None:
    selected = action_features[int(action)].detach().clone()
    result = task.step(int(action))
    after = result.observation
    state.exact_memory.update(
        action=int(action), before=observation, after=after,
        progress_delta=result.progress_delta, information_gain=result.information_gain, failed=result.failed,
    )
    state.causal_memory.update(action=int(action), before=observation, after=after)
    state.trace.update(
        before=observation, after=after,
        progress_delta=result.progress_delta, information_gain=result.information_gain, failed=result.failed,
    )
    state.attributed.update(
        selected_action_features=selected, before=observation, after=after,
        progress_delta=result.progress_delta, information_gain=result.information_gain, failed=result.failed,
    )
    state.previous_feedback = [
        float(result.progress_delta),
        float(result.information_gain),
        float(result.failed),
    ]


def _private_train_goal_label(task: Any) -> int:
    if getattr(task, "split", None) != "train":
        raise ValueError("private goal labels are train-only")
    if getattr(task, "family", None) != "implicit_goal_regimes":
        raise ValueError("private goal labels are hidden-goal-family only")
    if "target" in task.observe():
        raise ValueError("implicit-goal training observation unexpectedly exposes target")
    goal = getattr(task, "_goal", None)
    if not isinstance(goal, tuple) or len(goal) != 3:
        raise ValueError("train-only private goal label unavailable")
    return goal_index(goal)


def collect_r11_goal_dataset(
    parent: Any,
    *,
    make_task: Any,
    indices: tuple[int, int],
) -> dict[str, Tensor]:
    features: list[Tensor] = []
    supports: list[Tensor] = []
    labels: list[int] = []
    episode_rows = 0
    for index in range(int(indices[0]), int(indices[1]) + 1):
        task = make_task("implicit_goal_regimes", "train", int(index))
        label = _private_train_goal_label(task)
        state = _new_state(parent, task)
        episode_rows += 1
        while not task.done:
            observation = task.observe()
            _, action_features, _, _, public_posterior, r11_action, _ = _public_step_context(
                parent, state, observation
            )
            support_mask = public_posterior > 0.0
            if not bool(support_mask[label]):
                raise AssertionError("true train goal fell outside exact public support")
            features.append(
                encode_public_goal_features(
                    support_mask=support_mask,
                    observation=dict(observation),
                    previous_feedback=state.previous_feedback,
                )
            )
            supports.append(support_mask.detach().clone())
            labels.append(int(label))
            _advance(state, task, observation, action_features, r11_action)
    return {
        "features": torch.stack(features, dim=0),
        "support_mask": torch.stack(supports, dim=0),
        "labels": torch.tensor(labels, dtype=torch.long),
        "episodes": torch.tensor([episode_rows], dtype=torch.long),
    }


def train_goal_ensemble(
    model: NativeR21GoalBeliefEnsemble,
    dataset: Mapping[str, Tensor],
    *,
    seed: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
) -> dict[str, Any]:
    features = dataset["features"]
    support = dataset["support_mask"].bool()
    labels = dataset["labels"].long()
    rows = int(features.shape[0])
    summaries = []
    for head_index, head in enumerate(model.heads):
        torch.manual_seed(int(seed) + 97 * head_index)
        optimizer = torch.optim.AdamW(
            head.parameters(),
            lr=float(learning_rate),
            weight_decay=float(weight_decay),
        )
        rng = random.Random(int(seed) + 1009 * head_index)
        history = []
        for epoch in range(int(epochs)):
            order = list(range(rows))
            rng.shuffle(order)
            losses = []
            correct = 0
            seen = 0
            head.train()
            for start in range(0, rows, int(batch_size)):
                ids = torch.tensor(order[start : start + int(batch_size)], dtype=torch.long)
                x = features.index_select(0, ids)
                mask = support.index_select(0, ids)
                y = labels.index_select(0, ids)
                logits = head(x)
                logits = logits.masked_fill(~mask, torch.finfo(logits.dtype).min)
                loss = F.cross_entropy(logits, y)
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
                optimizer.step()
                losses.append(float(loss.detach().item()))
                pred = logits.detach().argmax(dim=-1)
                correct += int((pred == y).sum().item())
                seen += int(y.numel())
            history.append({
                "epoch": epoch + 1,
                "mean_loss": sum(losses) / max(1, len(losses)),
                "accuracy": correct / max(1, seen),
            })
        summaries.append({"head": head_index, "history": history})
    model.eval()
    return {
        "rows": rows,
        "episodes": int(dataset["episodes"][0].item()),
        "heads": summaries,
    }


def _ensemble_nll(
    model: NativeR21GoalBeliefEnsemble,
    dataset: Mapping[str, Tensor],
    *,
    temperature: float,
) -> tuple[float, float]:
    model.eval()
    features = dataset["features"]
    support = dataset["support_mask"].bool()
    labels = dataset["labels"].long()
    with torch.no_grad():
        logits = model.ensemble_logits(features)
        masked = logits.masked_fill(
            ~support.unsqueeze(0),
            torch.finfo(logits.dtype).min,
        )
        probs = torch.softmax(masked / float(temperature), dim=-1).mean(dim=0)
        chosen = probs.gather(1, labels[:, None]).squeeze(1).clamp_min(1.0e-12)
        nll = float((-chosen.log()).mean().item())
        accuracy = float((probs.argmax(dim=-1) == labels).float().mean().item())
    return nll, accuracy


def calibrate_temperature(
    model: NativeR21GoalBeliefEnsemble,
    dataset: Mapping[str, Tensor],
    *,
    candidates: Sequence[float],
) -> dict[str, Any]:
    rows = []
    for value in candidates:
        nll, accuracy = _ensemble_nll(model, dataset, temperature=float(value))
        rows.append({"temperature": float(value), "nll": nll, "top1_accuracy": accuracy})
    selected = min(rows, key=lambda row: (row["nll"], row["temperature"]))
    return {"selected_temperature": selected["temperature"], "candidates": rows}


def rollout_r21(
    parent: Any,
    model: NativeR21GoalBeliefEnsemble,
    task: Any,
    *,
    beta: float,
    temperature: float,
    max_support: int,
) -> dict[str, Any]:
    state = _new_state(parent, task)
    overrides = 0
    fused_steps = 0
    while not task.done:
        observation = task.observe()
        _, action_features, _, parent_output, public_posterior, r11_action, r11_decision = _public_step_context(
            parent, state, observation
        )
        action = int(r11_action)
        support_count = int((public_posterior > 0.0).sum().item())
        hidden = not isinstance(observation.get("target"), list)
        if (
            hidden
            and support_count <= int(max_support)
            and r11_decision.get("reason") != "r9_public_progress_complete"
        ):
            support_mask = public_posterior > 0.0
            features = encode_public_goal_features(
                support_mask=support_mask,
                observation=dict(observation),
                previous_feedback=state.previous_feedback,
            )
            with torch.no_grad():
                neural = model.posterior(
                    features=features,
                    support_mask=support_mask,
                    temperature=float(temperature),
                )
            fused = fuse_public_and_neural_posterior(
                public_posterior,
                neural,
                beta=float(beta),
            )
            action, _decision = choose_public_causal_action(
                observation=observation,
                exact_memory=state.exact_memory,
                causal_memory=state.causal_memory,
                posterior=fused,
                parent_logits=parent_output["action_logits"][0],
                horizon=R11_HORIZON,
            )
            fused_steps += 1
            overrides += int(int(action) != int(r11_action))
        _advance(state, task, observation, action_features, int(action))
    return {
        "solved": bool(task.solved),
        "steps": int(task.step_count),
        "overrides_vs_r11": int(overrides),
        "neural_fused_steps": int(fused_steps),
    }


def evaluate_r21(
    parent: Any,
    model: NativeR21GoalBeliefEnsemble,
    *,
    make_task: Any,
    families: Sequence[str],
    split: str,
    indices: tuple[int, int],
    beta: float,
    temperature: float,
    max_support: int,
) -> dict[str, Any]:
    if split not in {"dev", "fresh"}:
        raise ValueError("R21 evaluation split must be dev/fresh")
    rows = []
    families_result: dict[str, dict[str, int]] = {}
    solved = steps = overrides = fused_steps = 0
    for family in families:
        fs = fst = fov = ffu = episodes = 0
        for index in range(int(indices[0]), int(indices[1]) + 1):
            result = rollout_r21(
                parent,
                model,
                make_task(str(family), str(split), int(index)),
                beta=float(beta),
                temperature=float(temperature),
                max_support=int(max_support),
            )
            fs += int(result["solved"])
            fst += int(result["steps"])
            fov += int(result["overrides_vs_r11"])
            ffu += int(result["neural_fused_steps"])
            solved += int(result["solved"])
            steps += int(result["steps"])
            overrides += int(result["overrides_vs_r11"])
            fused_steps += int(result["neural_fused_steps"])
            episodes += 1
            rows.append({"family": str(family), "split": str(split), "index": int(index), **result})
        families_result[str(family)] = {
            "episodes": episodes,
            "solved": fs,
            "steps": fst,
            "overrides_vs_r11": fov,
            "neural_fused_steps": ffu,
        }
    return {
        "split": str(split),
        "indices": list(indices),
        "episodes": len(rows),
        "solved": solved,
        "steps": steps,
        "overrides_vs_r11": overrides,
        "neural_fused_steps": fused_steps,
        "families": families_result,
        "rows": rows,
    }


def save_checkpoint(
    model: NativeR21GoalBeliefEnsemble,
    path: str | Path,
    *,
    parent_checkpoint_sha256: str,
    parent_state_dict_sha256: str,
    r11_authority_blob_sha: str,
    predev_lock_sha256: str,
    training_summary: Mapping[str, Any],
    calibration: Mapping[str, Any],
) -> dict[str, Any]:
    state = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}
    payload = {
        "format": CHECKPOINT_FORMAT,
        "status": "TRAINED_DEV_ONLY_FRESH_UNOPENED",
        "architecture": model.architecture(),
        "successor_parameters": model.parameter_count(),
        "physical_parameters": 877542 + model.parameter_count(),
        "parent_checkpoint_sha256": str(parent_checkpoint_sha256),
        "parent_state_dict_sha256": str(parent_state_dict_sha256),
        "r11_authority_blob_sha": str(r11_authority_blob_sha),
        "predev_lock_sha256": str(predev_lock_sha256),
        "training_summary": dict(training_summary),
        "calibration": dict(calibration),
        "state_dict_sha256": state_dict_sha256(state),
        "state_dict": state,
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, destination)
    return {
        key: value for key, value in payload.items()
        if key != "state_dict"
    } | {"checkpoint_sha256": sha256_file(destination)}


def load_checkpoint(path: str | Path) -> tuple[NativeR21GoalBeliefEnsemble, dict[str, Any]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != CHECKPOINT_FORMAT:
        raise ValueError("unsupported R21 checkpoint")
    architecture = payload["architecture"]
    model = NativeR21GoalBeliefEnsemble(
        ensemble_size=int(architecture["r21_ensemble_size"]),
        hidden_dim=int(architecture["r21_hidden_dim"]),
    )
    model.load_state_dict(payload["state_dict"], strict=True)
    if model.state_sha256() != payload["state_dict_sha256"]:
        raise ValueError("R21 state digest mismatch")
    model.eval()
    metadata = {k: v for k, v in payload.items() if k != "state_dict"}
    metadata["checkpoint_sha256"] = sha256_file(path)
    return model, metadata
