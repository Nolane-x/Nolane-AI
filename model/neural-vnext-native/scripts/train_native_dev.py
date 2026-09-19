from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
MODEL_ROOT = HERE.parents[2]
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from cogcoder.r18_benchmark import R18_FAMILIES, make_r18_task, oracle_plan  # noqa: E402
from native_core import NativeRecurrentPolicy, parameter_count  # noqa: E402
from native_training import (  # noqa: E402
    evaluate_policy,
    load_lock,
    save_checkpoint,
    sha256_json_file,
    train_native_policy,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train Neural vNext Native only on FIGG-18 train, then evaluate dev. Fresh is never instantiated."
    )
    parser.add_argument("--lock", type=Path, default=ROOT / "PREDEV_LOCK.json")
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dev-result", required=True, type=Path)
    args = parser.parse_args()

    lock = load_lock(args.lock)
    benchmark = lock["benchmark"]
    training = lock["training"]
    architecture = lock["architecture"]

    if benchmark["training_split"] != "train" or benchmark["development_split"] != "dev":
        raise ValueError("native trainer requires locked train/dev split names")
    if training.get("fresh_split_forbidden") is not True:
        raise ValueError("native training lock must forbid fresh")

    model = NativeRecurrentPolicy(
        global_dim=int(architecture["public_global_features"]),
        action_dim=int(architecture["public_action_features"]),
        hidden_dim=int(architecture["hidden_dim"]),
        attention_heads=int(architecture["attention_heads"]),
    )
    train_indices = tuple(int(value) for value in benchmark["training_indices"])
    dev_indices = tuple(int(value) for value in benchmark["development_indices"])
    dagger_mix = [float(value) for value in training["dagger_teacher_mix"]]

    summary = train_native_policy(
        model,
        make_task=make_r18_task,
        oracle_plan=oracle_plan,
        families=tuple(benchmark["families"]),
        train_indices=(train_indices[0], train_indices[1]),
        seed=int(training["seed"]),
        expert_epochs=int(training["expert_epochs"]),
        dagger_teacher_mix=dagger_mix,
        learning_rate=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
        max_grad_norm=float(training["max_grad_norm"]),
    )
    manifest = save_checkpoint(
        model,
        args.checkpoint,
        predev_lock_sha256=sha256_json_file(args.lock),
        training_summary=summary,
    )
    dev = evaluate_policy(
        model,
        make_task=make_r18_task,
        families=tuple(benchmark["families"]),
        split="dev",
        indices=(dev_indices[0], dev_indices[1]),
    )
    manifest["dev_evaluation"] = {
        key: value for key, value in dev.items() if key != "rows"
    }
    manifest["fresh_opened"] = False

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.dev_result.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.dev_result.write_text(json.dumps(dev, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "DEV_COMPLETE_FRESH_UNOPENED",
                "parameters": parameter_count(model),
                "checkpoint_sha256": manifest["checkpoint_sha256"],
                "state_dict_sha256": manifest["state_dict_sha256"],
                "dev_solved": dev["solved"],
                "dev_episodes": dev["episodes"],
                "dev_solve_rate": dev["solve_rate"],
                "families": dev["families"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
