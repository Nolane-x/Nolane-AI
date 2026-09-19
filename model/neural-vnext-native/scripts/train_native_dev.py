from __future__ import annotations

import argparse
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

from cogcoder.r18_benchmark import make_r18_task, oracle_plan  # noqa: E402
from native_core import NativeRecurrentPolicy, parameter_count  # noqa: E402
from native_training import (  # noqa: E402
    evaluate_policy,
    load_lock,
    save_checkpoint,
    sha256_json_file,
    train_native_policy,
)


def _candidate_rank(dev: dict[str, object]) -> tuple[int, int, int]:
    families = dev["families"]
    if not isinstance(families, dict) or not families:
        raise ValueError("development result is missing family metrics")
    solved = int(dev["solved"])
    worst_family = min(int(row["solved"]) for row in families.values())
    steps = int(dev["steps"])
    return solved, worst_family, -steps


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministically tune Neural vNext Native on FIGG-18 dev only. Fresh is never instantiated."
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
    if training.get("model_initialization_seed_bound_before_construction") is not True:
        raise ValueError("native candidate initialization must be seed-bound before model construction")

    train_indices = tuple(int(value) for value in benchmark["training_indices"])
    dev_indices = tuple(int(value) for value in benchmark["development_indices"])
    families = tuple(str(value) for value in benchmark["families"])
    seed = int(training["seed"])
    candidates = training.get("development_candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("development_candidates must be a non-empty list")

    best_model: NativeRecurrentPolicy | None = None
    best_name: str | None = None
    best_rank: tuple[int, int, int] | None = None
    best_dev: dict[str, object] | None = None
    best_training: dict[str, object] | None = None
    tournament: list[dict[str, object]] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("development candidate entries must be objects")
        name = str(candidate["name"])
        torch.manual_seed(seed)
        model = NativeRecurrentPolicy(
            global_dim=int(architecture["public_global_features"]),
            action_dim=int(architecture["public_action_features"]),
            hidden_dim=int(architecture["hidden_dim"]),
            attention_heads=int(architecture["attention_heads"]),
        )
        summary = train_native_policy(
            model,
            make_task=make_r18_task,
            oracle_plan=oracle_plan,
            families=families,
            train_indices=(train_indices[0], train_indices[1]),
            seed=seed,
            expert_epochs=int(candidate["expert_epochs"]),
            dagger_teacher_mix=[float(value) for value in candidate["dagger_teacher_mix"]],
            learning_rate=float(training["learning_rate"]),
            weight_decay=float(training["weight_decay"]),
            max_grad_norm=float(training["max_grad_norm"]),
            goal_loss_weight=float(training["goal_belief"]["loss_weight"]),
        )
        dev = evaluate_policy(
            model,
            make_task=make_r18_task,
            families=families,
            split="dev",
            indices=(dev_indices[0], dev_indices[1]),
        )
        rank = _candidate_rank(dev)
        tournament.append(
            {
                "name": name,
                "expert_epochs": int(candidate["expert_epochs"]),
                "dagger_teacher_mix": [float(value) for value in candidate["dagger_teacher_mix"]],
                "rank": list(rank),
                "development": {key: value for key, value in dev.items() if key != "rows"},
                "training": summary,
            }
        )
        print(
            json.dumps(
                {
                    "status": "DEV_CANDIDATE_COMPLETE_FRESH_UNOPENED",
                    "candidate": name,
                    "rank": list(rank),
                    "dev_solved": dev["solved"],
                    "dev_episodes": dev["episodes"],
                    "families": dev["families"],
                },
                sort_keys=True,
            )
        )
        better = best_rank is None or rank > best_rank
        tied_but_lexical = rank == best_rank and best_name is not None and name < best_name
        if better or tied_but_lexical:
            best_model = model
            best_name = name
            best_rank = rank
            best_dev = dev
            best_training = summary

    if best_model is None or best_name is None or best_dev is None or best_training is None:
        raise AssertionError("development tournament did not produce a candidate")

    training_summary = {
        "seed": seed,
        "selected_candidate": best_name,
        "selected_rank": list(best_rank),
        "selected_training": best_training,
        "selection_rule": list(training["selection_rule"]),
        "tournament": tournament,
        "fresh_opened": False,
    }
    manifest = save_checkpoint(
        best_model,
        args.checkpoint,
        predev_lock_sha256=sha256_json_file(args.lock),
        training_summary=training_summary,
    )
    manifest["selected_candidate"] = best_name
    manifest["selected_rank"] = list(best_rank)
    manifest["dev_evaluation"] = {
        key: value for key, value in best_dev.items() if key != "rows"
    }
    manifest["fresh_opened"] = False

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.dev_result.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.dev_result.write_text(json.dumps(best_dev, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "DEV_TOURNAMENT_COMPLETE_FRESH_UNOPENED",
                "selected_candidate": best_name,
                "selected_rank": list(best_rank),
                "parameters": parameter_count(best_model),
                "checkpoint_sha256": manifest["checkpoint_sha256"],
                "state_dict_sha256": manifest["state_dict_sha256"],
                "dev_solved": best_dev["solved"],
                "dev_episodes": best_dev["episodes"],
                "dev_solve_rate": best_dev["solve_rate"],
                "families": best_dev["families"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
