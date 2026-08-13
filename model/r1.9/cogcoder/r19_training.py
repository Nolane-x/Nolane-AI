from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Sequence

import torch
import torch.nn.functional as F

from .neural_system2 import NeuralSystem2Workspace
from .r19_frontier import FrontierRolloutHead, frontier_parameter_count
from .r19_rollout import RolloutRow


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def configure_r19_training(parent: NeuralSystem2Workspace, head: FrontierRolloutHead) -> list[str]:
    for parameter in parent.parameters():
        parameter.requires_grad_(False)
    names: list[str] = []
    for name, parameter in head.named_parameters():
        parameter.requires_grad_(True)
        names.append(name)
    return names


def _batches(rows: Sequence[RolloutRow], batch_size: int) -> list[list[RolloutRow]]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    return [list(rows[start : start + batch_size]) for start in range(0, len(rows), batch_size)]


def _stack(batch: Sequence[RolloutRow]):
    state = torch.stack([row.state_sketch for row in batch])
    context = torch.stack([row.context_fingerprint for row in batch])
    actions = torch.stack([row.program_action_embeddings for row in batch])
    parent = torch.stack([row.parent_effects for row in batch])
    target = torch.stack([row.target_effect for row in batch])
    return state, context, actions, parent, target


def evaluate_r19_rows(
    head: FrontierRolloutHead,
    rows: Sequence[RolloutRow],
    *,
    batch_size: int = 128,
) -> dict[str, object]:
    head.eval()
    totals = {"candidate_sq": 0.0, "baseline_sq": 0.0, "elements": 0}
    family_totals = defaultdict(lambda: {"candidate_sq": 0.0, "baseline_sq": 0.0, "elements": 0})

    with torch.no_grad():
        for batch in _batches(rows, batch_size):
            state, context, actions, parent, target = _stack(batch)
            predicted = head(state, context, actions, parent)["predicted_effect"]
            baseline = parent.sum(dim=1)
            for index, row in enumerate(batch):
                candidate_diff = predicted[index] - target[index]
                baseline_diff = baseline[index] - target[index]
                candidate_sq = float((candidate_diff * candidate_diff).sum().item())
                baseline_sq = float((baseline_diff * baseline_diff).sum().item())
                elements = int(candidate_diff.numel())
                totals["candidate_sq"] += candidate_sq
                totals["baseline_sq"] += baseline_sq
                totals["elements"] += elements
                family_totals[row.family]["candidate_sq"] += candidate_sq
                family_totals[row.family]["baseline_sq"] += baseline_sq
                family_totals[row.family]["elements"] += elements

    def summarize(item: dict[str, float | int]) -> dict[str, float | int]:
        denom = max(1, int(item["elements"]))
        candidate = float(item["candidate_sq"]) / denom
        baseline = float(item["baseline_sq"]) / denom
        return {
            "candidate_mse": candidate,
            "baseline_mse": baseline,
            "relative_improvement": 1.0 - candidate / max(baseline, 1e-12),
            "elements": int(item["elements"]),
        }

    return {
        **summarize(totals),
        "rows": len(rows),
        "families": {name: summarize(item) for name, item in sorted(family_totals.items())},
    }


def train_r19_epoch(
    head: FrontierRolloutHead,
    rows: Sequence[RolloutRow],
    optimizer: torch.optim.Optimizer,
    *,
    batch_size: int = 128,
) -> float:
    head.train()
    batches = _batches(rows, batch_size)
    if not batches:
        return 0.0
    order = torch.randperm(len(batches)).tolist()
    total = 0.0
    count = 0
    for batch_index in order:
        batch = batches[batch_index]
        state, context, actions, parent, target = _stack(batch)
        optimizer.zero_grad(set_to_none=True)
        out = head(state, context, actions, parent)
        loss = F.mse_loss(out["predicted_effect"], target)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(head.parameters(), max_norm=1.0)
        optimizer.step()
        total += float(loss.detach().item()) * len(batch)
        count += len(batch)
    return total / max(1, count)


def r19_internal_gate(metrics: dict[str, object], *, min_relative_improvement: float = 0.05) -> bool:
    if float(metrics.get("relative_improvement", -1.0)) < float(min_relative_improvement):
        return False
    families = metrics.get("families")
    if not isinstance(families, dict) or not families:
        return False
    for row in families.values():
        if not isinstance(row, dict):
            return False
        if float(row.get("candidate_mse", float("inf"))) >= float(row.get("baseline_mse", 0.0)):
            return False
    return True


def _architecture(head: FrontierRolloutHead) -> dict[str, int]:
    relation_dim = int(head.relation_encoder[0].out_features)
    return {
        "state_dim": head.state_dim,
        "context_dim": head.context_dim,
        "action_dim": head.action_dim,
        "effect_dim": head.effect_dim,
        "hidden_dim": head.hidden_dim,
        "relation_dim": relation_dim,
        "max_horizon": head.max_horizon,
        "refine_steps": head.refine_steps,
    }


def save_r19_delta(
    path: str | Path,
    head: FrontierRolloutHead,
    *,
    parent_checkpoint: str | Path,
    parent_effective_parameters: int,
    report: dict[str, object],
) -> dict[str, object]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    delta_parameters = frontier_parameter_count(head)
    parent_sha = sha256_file(parent_checkpoint)
    payload = {
        "format": "nolane-r1.9-frontier-rollout-delta-v1",
        "architecture": _architecture(head),
        "parent_sha256": parent_sha,
        "parent_effective_parameters": int(parent_effective_parameters),
        "delta_parameters": int(delta_parameters),
        "candidate_effective_parameters": int(parent_effective_parameters) + int(delta_parameters),
        "head_state": {key: value.detach().cpu() for key, value in head.state_dict().items()},
        "report": report,
    }
    torch.save(payload, path)
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "parent_sha256": parent_sha,
        "delta_parameters": int(delta_parameters),
        "candidate_effective_parameters": payload["candidate_effective_parameters"],
    }


def load_r19_delta(
    path: str | Path,
    *,
    expected_parent_checkpoint: str | Path,
) -> tuple[FrontierRolloutHead, dict[str, object]]:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != "nolane-r1.9-frontier-rollout-delta-v1":
        raise ValueError("unsupported R1.9 delta format")
    expected = sha256_file(expected_parent_checkpoint)
    if payload.get("parent_sha256") != expected:
        raise ValueError("parent checkpoint SHA-256 mismatch")
    architecture = dict(payload["architecture"])
    head = FrontierRolloutHead(**architecture)
    head.load_state_dict(payload["head_state"], strict=True)
    return head, payload
