from __future__ import annotations

import copy
import hashlib
import json
import random
import time
from pathlib import Path

import torch

from cogcoder.r17_training import load_r17_checkpoint, sha256_file
from cogcoder.r18_benchmark import R18_FAMILIES, make_r18_task
from cogcoder.r19_frontier import FrontierRolloutHead, frontier_parameter_count
from cogcoder.r19_rollout import collect_rollout_rows
from cogcoder.r19_training import (
    configure_r19_training,
    evaluate_r19_rows,
    load_r19_delta,
    r19_internal_gate,
    save_r19_delta,
    train_r19_epoch,
)

SEED = 190919
FIT_START = 32
FIT_COUNT = 16
VAL_START = 48
VAL_COUNT = 8
MAX_STATES = 2
EPOCHS = 15
LR = 8e-4
WEIGHT_DECAY = 1e-4
BATCH_SIZE = 128
PARENT_EFFECTIVE_PARAMETERS = 76_619_419
MAX_EFFECTIVE_PARAMETERS = 79_000_000


def _tensor_digest(model: torch.nn.Module) -> str:
    h = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        h.update(name.encode())
        h.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def _collect(parent, start: int, count: int):
    rows = []
    for family in R18_FAMILIES:
        for index in range(start, start + count):
            rows.extend(
                collect_rollout_rows(
                    parent,
                    make_r18_task(family, "train", index),
                    max_states=MAX_STATES,
                )
            )
    return tuple(rows)


def _snapshot(head: FrontierRolloutHead):
    return {name: value.detach().cpu().clone() for name, value in head.state_dict().items()}


def main() -> None:
    torch.manual_seed(SEED)
    random.seed(SEED)
    torch.set_num_threads(4)
    root = Path(__file__).resolve().parents[1]
    r12 = root / "checkpoints/Nolane-Rebuild-R1.2-ACE.pt"
    r16 = root / "checkpoints/Nolane-R1.6-NS2-EffectProgressCritic.pt"
    parent_path = root / "checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt"
    output = root / "checkpoints/Nolane-R1.9-FGR-FrontierRollout.pt"
    result_path = root / "results/r1_9_frontier_rollout_internal.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)

    parent, parent_meta = load_r17_checkpoint(
        parent_path,
        expected_r1_2_checkpoint=r12,
        expected_r1_6_parent_checkpoint=r16,
    )
    if int(parent_meta["candidate_effective_parameters"]) != PARENT_EFFECTIVE_PARAMETERS:
        raise RuntimeError("unexpected R1.8 effective parameter count")
    parent_digest_before = _tensor_digest(parent)
    head = FrontierRolloutHead()
    configure_r19_training(parent, head)
    delta_parameters = frontier_parameter_count(head)
    candidate_effective = PARENT_EFFECTIVE_PARAMETERS + delta_parameters
    if delta_parameters >= 2_000_000 or candidate_effective >= MAX_EFFECTIVE_PARAMETERS:
        raise RuntimeError("R1.9 parameter budget violated")

    t0 = time.time()
    fit_rows = _collect(parent, FIT_START, FIT_COUNT)
    val_rows = _collect(parent, VAL_START, VAL_COUNT)
    initial = evaluate_r19_rows(head, val_rows, batch_size=BATCH_SIZE)
    print(json.dumps({
        "event": "precompute",
        "fit_rows": len(fit_rows),
        "val_rows": len(val_rows),
        "seconds": time.time() - t0,
        "delta_parameters": delta_parameters,
        "candidate_effective_parameters": candidate_effective,
        "initial": initial,
    }, sort_keys=True), flush=True)

    optimizer = torch.optim.AdamW(head.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    best_metrics = None
    best_epoch = 0
    best_state = None
    history = []

    for epoch in range(1, EPOCHS + 1):
        loss = train_r19_epoch(head, fit_rows, optimizer, batch_size=BATCH_SIZE)
        metrics = evaluate_r19_rows(head, val_rows, batch_size=BATCH_SIZE)
        row = {"epoch": epoch, "train_loss": loss, **metrics}
        history.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
        if r19_internal_gate(metrics) and (
            best_metrics is None or float(metrics["candidate_mse"]) < float(best_metrics["candidate_mse"])
        ):
            best_epoch = epoch
            best_metrics = copy.deepcopy(metrics)
            best_state = _snapshot(head)

    if best_state is None or best_metrics is None:
        report = {
            "version": "r1.9-frontier-rollout-internal-v1",
            "accepted": False,
            "initial_validation": initial,
            "history": history,
        }
        result_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        raise SystemExit(2)

    head.load_state_dict(best_state, strict=True)
    parent_digest_after = _tensor_digest(parent)
    if parent_digest_after != parent_digest_before:
        raise RuntimeError("immutable R1.8 parent changed during R1.9 training")

    protocol = {
        "benchmark": "FIGG-19 Rollout v1",
        "source_families": list(R18_FAMILIES),
        "split": "train-only",
        "fit_indices": [FIT_START, FIT_START + FIT_COUNT],
        "internal_validation_indices": [VAL_START, VAL_START + VAL_COUNT],
        "max_states": MAX_STATES,
        "program_horizon": 2,
        "epochs": EPOCHS,
        "lr": LR,
        "weight_decay": WEIGHT_DECAY,
        "batch_size": BATCH_SIZE,
        "seed": SEED,
        "dev_opened": False,
        "fresh_opened": False,
    }
    report = {
        "version": "r1.9-frontier-rollout-internal-v1",
        "accepted": True,
        "parent_sha256": sha256_file(parent_path),
        "parent_tensor_digest_before": parent_digest_before,
        "parent_tensor_digest_after": parent_digest_after,
        "parent_effective_parameters": PARENT_EFFECTIVE_PARAMETERS,
        "delta_parameters": delta_parameters,
        "candidate_effective_parameters": candidate_effective,
        "protocol": protocol,
        "fit_rows": len(fit_rows),
        "validation_rows": len(val_rows),
        "initial_validation": initial,
        "best_epoch": best_epoch,
        "best_validation": best_metrics,
        "history": history,
    }
    meta = save_r19_delta(
        output,
        head,
        parent_checkpoint=parent_path,
        parent_effective_parameters=PARENT_EFFECTIVE_PARAMETERS,
        report=report,
    )
    report["checkpoint"] = meta
    result_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    reloaded, _ = load_r19_delta(output, expected_parent_checkpoint=parent_path)
    reproduced = evaluate_r19_rows(reloaded, val_rows, batch_size=BATCH_SIZE)
    if abs(float(reproduced["candidate_mse"]) - float(best_metrics["candidate_mse"])) > 1e-10:
        raise RuntimeError("reloaded R1.9 validation metric did not reproduce")
    print(json.dumps({
        "accepted": True,
        "best_epoch": best_epoch,
        "best_validation": best_metrics,
        "reproduced": reproduced,
        "checkpoint": meta,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
