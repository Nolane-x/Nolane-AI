from __future__ import annotations

from dataclasses import dataclass
import copy
import random
from typing import Any, Sequence

import torch
from torch import Tensor, nn
import torch.nn.functional as F

from native_core import (
    ACTION_FEATURE_DIM,
    GLOBAL_FEATURE_DIM,
    PublicActionMemory,
    encode_public_state,
)

STATE_DIMS = 3
STATE_CARDINALITY = 5
ACTION_COUNT = 4


class PublicDynamicsNet(nn.Module):
    """Set-aware public transition model for the hidden-goal FIGG-18 family."""

    def __init__(self, hidden_dim: int = 64, heads: int = 4) -> None:
        super().__init__()
        if hidden_dim % heads:
            raise ValueError("hidden_dim must be divisible by heads")
        self.hidden_dim = int(hidden_dim)
        self.heads = int(heads)
        self.global_encoder = nn.Sequential(
            nn.Linear(GLOBAL_FEATURE_DIM, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.action_encoder = nn.Sequential(
            nn.Linear(ACTION_FEATURE_DIM, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.action_attention = nn.MultiheadAttention(
            hidden_dim,
            heads,
            batch_first=True,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, STATE_DIMS * STATE_CARDINALITY),
        )

    def forward(self, global_features: Tensor, action_features: Tensor) -> Tensor:
        if global_features.ndim != 2 or global_features.shape[-1] != GLOBAL_FEATURE_DIM:
            raise ValueError("global_features must be [batch, global_dim]")
        if action_features.ndim != 3 or action_features.shape[-1] != ACTION_FEATURE_DIM:
            raise ValueError("action_features must be [batch, actions, action_dim]")
        g = self.global_encoder(global_features)
        a = self.action_encoder(action_features)
        contextual, _ = self.action_attention(a, a, a, need_weights=False)
        g_expand = g[:, None, :].expand(-1, contextual.shape[1], -1)
        logits = self.head(torch.cat((contextual, g_expand), dim=-1))
        return logits.view(
            global_features.shape[0],
            action_features.shape[1],
            STATE_DIMS,
            STATE_CARDINALITY,
        )

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())


@dataclass(frozen=True)
class TransitionDataset:
    global_features: Tensor
    action_features: Tensor
    labels: Tensor
    action_mask: Tensor

    def __len__(self) -> int:
        return int(self.global_features.shape[0])


def _counterfactual_labels(task: Any, observation: dict[str, Any]) -> tuple[Tensor, Tensor]:
    descriptions = observation["actions"]
    if len(descriptions) != ACTION_COUNT:
        raise ValueError("R18 world model is trained only on 4-action hidden-goal tasks")
    before = [int(v) for v in observation["state"]]
    labels = torch.zeros((ACTION_COUNT, STATE_DIMS), dtype=torch.long)
    mask = torch.zeros((ACTION_COUNT,), dtype=torch.bool)
    for action, description in enumerate(descriptions):
        if "submit" in str(description).lower():
            continue
        probe = copy.deepcopy(task)
        result = probe.step(int(action))
        after = [int(v) for v in result.observation["state"]]
        labels[action] = torch.tensor(
            [int((a - b) % STATE_CARDINALITY) for b, a in zip(before, after)],
            dtype=torch.long,
        )
        mask[action] = True
    return labels, mask


def collect_public_transition_dataset(
    *,
    make_task: Any,
    indices: tuple[int, int],
    probe_steps: int,
) -> TransitionDataset:
    globals_: list[Tensor] = []
    actions_: list[Tensor] = []
    labels_: list[Tensor] = []
    masks_: list[Tensor] = []

    for index in range(int(indices[0]), int(indices[1]) + 1):
        task = make_task("implicit_goal_regimes", "train", int(index))
        memory = PublicActionMemory(len(task.action_descriptions))
        previous_feedback = [0.0, 0.0, 0.0]
        step = 0
        while not task.done and step < int(probe_steps):
            observation = task.observe()
            global_features, action_features, _valid = encode_public_state(
                observation,
                memory,
                previous_feedback=previous_feedback,
            )
            labels, mask = _counterfactual_labels(task, observation)
            globals_.append(global_features)
            actions_.append(action_features)
            labels_.append(labels)
            masks_.append(mask)

            non_submit = [
                i for i, description in enumerate(observation["actions"])
                if "submit" not in str(description).lower()
            ]
            behavior_action = non_submit[(int(index) + step) % len(non_submit)]
            before = observation
            result = task.step(int(behavior_action))
            memory.update(
                action=int(behavior_action),
                before=before,
                after=result.observation,
                progress_delta=result.progress_delta,
                information_gain=result.information_gain,
                failed=result.failed,
            )
            previous_feedback = [
                float(result.progress_delta),
                float(result.information_gain),
                float(result.failed),
            ]
            step += 1

    if not globals_:
        raise ValueError("empty R16 public transition dataset")
    return TransitionDataset(
        global_features=torch.stack(globals_),
        action_features=torch.stack(actions_),
        labels=torch.stack(labels_),
        action_mask=torch.stack(masks_),
    )


def train_ensemble(
    dataset: TransitionDataset,
    *,
    seeds: Sequence[int],
    hidden_dim: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
) -> tuple[list[PublicDynamicsNet], list[dict[str, float]]]:
    models: list[PublicDynamicsNet] = []
    summaries: list[dict[str, float]] = []
    n = len(dataset)
    for seed in seeds:
        torch.manual_seed(int(seed))
        random.seed(int(seed))
        model = PublicDynamicsNet(hidden_dim=int(hidden_dim))
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=float(learning_rate),
            weight_decay=float(weight_decay),
            foreach=False,
            fused=False,
        )
        generator = torch.Generator().manual_seed(int(seed) + 991)
        last_loss = 0.0
        for _epoch in range(int(epochs)):
            order = torch.randperm(n, generator=generator)
            losses: list[float] = []
            for start in range(0, n, int(batch_size)):
                idx = order[start : start + int(batch_size)]
                logits = model(
                    dataset.global_features[idx],
                    dataset.action_features[idx],
                )
                mask = dataset.action_mask[idx]
                selected_logits = logits[mask]
                selected_labels = dataset.labels[idx][mask]
                loss = sum(
                    F.cross_entropy(selected_logits[:, dim, :], selected_labels[:, dim])
                    for dim in range(STATE_DIMS)
                ) / float(STATE_DIMS)
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, foreach=False)
                optimizer.step()
                losses.append(float(loss.detach()))
            last_loss = sum(losses) / max(1, len(losses))
        model.eval()
        models.append(model)
        summaries.append({
            "seed": float(seed),
            "final_mean_loss": float(last_loss),
            "parameters": float(model.parameter_count()),
        })
    return models, summaries


