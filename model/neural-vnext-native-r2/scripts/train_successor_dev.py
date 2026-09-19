from __future__ import annotations

import argparse
import copy
from hashlib import sha256
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
from native_training import evaluate_policy, load_checkpoint  # noqa: E402
from successor_core import NativeR2TransitionPolicy  # noqa: E402
from successor_training import (  # noqa: E402
    evaluate_successor,
    load_lock,
    save_successor_checkpoint,
    train_successor_policy,
)


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


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


def _compact(result: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "rows"}


def _rank(result: Mapping[str, Any]) -> tuple[int, int, int]:
    family_min = min(
        int(row["solved"])
        for row in result["families"].values()
    )
    return (
        int(result["solved"]),
        family_min,
        -int(result["steps"]),
    )


def _eligibility(
    parent: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    total_improved = int(candidate["solved"]) > int(parent["solved"])
    family_regression = {
        family: int(candidate["families"][family]["solved"])
        - int(parent["families"][family]["solved"])
        for family in parent["families"]
    }
    no_large_regression = all(delta >= -2 for delta in family_regression.values())
    target_gain = any(
        int(candidate["families"][family]["solved"])
        > int(parent["families"][family]["solved"])
        for family in ("regime_switch", "implicit_goal_regimes")
    )
    eligible = bool(total_improved and no_large_regression and target_gain)
    return {
        "eligible": eligible,
        "total_improved": total_improved,
        "no_family_regression_below_minus_2": no_large_regression,
        "target_family_gain": target_gain,
        "family_solved_delta": family_regression,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Train Neural vNext Native R2 transition-trace residuals against the "
            "frozen accepted parent. Development only; fresh is forbidden."
        )
    )
    parser.add_argument("--lock", type=Path, default=ROOT / "PREDEV_LOCK.json")
    parser.add_argument("--parent-checkpoint", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dev-result", required=True, type=Path)
    args = parser.parse_args()

    lock = load_lock(args.lock)
    benchmark = lock["benchmark"]
    parent_lock = lock["parent"]
    training = lock["training"]
    architecture = lock["architecture"]

    if benchmark["training_split"] != "train":
        raise ValueError("successor training split must be train")
    if benchmark["development_split"] != "dev":
        raise ValueError("successor development split must be dev")
    if lock["fresh_isolation"]["status"] != "UNOPENED":
        raise ValueError("successor fresh court must remain unopened")
    if benchmark["fresh_indices"] != [40, 79]:
        raise ValueError("R2 successor must reserve fresh:40..79")

    seed = int(training["seed"])
    runtime = _configure_deterministic_runtime(seed)

    parent, parent_metadata = load_checkpoint(args.parent_checkpoint)
    actual_parent_checkpoint = str(parent_metadata["checkpoint_sha256"])
    actual_parent_state = str(parent_metadata["state_dict_sha256"])
    if actual_parent_checkpoint != str(parent_lock["checkpoint_sha256"]):
        raise ValueError(
            "accepted parent checkpoint hash mismatch: "
            f"{actual_parent_checkpoint}"
        )
    if actual_parent_state != str(parent_lock["state_dict_sha256"]):
        raise ValueError(
            "accepted parent state hash mismatch: "
            f"{actual_parent_state}"
        )
    for parameter in parent.parameters():
        parameter.requires_grad_(False)
    parent.eval()

    families = tuple(str(value) for value in benchmark["families"])
    train_indices = tuple(int(value) for value in benchmark["successor_training_indices"])
    dev_indices = tuple(int(value) for value in benchmark["development_indices"])

    parent_dev = evaluate_policy(
        parent,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=dev_indices,
    )
    parent_state_before = state_dict_sha256(parent.state_dict())

    candidates: list[dict[str, Any]] = []
    selected_model: NativeR2TransitionPolicy | None = None
    selected_name: str | None = None
    selected_dev: dict[str, Any] | None = None
    selected_training: dict[str, Any] | None = None
    selected_eligibility: dict[str, Any] | None = None
    selected_rank: tuple[int, int, int] | None = None

    for candidate in training["candidate_curricula"]:
        name = str(candidate["name"])
        torch.manual_seed(seed)
        candidate_parent = copy.deepcopy(parent)
        model = NativeR2TransitionPolicy(
            candidate_parent,
            trace_token_dim=int(architecture["transition_token_dim"]),
            trace_hidden_dim=int(architecture["trace_hidden_dim"]),
            trace_length=int(architecture["transition_trace_length"]),
        )
        initial_parent_state = state_dict_sha256(model.parent.state_dict())
        if initial_parent_state != actual_parent_state:
            raise ValueError("successor construction changed frozen parent state")

        train_summary = train_successor_policy(
            model,
            make_task=make_r18_task,
            oracle_plan=oracle_plan,
            families=families,
            train_indices=train_indices,
            seed=seed,
            expert_epochs=int(candidate["expert_epochs"]),
            dagger_teacher_mix=[
                float(value)
                for value in candidate["dagger_teacher_mix"]
            ],
            learning_rate=float(candidate["learning_rate"]),
            weight_decay=float(training["weight_decay"]),
            max_grad_norm=float(training["max_grad_norm"]),
            residual_l2_weight=float(candidate["residual_l2_weight"]),
        )
        final_parent_state = state_dict_sha256(model.parent.state_dict())
        if final_parent_state != actual_parent_state:
            raise ValueError(
                f"candidate {name} mutated frozen parent parameters"
            )

        dev = evaluate_successor(
            model,
            make_task=make_r18_task,
            families=families,
            split="dev",
            indices=dev_indices,
        )
        eligibility = _eligibility(parent_dev, dev)
        rank = _rank(dev)
        row = {
            "name": name,
            "rank": list(rank),
            "eligibility": eligibility,
            "development": _compact(dev),
            "training": train_summary,
        }
        candidates.append(row)
        print(
            json.dumps(
                {
                    "status": "R2_DEV_CANDIDATE_COMPLETE_FRESH_UNOPENED",
                    "candidate": name,
                    "rank": list(rank),
                    "eligibility": eligibility,
                    "parent_dev_solved": parent_dev["solved"],
                    "candidate_dev_solved": dev["solved"],
                    "families": dev["families"],
                    "successor_parameters": model.successor_parameter_count(),
                    "full_parameters": model.full_parameter_count(),
                },
                sort_keys=True,
            )
        )

        if not eligibility["eligible"]:
            continue
        better = selected_rank is None or rank > selected_rank
        lexical = (
            selected_rank is not None
            and rank == selected_rank
            and selected_name is not None
            and name < selected_name
        )
        if better or lexical:
            selected_model = model
            selected_name = name
            selected_dev = dev
            selected_training = train_summary
            selected_eligibility = eligibility
            selected_rank = rank

    if state_dict_sha256(parent.state_dict()) != parent_state_before:
        raise ValueError("development tournament mutated source parent instance")

    if selected_model is None:
        best = max(candidates, key=lambda row: (tuple(row["rank"]), row["name"]))
        raise RuntimeError(
            "no successor candidate satisfied preregistered eligibility; "
            f"best observed={best['name']} rank={best['rank']}"
        )

    training_summary = {
        "seed": seed,
        "deterministic_runtime": runtime,
        "parent_dev": _compact(parent_dev),
        "selected_candidate": selected_name,
        "selected_rank": list(selected_rank),
        "selected_eligibility": selected_eligibility,
        "selected_training": selected_training,
        "tournament": candidates,
        "fresh_opened": False,
    }
    manifest = save_successor_checkpoint(
        selected_model,
        args.checkpoint,
        parent_checkpoint_sha256=actual_parent_checkpoint,
        parent_state_dict_sha256=actual_parent_state,
        predev_lock_sha256=_sha256_file(args.lock),
        training_summary=training_summary,
    )
    manifest["selected_candidate"] = selected_name
    manifest["selected_rank"] = list(selected_rank)
    manifest["selected_eligibility"] = selected_eligibility
    manifest["parent_dev_evaluation"] = _compact(parent_dev)
    manifest["dev_evaluation"] = _compact(selected_dev)
    manifest["fresh_opened"] = False

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.dev_result.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.dev_result.write_text(
        json.dumps(selected_dev, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "R2_DEV_TOURNAMENT_COMPLETE_FRESH_UNOPENED",
                "selected_candidate": selected_name,
                "selected_rank": list(selected_rank),
                "selected_eligibility": selected_eligibility,
                "parent_dev_solved": parent_dev["solved"],
                "dev_solved": selected_dev["solved"],
                "dev_episodes": selected_dev["episodes"],
                "dev_solve_rate": selected_dev["solve_rate"],
                "families": selected_dev["families"],
                "full_parameters": selected_model.full_parameter_count(),
                "successor_parameters": selected_model.successor_parameter_count(),
                "checkpoint_sha256": manifest["checkpoint_sha256"],
                "state_dict_sha256": manifest["state_dict_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
