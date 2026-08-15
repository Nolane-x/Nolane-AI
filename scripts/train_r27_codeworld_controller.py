from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterable

import torch
from torch import Tensor
from torch.nn import functional as F

from cogcoder.r27_codeworld_controller import (
    ACTION_KINDS,
    CodeWorldController,
    CodeWorldControllerConfig,
    controller_parameter_count,
)
from cogcoder.r27_codeworld_curriculum import (
    CurriculumRow,
    build_curriculum,
    split_by_language_task_pair,
)

PARENT_EFFECTIVE_PARAMETERS = 78_779_253
R27_FORMAT = "nolane-r2.7-codeworld-generalist-v1"


@dataclass
class TrainingResult:
    config: CodeWorldControllerConfig
    controller_state: dict[str, Tensor]
    controller_parameters: int
    train_accuracy: float
    heldout_accuracy: float
    epochs: int
    seed: int
    training_rows: int
    heldout_rows: int


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _batches(rows: list[CurriculumRow], batch_size: int, *, seed: int) -> Iterable[list[CurriculumRow]]:
    order = torch.randperm(len(rows), generator=torch.Generator().manual_seed(seed)).tolist()
    for start in range(0, len(order), batch_size):
        yield [rows[i] for i in order[start : start + batch_size]]


def _collate(rows: list[CurriculumRow], cfg: CodeWorldControllerConfig) -> tuple[Tensor, ...]:
    batch = len(rows)
    max_history = max(row.history_features.shape[0] for row in rows)
    history = torch.zeros(batch, max_history, cfg.history_feature_dim)
    for index, row in enumerate(rows):
        length = row.history_features.shape[0]
        history[index, :length] = row.history_features
    state = torch.stack([row.state_features for row in rows])
    action = torch.stack([row.action_features for row in rows])
    language = torch.tensor([row.language_id for row in rows], dtype=torch.long)
    task = torch.tensor([row.task_type_id for row in rows], dtype=torch.long)
    mask = torch.ones(batch, len(ACTION_KINDS), dtype=torch.bool)
    target = torch.tensor([ACTION_KINDS.index(row.target_action) for row in rows], dtype=torch.long)
    success = (target == ACTION_KINDS.index("finish")).float()
    return state, action, history, language, task, mask, target, success


def _accuracy(model: CodeWorldController, rows: list[CurriculumRow], batch_size: int = 128) -> float:
    if not rows:
        return 0.0
    cfg = model.config
    correct = 0
    model.eval()
    with torch.no_grad():
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            state, action, history, language, task, mask, target, _ = _collate(batch, cfg)
            out = model(
                state_features=state,
                action_features=action,
                history_features=history,
                language_ids=language,
                task_type_ids=task,
                action_mask=mask,
            )
            correct += int((out.action_logits.argmax(dim=-1) == target).sum().item())
    return correct / len(rows)


def train_controller(
    *,
    seed: int = 27,
    epochs: int = 12,
    episodes_per_pair: int = 24,
    batch_size: int = 64,
    learning_rate: float = 2e-3,
) -> TrainingResult:
    torch.manual_seed(seed)
    cfg = CodeWorldControllerConfig()
    rows = build_curriculum(seed=seed, episodes_per_pair=episodes_per_pair, config=cfg)
    train_rows, heldout_rows = split_by_language_task_pair(rows)
    model = CodeWorldController(cfg)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)

    for epoch in range(epochs):
        model.train()
        for batch in _batches(train_rows, batch_size, seed=seed + epoch):
            state, action, history, language, task, mask, target, success = _collate(batch, cfg)
            out = model(
                state_features=state,
                action_features=action,
                history_features=history,
                language_ids=language,
                task_type_ids=task,
                action_mask=mask,
            )
            action_loss = F.cross_entropy(out.action_logits, target)
            success_loss = F.binary_cross_entropy_with_logits(out.success_logit, success)
            stop_loss = F.binary_cross_entropy_with_logits(out.stop_logit, success)
            loss = action_loss + 0.1 * success_loss + 0.05 * stop_loss
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

    return TrainingResult(
        config=cfg,
        controller_state={k: v.detach().cpu() for k, v in model.state_dict().items()},
        controller_parameters=controller_parameter_count(model),
        train_accuracy=_accuracy(model, train_rows),
        heldout_accuracy=_accuracy(model, heldout_rows),
        epochs=epochs,
        seed=seed,
        training_rows=len(train_rows),
        heldout_rows=len(heldout_rows),
    )


def save_r27_bundle(parent_path: Path, output_path: Path, result: TrainingResult) -> dict[str, object]:
    parent_path = Path(parent_path)
    output_path = Path(output_path)
    parent_sha = _sha256(parent_path)
    delta = {
        "format": R27_FORMAT,
        "architecture": result.config.__dict__.copy(),
        "controller_parameters": result.controller_parameters,
        "state": result.controller_state,
        "training_report": {
            "seed": result.seed,
            "epochs": result.epochs,
            "training_rows": result.training_rows,
            "heldout_rows": result.heldout_rows,
            "train_accuracy": result.train_accuracy,
            "heldout_pair_accuracy": result.heldout_accuracy,
            "split_rule": "language_task_pair_disjoint_v1",
        },
    }
    try:
        parent_payload = torch.load(parent_path, map_location="cpu", weights_only=True)
    except Exception:
        parent_payload = {"external_parent_sha256": parent_sha}
    if not isinstance(parent_payload, dict):
        parent_payload = {"external_parent_sha256": parent_sha}
    payload = dict(parent_payload)
    payload.update(
        {
            "format": "nolane-r2.7-hybrid-standalone-bundle-v1",
            "version": "R2.7-CodeWorld-Generalist-Phase-A",
            "parent_r20i_sha256": parent_sha,
            "parent_effective_parameters": PARENT_EFFECTIVE_PARAMETERS,
            "r27_codeworld_delta": delta,
            "effective_parameters": PARENT_EFFECTIVE_PARAMETERS + result.controller_parameters,
            "claim_boundary_r27": (
                "Phase-A internal policy-transfer evidence only; no external coding benchmark claim."
            ),
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, output_path)
    return {
        "format": payload["format"],
        "version": payload["version"],
        "parent_sha256": parent_sha,
        "controller_parameters": result.controller_parameters,
        "candidate_effective_parameters": payload["effective_parameters"],
        "train_accuracy": result.train_accuracy,
        "heldout_pair_accuracy": result.heldout_accuracy,
        "bytes": output_path.stat().st_size,
        "sha256": _sha256(output_path),
    }


if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--episodes-per-pair", type=int, default=24)
    args = parser.parse_args()
    result = train_controller(epochs=args.epochs, episodes_per_pair=args.episodes_per_pair)
    meta = save_r27_bundle(args.parent, args.output, result)
    print(json.dumps(meta, indent=2, sort_keys=True))