@torch.no_grad()
def ensemble_predictions(
    models: Sequence[PublicDynamicsNet],
    global_features: Tensor,
    action_features: Tensor,
) -> tuple[Tensor, Tensor, Tensor]:
    if not models:
        raise ValueError("R18 requires at least one world model")
    logits = [
        model(global_features, action_features)
        for model in models
    ]
    probs = [torch.softmax(row, dim=-1) for row in logits]
    preds = torch.stack([row.argmax(dim=-1) for row in probs], dim=0)
    agreement = (preds == preds[0:1]).all(dim=0).all(dim=-1)
    agreed = preds[0]
    confidences: list[Tensor] = []
    for member_probs in probs:
        gathered = member_probs.gather(-1, agreed.unsqueeze(-1)).squeeze(-1)
        confidences.append(gathered.min(dim=-1).values)
    confidence = torch.stack(confidences, dim=0).min(dim=0).values
    return agreed, agreement, confidence


@torch.no_grad()
def calibrate_threshold(
    models: Sequence[PublicDynamicsNet],
    dataset: TransitionDataset,
    *,
    minimum_precision: float,
    minimum_coverage: int,
    thresholds: Sequence[float],
) -> dict[str, Any]:
    prediction, agreement, confidence = ensemble_predictions(
        models,
        dataset.global_features,
        dataset.action_features,
    )
    exact = (prediction == dataset.labels).all(dim=-1)
    base = dataset.action_mask & agreement
    rows: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    for threshold in sorted((float(v) for v in thresholds), reverse=True):
        eligible = base & (confidence >= float(threshold))
        count = int(eligible.sum().item())
        correct = int((exact & eligible).sum().item())
        precision = float(correct / count) if count else 0.0
        row = {
            "threshold": float(threshold),
            "eligible": count,
            "correct": correct,
            "precision": precision,
        }
        rows.append(row)
        if (
            count >= int(minimum_coverage)
            and precision >= float(minimum_precision)
        ):
            selected = row
    return {
        "minimum_precision": float(minimum_precision),
        "minimum_coverage": int(minimum_coverage),
        "candidates": rows,
        "selected": selected,
    }


def ensemble_state_dict(models: Sequence[PublicDynamicsNet]) -> list[dict[str, Tensor]]:
    return [
        {name: tensor.detach().cpu() for name, tensor in model.state_dict().items()}
        for model in models
    ]


def load_ensemble(
    states: Sequence[dict[str, Tensor]],
    *,
    hidden_dim: int,
) -> list[PublicDynamicsNet]:
    models: list[PublicDynamicsNet] = []
    for state in states:
        model = PublicDynamicsNet(hidden_dim=int(hidden_dim))
        model.load_state_dict(state, strict=True)
        model.eval()
        models.append(model)
    return models
