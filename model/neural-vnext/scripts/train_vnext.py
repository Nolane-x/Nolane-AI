from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import torch

HERE = Path(__file__).resolve()
VNEXT_ROOT = HERE.parents[1]
MODEL_ROOT = HERE.parents[2]
R23_ROOT = MODEL_ROOT / "neural-r2.3"
R21_ROOT = MODEL_ROOT / "neural-r2.1"
for root in (VNEXT_ROOT, R23_ROOT, R21_ROOT):
    text = str(root)
    if text not in sys.path:
        sys.path.insert(0, text)

from nvnext.pipeline import (  # noqa: E402
    load_predev_lock,
    load_verified_training_cache,
    run_training_epoch,
    save_frozen_candidate,
    sha256_file,
    sha256_json_file,
)
from nvnext.training import make_vnext_optimizer  # noqa: E402
from r23.standalone import load_r23_one_weight  # noqa: E402


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return parsed


def _unit_float(value: str) -> float:
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise argparse.ArgumentTypeError("value must lie in [0, 1]")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train and freeze the Neural vNext multi-depth candidate without touching fresh blocks."
    )
    parser.add_argument("--parent-checkpoint", required=True, type=Path)
    parser.add_argument("--training-cache", required=True, type=Path)
    parser.add_argument(
        "--predev-lock",
        type=Path,
        default=VNEXT_ROOT / "PREDEV_LOCK.json",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--seed", type=int, default=20260919)
    parser.add_argument("--batch-size", type=_positive_int, default=16)
    parser.add_argument("--warmup-epochs", type=int, default=1)
    parser.add_argument("--joint-epochs", type=int, default=1)
    parser.add_argument("--warmup-lr", type=float, default=2e-4)
    parser.add_argument("--joint-lr", type=float, default=5e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--min-depth", type=_positive_int, default=2)
    parser.add_argument("--max-depth", type=_positive_int, default=4)
    parser.add_argument("--halt-threshold", type=_unit_float, default=0.5)
    parser.add_argument("--stability-steps", type=_positive_int, default=2)
    args = parser.parse_args()

    if args.warmup_epochs < 0 or args.joint_epochs < 0:
        parser.error("epoch counts must be non-negative")
    if args.warmup_epochs + args.joint_epochs < 1:
        parser.error("at least one training stage must run")
    if args.min_depth < 2 or args.max_depth < args.min_depth:
        parser.error("multi-depth training requires 2 <= min-depth <= max-depth")
    if args.max_grad_norm <= 0:
        parser.error("max-grad-norm must be positive")

    lock = load_predev_lock(args.predev_lock)
    parent = lock.get("parent")
    architecture = lock.get("candidate_architecture")
    if not isinstance(parent, dict) or not isinstance(architecture, dict):
        raise ValueError("predevelopment lock is missing parent/candidate architecture")

    expected_parent_sha = parent.get("one_weight_sha256")
    actual_parent_sha = sha256_file(args.parent_checkpoint)
    if actual_parent_sha != expected_parent_sha:
        raise ValueError(
            f"parent checkpoint SHA-256 mismatch: {actual_parent_sha} != {expected_parent_sha}"
        )
    if args.max_depth > architecture.get("maximum_recurrent_depth", 0):
        raise ValueError("requested training depth exceeds preregistered maximum")
    if args.min_depth < architecture.get("minimum_adaptive_depth", 10**9):
        raise ValueError("requested minimum depth is below preregistered minimum")

    _parent, _rollout, _executive, _router, reasoner, _meta = load_r23_one_weight(
        args.parent_checkpoint
    )
    records = load_verified_training_cache(args.training_cache, predev_lock=lock)

    torch.manual_seed(args.seed)
    generator = torch.Generator().manual_seed(args.seed)
    stages: list[dict[str, object]] = []

    def run_stage(stage: str, epochs: int, learning_rate: float) -> None:
        if epochs == 0:
            return
        optimizer = make_vnext_optimizer(
            reasoner,
            stage=stage,
            learning_rate=learning_rate,
            weight_decay=args.weight_decay,
        )
        for epoch in range(epochs):
            metrics = run_training_epoch(
                reasoner,
                records,
                optimizer,
                batch_size=args.batch_size,
                generator=generator,
                min_steps=args.min_depth,
                max_steps=args.max_depth,
                max_grad_norm=args.max_grad_norm,
            )
            stages.append(
                {
                    "stage": stage,
                    "epoch": epoch + 1,
                    "learning_rate": learning_rate,
                    "metrics": metrics,
                }
            )

    run_stage("depth_warmup", args.warmup_epochs, args.warmup_lr)
    run_stage("joint_reasoner", args.joint_epochs, args.joint_lr)

    training_summary = {
        "seed": args.seed,
        "verified_records": len(records),
        "cache_sha256": sha256_file(args.training_cache),
        "source_kind_counts": dict(Counter(record.source_kind for record in records)),
        "family_counts": dict(Counter(record.family for record in records)),
        "fresh_indices_consumed": False,
        "stages": stages,
    }
    adaptive_depth = {
        "min_steps": args.min_depth,
        "max_steps": args.max_depth,
        "halt_threshold": args.halt_threshold,
        "stability_steps": args.stability_steps,
    }
    physical_parameters = parent.get("physical_parameters")
    if type(physical_parameters) is not int:
        raise ValueError("parent physical parameter authority must be an exact integer")

    manifest = save_frozen_candidate(
        reasoner,
        args.output,
        parent_one_weight_sha256=actual_parent_sha,
        predev_lock_sha256=sha256_json_file(args.predev_lock),
        physical_parameters=physical_parameters,
        adaptive_depth=adaptive_depth,
        training_summary=training_summary,
        physical_parameter_ceiling=int(architecture["physical_parameter_ceiling"]),
    )
    manifest_path = args.manifest or args.output.with_suffix(args.output.suffix + ".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "bundle": str(args.output),
                "manifest": str(manifest_path),
                "state_dict_sha256": manifest["state_dict_sha256"],
                "bundle_sha256": manifest["bundle_sha256"],
                "verified_records": len(records),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
