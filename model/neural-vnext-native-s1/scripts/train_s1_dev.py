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
PARENT_ROOT = MODEL_ROOT / "neural-vnext-native"
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (ROOT, PARENT_ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from cogcoder.r18_benchmark import make_r18_task, oracle_plan  # noqa: E402
from native_core import state_dict_sha256  # noqa: E402
from native_training import (  # noqa: E402
    evaluate_policy as evaluate_parent,
    load_checkpoint as load_parent_checkpoint,
)
from successor_core import DualTimescaleResidualPolicy  # noqa: E402
from successor_training import (  # noqa: E402
    evaluate_policy,
    load_lock,
    save_checkpoint,
    sha256_json_file,
    train_policy,
)


def _configure_deterministic_runtime(seed: int) -> dict[str, Any]:
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    torch.use_deterministic_algorithms(True)
    torch.backends.mkldnn.enabled = False
    torch.set_float32_matmul_precision("highest")
    torch.set_flush_denormal(True)
    torch.manual_seed(int(seed))
    return {
        "seed": int(seed),
        "deterministic_algorithms": bool(torch.are_deterministic_algorithms_enabled()),
        "mkldnn_enabled": bool(torch.backends.mkldnn.enabled),
        "float32_matmul_precision": str(torch.get_float32_matmul_precision()),
        "num_threads": int(torch.get_num_threads()),
        "num_interop_threads": int(torch.get_num_interop_threads()),
    }


def _rank(dev: Mapping[str, Any]) -> tuple[int, int, int]:
    families = dev["families"]
    return (
        int(dev["solved"]),
        min(int(row["solved"]) for row in families.values()),
        -int(dev["steps"]),
    )


def _compact(dev: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in dev.items() if key != "rows"}


def _freeze_readiness(
    parent_dev: Mapping[str, Any],
    candidate_dev: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    rule = lock["training"]["freeze_readiness"]
    gain = int(candidate_dev["solved"]) - int(parent_dev["solved"])
    regressions = {
        family: int(parent_dev["families"][family]["solved"])
        - int(candidate_dev["families"][family]["solved"])
        for family in parent_dev["families"]
    }
    worst_regression = max(regressions.values())
    gain_pass = gain >= int(rule["minimum_gain_over_parent_solved"])
    regression_pass = worst_regression <= int(rule["maximum_family_regression_solved"])
    return {
        "ready": bool(gain_pass and regression_pass),
        "gain_over_parent_solved": gain,
        "minimum_gain_required": int(rule["minimum_gain_over_parent_solved"]),
        "gain_pass": gain_pass,
        "family_regressions": regressions,
        "worst_family_regression": worst_regression,
        "maximum_family_regression_allowed": int(rule["maximum_family_regression_solved"]),
        "family_regression_pass": regression_pass,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train Neural vNext Native S1 on train only and evaluate new dev 32..63."
    )
    parser.add_argument("--lock", type=Path, default=ROOT / "PREDEV_LOCK.json")
    parser.add_argument("--parent-checkpoint", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dev-result", type=Path, required=True)
    args = parser.parse_args()

    lock = load_lock(args.lock)
    parent_authority = lock["parent_authority"]
    benchmark = lock["benchmark"]
    training = lock["training"]
    architecture = lock["architecture"]
    seed = int(training["seed"])
    deterministic_runtime = _configure_deterministic_runtime(seed)

    parent_model, parent_metadata = load_parent_checkpoint(args.parent_checkpoint)
    if parent_metadata["checkpoint_sha256"] != parent_authority["checkpoint_sha256"]:
        raise ValueError("parent checkpoint SHA does not match accepted authority")
    if parent_metadata["state_dict_sha256"] != parent_authority["state_dict_sha256"]:
        raise ValueError("parent state SHA does not match accepted authority")
    parent_state_sha = state_dict_sha256(parent_model.state_dict())
    if parent_state_sha != parent_authority["state_dict_sha256"]:
        raise ValueError("loaded parent tensors do not match accepted authority")

    families = tuple(str(value) for value in benchmark["families"])
    dev_indices = tuple(int(value) for value in benchmark["development_indices"])
    if benchmark["development_split"] != "dev":
        raise ValueError("S1 development split must be dev")
    if list(benchmark["fresh_indices_reserved"]) != [40, 79]:
        raise ValueError("S1 must reserve fresh 40..79")
    if lock["fresh_isolation"]["status"] != "UNOPENED":
        raise ValueError("S1 fresh must remain unopened during development")

    parent_dev = evaluate_parent(
        parent_model,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=(dev_indices[0], dev_indices[1]),
    )
    print(
        json.dumps(
            {
                "status": "S1_PARENT_NEW_DEV_COMPLETE_FRESH_UNOPENED",
                "solved": parent_dev["solved"],
                "episodes": parent_dev["episodes"],
                "solve_rate": parent_dev["solve_rate"],
                "families": parent_dev["families"],
                "state_dict_sha256": parent_state_sha,
            },
            sort_keys=True,
        )
    )

    best_model: DualTimescaleResidualPolicy | None = None
    best_name = ""
    best_rank: tuple[int, int, int] | None = None
    best_dev: dict[str, Any] | None = None
    best_summary: dict[str, Any] | None = None
    best_readiness: dict[str, Any] | None = None
    tournament: list[dict[str, Any]] = []

    for candidate in training["candidates"]:
        name = str(candidate["name"])
        # Reload the exact accepted parent and rebuild the specialist from the
        # same seed so candidates differ only by locked training curriculum.
        parent, metadata = load_parent_checkpoint(args.parent_checkpoint)
        if metadata["state_dict_sha256"] != parent_authority["state_dict_sha256"]:
            raise ValueError("candidate parent reload mismatch")
        torch.manual_seed(seed)
        model = DualTimescaleResidualPolicy(
            parent,
            specialist_dim=int(architecture["specialist_dim"]),
        )
        initial_parent_sha = state_dict_sha256(model.parent.state_dict())
        summary = train_policy(
            model,
            make_task=make_r18_task,
            oracle_plan=oracle_plan,
            family_train_indices=training["family_training_indices"],
            seed=seed,
            expert_epochs=int(candidate["expert_epochs"]),
            dagger_teacher_mix=[float(value) for value in candidate["dagger_teacher_mix"]],
            learning_rate=float(candidate["learning_rate"]),
            weight_decay=float(training["weight_decay"]),
            max_grad_norm=float(training["max_grad_norm"]),
        )
        final_parent_sha = state_dict_sha256(model.parent.state_dict())
        if initial_parent_sha != parent_authority["state_dict_sha256"]:
            raise AssertionError("S1 candidate did not start from exact parent")
        if final_parent_sha != initial_parent_sha:
            raise AssertionError("S1 training mutated accepted parent tensors")

        dev = evaluate_policy(
            model,
            make_task=make_r18_task,
            families=families,
            split="dev",
            indices=(dev_indices[0], dev_indices[1]),
        )
        rank = _rank(dev)
        readiness = _freeze_readiness(parent_dev, dev, lock)
        row = {
            "name": name,
            "rank": list(rank),
            "development": _compact(dev),
            "training": summary,
            "freeze_readiness": readiness,
            "parent_state_preserved": True,
        }
        tournament.append(row)
        print(
            json.dumps(
                {
                    "status": "S1_DEV_CANDIDATE_COMPLETE_FRESH_UNOPENED",
                    "candidate": name,
                    "rank": list(rank),
                    "solved": dev["solved"],
                    "episodes": dev["episodes"],
                    "families": dev["families"],
                    "freeze_readiness": readiness,
                    "parent_state_preserved": True,
                },
                sort_keys=True,
            )
        )

        if (
            best_rank is None
            or rank > best_rank
            or (rank == best_rank and name < best_name)
        ):
            best_model = model
            best_name = name
            best_rank = rank
            best_dev = dev
            best_summary = summary
            best_readiness = readiness

    if best_model is None or best_dev is None or best_summary is None or best_readiness is None:
        raise AssertionError("S1 tournament produced no candidate")

    manifest = save_checkpoint(
        best_model,
        args.checkpoint,
        predev_lock_sha256=sha256_json_file(args.lock),
        parent_checkpoint_sha256=parent_authority["checkpoint_sha256"],
        parent_state_dict_sha256=parent_authority["state_dict_sha256"],
        training_summary={
            "seed": seed,
            "deterministic_runtime": deterministic_runtime,
            "parent_new_dev": _compact(parent_dev),
            "selected_candidate": best_name,
            "selected_rank": list(best_rank),
            "selected_training": best_summary,
            "selected_freeze_readiness": best_readiness,
            "tournament": tournament,
            "fresh_opened": False,
        },
    )
    manifest["selected_candidate"] = best_name
    manifest["selected_rank"] = list(best_rank)
    manifest["parent_new_dev"] = _compact(parent_dev)
    manifest["dev_evaluation"] = _compact(best_dev)
    manifest["freeze_readiness"] = best_readiness
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
                "status": "S1_DEV_TOURNAMENT_COMPLETE_FRESH_UNOPENED",
                "selected_candidate": best_name,
                "selected_rank": list(best_rank),
                "parent_new_dev_solved": parent_dev["solved"],
                "dev_solved": best_dev["solved"],
                "dev_episodes": best_dev["episodes"],
                "dev_solve_rate": best_dev["solve_rate"],
                "families": best_dev["families"],
                "freeze_readiness": best_readiness,
                "checkpoint_sha256": manifest["checkpoint_sha256"],
                "state_dict_sha256": manifest["state_dict_sha256"],
                "parent_state_dict_sha256": manifest["parent_state_dict_sha256"],
                "parameters": manifest["parameters"],
                "specialist_parameters": manifest["specialist_parameters"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
