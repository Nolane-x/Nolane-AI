from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

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
    configure_training_scope,
    evaluate_policy,
    load_lock,
    save_checkpoint,
    sha256_json_file,
    train_native_policy,
)


def _candidate_rank(dev: Mapping[str, Any]) -> tuple[int, int, int]:
    families = dev["families"]
    if not isinstance(families, dict) or not families:
        raise ValueError("development result is missing family metrics")
    solved = int(dev["solved"])
    worst_family = min(int(row["solved"]) for row in families.values())
    steps = int(dev["steps"])
    return solved, worst_family, -steps


def _compact_dev(dev: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in dev.items() if key != "rows"}


def _new_model(architecture: Mapping[str, Any]) -> NativeRecurrentPolicy:
    return NativeRecurrentPolicy(
        global_dim=int(architecture["public_global_features"]),
        action_dim=int(architecture["public_action_features"]),
        hidden_dim=int(architecture["hidden_dim"]),
        attention_heads=int(architecture["attention_heads"]),
    )


def _clone_state_dict(model: NativeRecurrentPolicy) -> dict[str, torch.Tensor]:
    return {
        name: tensor.detach().cpu().clone()
        for name, tensor in model.state_dict().items()
    }


def _assert_visible_families_preserved(
    base_dev: Mapping[str, Any],
    candidate_dev: Mapping[str, Any],
) -> None:
    for family in (
        "conditional_regimes",
        "regime_switch",
        "causal_prerequisites",
    ):
        if candidate_dev["families"][family] != base_dev["families"][family]:
            raise AssertionError(
                f"hidden-goal specialist changed visible family {family}: "
                f"base={base_dev['families'][family]} "
                f"candidate={candidate_dev['families'][family]}"
            )


