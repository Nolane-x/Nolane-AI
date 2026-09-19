from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable, Sequence

import torch
from torch import Tensor, nn
import torch.nn.functional as F

from .core import PublicR18RecursiveCore, public_r18_parameter_count
from .data import PublicTeacherEpisode, tensorize_public_step

CHECKPOINT_FORMAT = "nolane-public-r18-recursive-core-v1"


def train_public_r18_epoch(
    model: PublicR18RecursiveCore,
    episodes: Sequence[PublicTeacherEpisode],
    optimizer: torch.optim.Optimizer,
    *,
    generator: torch.Generator | None = None,
    max_grad_norm: float = 1.0,
) -> dict[str, float]:
    if not episodes:
        raise ValueError("training requires at least one teacher episode")
    if max_grad_norm <= 0:
        raise ValueError("max_grad_norm must be positive")
    order = torch.randperm(len(episodes), generator=generator).tolist()
    model.train()
    total_loss = 0.0
    total_rows = 0
    total_correct = 0
    total_episodes = 0

    for episode_index in order:
        episode = episodes[episode_index]
        if not episode.steps:
            continue
        memory = model.initial_memory(1)
        losses: list[Tensor] = []
        optimizer.zero_grad(set_to_none=True)
        for row in episode.steps:
            batch = tensorize_public_step(
                row,
                observation_bytes=model.observation_bytes,
                action_bytes=model.action_bytes,
                max_actions=model.max_actions,
                action_memory_dim=model.action_memory_dim,
                public_scalar_dim=model.public_scalar_dim,
            )
            output = model(
                observation_tokens=batch["observation_tokens"],
                action_tokens=batch["action_tokens"],
                action_mask=batch["action_mask"],
                action_memory=batch["action_memory"],
                public_scalars=batch["public_scalars"],
                memory=memory,
                previous_action=batch["previous_action"],
                previous_feedback=batch["previous_feedback"],
            )
            memory = output["next_memory"]
            trajectory = output["action_logits_trajectory"]
            target = batch["target_action"]
            depth = trajectory.shape[1]
            weights = torch.linspace(
                0.7, 1.3, depth, dtype=trajectory.dtype, device=trajectory.device
            )
            ce = torch.stack(
                [
                    F.cross_entropy(trajectory[:, step], target)
                    for step in range(depth)
                ]
            )
            loss = (ce * weights).mean()
            losses.append(loss)
            total_correct += int(output["action_logits"].argmax(-1).item() == target.item())
            total_rows += 1

        episode_loss = torch.stack(losses).mean()
        episode_loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=float(max_grad_norm))
        optimizer.step()
        total_loss += float(episode_loss.detach()) * len(losses)
        total_episodes += 1

    if total_rows < 1:
        raise ValueError("training corpus contained no usable rows")
    return {
        "loss": total_loss / total_rows,
        "teacher_action_accuracy": total_correct / total_rows,
        "rows": float(total_rows),
        "episodes": float(total_episodes),
    }


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_public_r18_checkpoint(
    model: PublicR18RecursiveCore,
    path: str | Path,
    *,
    training_report: dict[str, object],
    predev_lock_sha256: str,
) -> dict[str, object]:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": CHECKPOINT_FORMAT,
        "status": "FROZEN_DEV_CANDIDATE",
        "architecture": model.architecture(),
        "physical_parameters": public_r18_parameter_count(model),
        "predev_lock_sha256": str(predev_lock_sha256),
        "training_report": dict(training_report),
        "state_dict": {
            name: value.detach().cpu().clone()
            for name, value in model.state_dict().items()
        },
    }
    torch.save(payload, destination)
    return {
        "path": str(destination),
        "sha256": _sha256_file(destination),
        "bytes": destination.stat().st_size,
        "format": CHECKPOINT_FORMAT,
        "status": payload["status"],
        "physical_parameters": payload["physical_parameters"],
        "architecture": payload["architecture"],
        "predev_lock_sha256": payload["predev_lock_sha256"],
        "training_report": payload["training_report"],
    }


def load_public_r18_checkpoint(
    path: str | Path,
) -> tuple[PublicR18RecursiveCore, dict[str, object]]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or payload.get("format") != CHECKPOINT_FORMAT:
        raise ValueError("unsupported public R18 Neural Core checkpoint")
    architecture = payload.get("architecture")
    state = payload.get("state_dict")
    if not isinstance(architecture, dict) or not isinstance(state, dict):
        raise ValueError("checkpoint is missing architecture/state_dict")
    model = PublicR18RecursiveCore(**architecture)
    model.load_state_dict(state, strict=True)
    model.eval()
    if public_r18_parameter_count(model) != payload.get("physical_parameters"):
        raise ValueError("physical parameter audit mismatch")
    metadata = {key: value for key, value in payload.items() if key != "state_dict"}
    metadata["sha256"] = _sha256_file(Path(path))
    return model, metadata
