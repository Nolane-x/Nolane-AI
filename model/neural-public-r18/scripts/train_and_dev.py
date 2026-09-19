from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import torch

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
MODEL_ROOT = HERE.parents[2]
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from npr18 import (  # noqa: E402
    PublicR18RecursiveCore,
    collect_public_teacher_corpus,
    evaluate_public_r18,
    load_public_r18_checkpoint,
    public_r18_parameter_count,
    save_public_r18_checkpoint,
    train_public_r18_epoch,
)
from cogcoder.r18_benchmark import make_r18_task, oracle_plan  # noqa: E402


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _positive(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return parsed


def _inside(bounds: list[int], start: int, count: int) -> bool:
    return (
        len(bounds) == 2
        and type(bounds[0]) is int
        and type(bounds[1]) is int
        and bounds[0] <= start
        and start + count - 1 <= bounds[1]
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train, freeze and dev-evaluate the self-contained public R18 Neural Core."
    )
    parser.add_argument("--predev-lock", type=Path, default=ROOT / "PREDEV_LOCK.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--train-start", type=int, default=0)
    parser.add_argument("--train-count", type=_positive, default=24)
    parser.add_argument("--dev-start", type=int, default=0)
    parser.add_argument("--dev-count", type=_positive, default=8)
    parser.add_argument("--epochs", type=_positive, default=2)
    parser.add_argument("--hidden-dim", type=_positive, default=192)
    parser.add_argument("--reasoning-steps", type=_positive, default=3)
    parser.add_argument("--learning-rate", type=float, default=8e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=20260919)
    args = parser.parse_args()

    lock = json.loads(args.predev_lock.read_text(encoding="utf-8"))
    training_lock = lock.get("training")
    dev_lock = lock.get("development")
    architecture_lock = lock.get("architecture")
    if not isinstance(training_lock, dict) or not isinstance(dev_lock, dict):
        raise ValueError("predevelopment lock is missing training/development authority")
    if not isinstance(architecture_lock, dict):
        raise ValueError("predevelopment lock is missing architecture authority")
    if not _inside(training_lock["allowed_indices"], args.train_start, args.train_count):
        raise ValueError("requested train indices are outside the preregistered train window")
    if not _inside(dev_lock["allowed_indices"], args.dev_start, args.dev_count):
        raise ValueError("requested dev indices are outside the preregistered dev window")
    if args.reasoning_steps > 8:
        raise ValueError("reasoning_steps exceeds the candidate's encoded depth")
    if args.learning_rate <= 0 or args.weight_decay < 0:
        raise ValueError("optimizer hyperparameters are invalid")

    torch.manual_seed(args.seed)
    generator = torch.Generator().manual_seed(args.seed)
    corpus = collect_public_teacher_corpus(
        make_task=make_r18_task,
        oracle_plan=oracle_plan,
        start_index=args.train_start,
        count_per_family=args.train_count,
    )
    unsolved_teacher = [episode.task_id for episode in corpus if not episode.solved]
    if unsolved_teacher:
        raise RuntimeError(
            f"teacher corpus failed to preserve solvability: {unsolved_teacher[:4]}"
        )

    model = PublicR18RecursiveCore(
        hidden_dim=args.hidden_dim,
        reasoning_steps=args.reasoning_steps,
    )
    parameter_count = public_r18_parameter_count(model)
    ceiling = architecture_lock.get("physical_parameter_ceiling")
    if type(ceiling) is not int or parameter_count >= ceiling:
        raise RuntimeError(
            f"candidate violates physical parameter ceiling: {parameter_count} >= {ceiling}"
        )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(args.learning_rate),
        weight_decay=float(args.weight_decay),
    )

    epoch_rows = []
    for epoch in range(args.epochs):
        metrics = train_public_r18_epoch(
            model,
            corpus,
            optimizer,
            generator=generator,
        )
        row = {"epoch": epoch + 1, **metrics}
        epoch_rows.append(row)
        print(json.dumps({"training": row}, sort_keys=True))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = args.output_dir / "public-r18-recursive-core.pt"
    training_report = {
        "seed": args.seed,
        "train_split": "train",
        "train_indices": [args.train_start, args.train_start + args.train_count - 1],
        "teacher_episodes": len(corpus),
        "teacher_rows": sum(len(episode.steps) for episode in corpus),
        "teacher_all_solved": True,
        "oracle_usage": "train-target generation only",
        "model_input_boundary": "public-only",
        "epochs": epoch_rows,
    }
    manifest = save_public_r18_checkpoint(
        model,
        checkpoint,
        training_report=training_report,
        predev_lock_sha256=_sha256(args.predev_lock),
    )
    (args.output_dir / "checkpoint-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    frozen, frozen_meta = load_public_r18_checkpoint(checkpoint)
    if frozen_meta["sha256"] != manifest["sha256"]:
        raise RuntimeError("frozen checkpoint changed before dev evaluation")
    dev = evaluate_public_r18(
        frozen,
        make_task=make_r18_task,
        split="dev",
        start_index=args.dev_start,
        count_per_family=args.dev_count,
    )
    family_nonzero = all(
        int(row["solved"]) > 0
        for row in dev["families"].values()
    )
    dev["candidate"] = lock["candidate"]
    dev["checkpoint_sha256"] = manifest["sha256"]
    dev["physical_parameters"] = parameter_count
    dev["predev_lock_sha256"] = _sha256(args.predev_lock)
    dev["weights_modified_after_freeze"] = False
    dev["fresh_consumed"] = False
    dev["minimum_dev_requirement"] = {
        "nonzero_solved_in_every_family": family_nonzero,
        "passed": family_nonzero,
    }
    (args.output_dir / "dev-result.json").write_text(
        json.dumps(dev, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "status": "PASS_DEV_MINIMUM" if family_nonzero else "FAIL_DEV_MINIMUM",
        "checkpoint_sha256": manifest["sha256"],
        "physical_parameters": parameter_count,
        "dev_solved": dev["solved"],
        "dev_episodes": dev["episodes"],
        "families": {
            name: row["solved"]
            for name, row in dev["families"].items()
        },
        "fresh_consumed": False,
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if family_nonzero else 2


if __name__ == "__main__":
    raise SystemExit(main())