def _configure_deterministic_runtime(seed: int) -> dict[str, Any]:
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        # Safe when a parent runtime already initialized the interop pool.
        pass
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(int(seed))
    return {
        "seed": int(seed),
        "deterministic_algorithms": bool(torch.are_deterministic_algorithms_enabled()),
        "num_threads": int(torch.get_num_threads()),
        "num_interop_threads": int(torch.get_num_interop_threads()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Train a deterministic shared Neural vNext Native base, freeze it, "
            "then tune hidden-goal residual specialists on dev only. Fresh is never instantiated."
        )
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
    deterministic_runtime = _configure_deterministic_runtime(seed)

    base_cfg = training.get("base_curriculum")
    base_family_ranges = training.get("base_family_training_indices")
    specialist_candidates = training.get("hidden_goal_specialists")
    specialist_ranges = training.get("hidden_goal_family_training_indices")
    if not isinstance(base_cfg, dict):
        raise ValueError("base_curriculum must be an object")
    if not isinstance(base_family_ranges, dict):
        raise ValueError("base_family_training_indices must be an object")
    if not isinstance(specialist_candidates, list) or not specialist_candidates:
        raise ValueError("hidden_goal_specialists must be a non-empty list")
    if not isinstance(specialist_ranges, dict):
        raise ValueError("hidden_goal_family_training_indices must be an object")

    # Stage A: one shared base, trained with the hidden-goal specialist frozen.
    torch.manual_seed(seed)
    base_model = _new_model(architecture)
    base_scope = configure_training_scope(base_model, "base")
    base_summary = train_native_policy(
        base_model,
        make_task=make_r18_task,
        oracle_plan=oracle_plan,
        families=families,
        train_indices=(train_indices[0], train_indices[1]),
        family_train_indices=base_family_ranges,
        seed=seed,
        expert_epochs=int(base_cfg["expert_epochs"]),
        dagger_teacher_mix=[float(value) for value in base_cfg["dagger_teacher_mix"]],
        learning_rate=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
        max_grad_norm=float(training["max_grad_norm"]),
        goal_loss_weight=0.0,
    )
    base_dev = evaluate_policy(
        base_model,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=(dev_indices[0], dev_indices[1]),
    )
    base_rank = _candidate_rank(base_dev)
    print(
        json.dumps(
            {
                "status": "DEV_BASE_COMPLETE_FRESH_UNOPENED",
                "candidate": "base_only",
                "rank": list(base_rank),
                "dev_solved": base_dev["solved"],
                "dev_episodes": base_dev["episodes"],
                "families": base_dev["families"],
                "scope": base_scope,
            },
            sort_keys=True,
        )
    )

    base_state = _clone_state_dict(base_model)
    best_model = base_model
    best_name = "base_only"
    best_rank = base_rank
    best_dev = base_dev
    best_training: dict[str, Any] = {
        "kind": "base_only",
        "base": base_summary,
        "scope": base_scope,
    }
    tournament: list[dict[str, Any]] = [
        {
            "name": "base_only",
            "rank": list(base_rank),
            "development": _compact_dev(base_dev),
            "training": base_summary,
            "scope": base_scope,
        }
    ]

    # Stage B: reset to the exact base for every specialist candidate, freeze the
    # shared core, and expose only hidden-goal residual parameters to the optimizer.
    for candidate in specialist_candidates:
        if not isinstance(candidate, dict):
            raise ValueError("hidden_goal_specialists entries must be objects")
        name = str(candidate["name"])
        torch.manual_seed(seed)
        model = _new_model(architecture)
        model.load_state_dict(base_state, strict=True)
        scope = configure_training_scope(model, "hidden_goal")
        specialist_summary = train_native_policy(
            model,
            make_task=make_r18_task,
            oracle_plan=oracle_plan,
            families=("implicit_goal_regimes",),
            train_indices=(
                int(specialist_ranges["implicit_goal_regimes"][0]),
                int(specialist_ranges["implicit_goal_regimes"][1]),
            ),
            family_train_indices={
                "implicit_goal_regimes": specialist_ranges["implicit_goal_regimes"],
            },
            seed=seed,
            expert_epochs=int(candidate["expert_epochs"]),
            dagger_teacher_mix=[float(value) for value in candidate["dagger_teacher_mix"]],
            learning_rate=float(candidate.get("learning_rate", training["learning_rate"])),
            weight_decay=float(training["weight_decay"]),
            max_grad_norm=float(training["max_grad_norm"]),
            goal_loss_weight=float(candidate.get("goal_loss_weight", training["goal_belief"]["loss_weight"])),
        )
        dev = evaluate_policy(
            model,
            make_task=make_r18_task,
            families=families,
            split="dev",
            indices=(dev_indices[0], dev_indices[1]),
        )
        _assert_visible_families_preserved(base_dev, dev)
        rank = _candidate_rank(dev)
        tournament.append(
            {
                "name": name,
                "rank": list(rank),
                "development": _compact_dev(dev),
                "training": specialist_summary,
                "scope": scope,
                "visible_families_preserved": True,
            }
        )
        print(
            json.dumps(
                {
                    "status": "DEV_HIDDEN_GOAL_SPECIALIST_COMPLETE_FRESH_UNOPENED",
                    "candidate": name,
                    "rank": list(rank),
                    "dev_solved": dev["solved"],
                    "dev_episodes": dev["episodes"],
                    "families": dev["families"],
                    "scope": scope,
                    "visible_families_preserved": True,
                },
                sort_keys=True,
            )
        )

        better = rank > best_rank
        tied_but_lexical = rank == best_rank and name < best_name
        if better or tied_but_lexical:
            best_model = model
            best_name = name
            best_rank = rank
            best_dev = dev
            best_training = {
                "kind": "base_plus_hidden_goal_specialist",
                "base": base_summary,
                "specialist": specialist_summary,
                "scope": scope,
            }

    training_summary = {
        "seed": seed,
        "deterministic_runtime": deterministic_runtime,
        "selected_candidate": best_name,
        "selected_rank": list(best_rank),
        "selected_training": best_training,
        "base_development": _compact_dev(base_dev),
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
    manifest["base_dev_evaluation"] = _compact_dev(base_dev)
    manifest["dev_evaluation"] = _compact_dev(best_dev)
    manifest["fresh_opened"] = False

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.dev_result.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.dev_result.write_text(
        json.dumps(best_dev, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "DEV_TOURNAMENT_COMPLETE_FRESH_UNOPENED",
                "deterministic_runtime": deterministic_runtime,
                "selected_candidate": best_name,
                "selected_rank": list(best_rank),
                "parameters": parameter_count(best_model),
                "checkpoint_sha256": manifest["checkpoint_sha256"],
                "state_dict_sha256": manifest["state_dict_sha256"],
                "base_dev_solved": base_dev["solved"],
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
