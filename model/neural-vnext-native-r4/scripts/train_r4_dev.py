from __future__ import annotations

import argparse
import copy
from hashlib import sha256
import json
from pathlib import Path
import random
import sys
from typing import Any, Mapping

import torch

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
MODEL_ROOT = HERE.parents[2]
R3_ROOT = MODEL_ROOT / "neural-vnext-native-r3"
R2_ROOT = MODEL_ROOT / "neural-vnext-native-r2"
NATIVE_ROOT = MODEL_ROOT / "neural-vnext-native"
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (ROOT, R3_ROOT, R2_ROOT, NATIVE_ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from cogcoder.r18_benchmark import make_r18_task, oracle_plan  # noqa: E402
from native_core import state_dict_sha256  # noqa: E402
from attributed_training import evaluate_r3, load_r3_checkpoint  # noqa: E402
from goal_belief_core import NativeR4PublicGoalBeliefPolicy  # noqa: E402
from goal_belief_training import (  # noqa: E402
    evaluate_r4,
    save_r4_checkpoint,
    train_r4_policy,
)


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _configure_runtime(seed: int) -> dict[str, Any]:
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
    random.seed(int(seed))
    return {
        "seed": int(seed),
        "deterministic_algorithms": bool(
            torch.are_deterministic_algorithms_enabled()
        ),
        "mkldnn_enabled": bool(torch.backends.mkldnn.enabled),
        "num_threads": int(torch.get_num_threads()),
        "num_interop_threads": int(torch.get_num_interop_threads()),
    }


def _compact(result: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "rows"}


def _family_solved(result: Mapping[str, Any]) -> dict[str, int]:
    return {
        str(family): int(row["solved"])
        for family, row in result["families"].items()
    }


def _eligibility(
    parent: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    base = _family_solved(parent)
    current = _family_solved(candidate)
    visible = ("conditional_regimes", "regime_switch", "causal_prerequisites")
    visible_exact = all(current[family] == base[family] for family in visible)
    implicit_delta = current["implicit_goal_regimes"] - base["implicit_goal_regimes"]
    total_delta = int(candidate["solved"]) - int(parent["solved"])
    deltas = {family: current[family] - base[family] for family in base}
    return {
        "eligible": bool(visible_exact and implicit_delta > 0 and total_delta > 0),
        "visible_target_families_exact": visible_exact,
        "implicit_goal_delta_vs_parent": implicit_delta,
        "total_solved_delta_vs_parent": total_delta,
        "family_solved_delta_vs_parent": deltas,
    }


def _rank(result: Mapping[str, Any], name: str) -> tuple[int, int, int, str]:
    return (
        int(result["families"]["implicit_goal_regimes"]["solved"]),
        int(result["solved"]),
        -int(result["steps"]),
        str(name),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train R4 public goal-consistency belief residual on frozen accepted R3."
    )
    parser.add_argument("--lock", type=Path, default=ROOT / "PREDEV_LOCK.json")
    parser.add_argument(
        "--parent-checkpoint",
        type=Path,
        default=R3_ROOT / "accepted" / "r3.pt",
    )
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dev-result", required=True, type=Path)
    args = parser.parse_args()

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("schema_version") != 1:
        raise ValueError("unsupported R4 PREDEV lock")
    if lock.get("candidate") != "Neural-vNext-Native-R4-PublicGoalConsistencyBelief":
        raise ValueError("unexpected R4 candidate identity")
    if lock["fresh_isolation"]["status"] != "UNOPENED":
        raise ValueError("R4 fresh court must remain unopened")
    if lock["benchmark"]["fresh_indices"] != [120, 159]:
        raise ValueError("R4 must reserve untouched fresh:120..159")

    parent_lock = lock["parent"]
    parent, parent_metadata = load_r3_checkpoint(args.parent_checkpoint)
    if parent_metadata["checkpoint_sha256"] != parent_lock["checkpoint_sha256"]:
        raise ValueError("accepted R3 checkpoint hash mismatch")
    if parent_metadata["state_dict_sha256"] != parent_lock["state_dict_sha256"]:
        raise ValueError("accepted R3 state hash mismatch")
    for parameter in parent.parameters():
        parameter.requires_grad_(False)
    parent.eval()

    training = lock["training"]
    benchmark = lock["benchmark"]
    architecture = lock["architecture"]
    seed = int(training["seed"])
    runtime = _configure_runtime(seed)
    families = tuple(str(v) for v in benchmark["families"])
    train_indices = tuple(int(v) for v in benchmark["hidden_training_indices"])
    dev_indices = tuple(int(v) for v in benchmark["development_indices"])

    parent_dev = evaluate_r3(
        parent,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=dev_indices,
    )
    print(json.dumps({
        "status": "R4_PARENT_BASELINE_FRESH_UNOPENED",
        "parent_dev_solved": parent_dev["solved"],
        "parent_dev_families": parent_dev["families"],
        "dev_indices": list(dev_indices),
    }, sort_keys=True))

    candidates: list[dict[str, Any]] = []
    selected_model = None
    selected_name = None
    selected_dev = None
    selected_training = None
    selected_eligibility = None
    selected_rank = None

    for candidate_index, cfg in enumerate(training["candidates"]):
        name = str(cfg["name"])
        torch.manual_seed(seed + candidate_index)
        model = NativeR4PublicGoalBeliefPolicy(
            copy.deepcopy(parent),
            belief_feature_dim=int(architecture["belief_feature_dim"]),
            belief_hidden_dim=int(architecture["belief_hidden_dim"]),
        )
        if state_dict_sha256(model.parent.state_dict()) != parent_lock["state_dict_sha256"]:
            raise ValueError(f"candidate {name} changed frozen R3 parent at init")

        train_summary = train_r4_policy(
            model,
            make_task=make_r18_task,
            oracle_plan=oracle_plan,
            families=("implicit_goal_regimes",),
            train_indices=train_indices,
            seed=seed + candidate_index,
            expert_epochs=int(cfg["expert_epochs"]),
            dagger_teacher_mix=[float(v) for v in cfg["dagger_teacher_mix"]],
            learning_rate=float(cfg["learning_rate"]),
            weight_decay=float(training["weight_decay"]),
            max_grad_norm=float(training["max_grad_norm"]),
            residual_l2_weight=float(cfg["residual_l2_weight"]),
        )
        if state_dict_sha256(model.parent.state_dict()) != parent_lock["state_dict_sha256"]:
            raise ValueError(f"candidate {name} mutated frozen R3 parent")

        dev = evaluate_r4(
            model,
            make_task=make_r18_task,
            families=families,
            split="dev",
            indices=dev_indices,
        )
        eligibility = _eligibility(parent_dev, dev)
        rank = _rank(dev, name)
        row = {
            "name": name,
            "training": train_summary,
            "development": _compact(dev),
            "eligibility": eligibility,
            "rank": list(rank),
        }
        candidates.append(row)
        print(json.dumps({
            "candidate": name,
            "dev_solved": dev["solved"],
            "dev_families": dev["families"],
            "eligibility": eligibility,
            "rank": list(rank),
            "fresh_opened": False,
        }, sort_keys=True))
        if eligibility["eligible"] and (
            selected_rank is None or rank > selected_rank
        ):
            selected_model = model
            selected_name = name
            selected_dev = dev
            selected_training = train_summary
            selected_eligibility = eligibility
            selected_rank = rank

    predev_sha = _sha256_file(args.lock)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    if selected_model is None:
        payload = {
            "schema_version": 1,
            "status": "R4_DEV_NO_ELIGIBLE_CANDIDATE_FRESH_UNOPENED",
            "parent_checkpoint_sha256": parent_metadata["checkpoint_sha256"],
            "parent_state_dict_sha256": parent_metadata["state_dict_sha256"],
            "predev_lock_sha256": predev_sha,
            "runtime": runtime,
            "parent_development": _compact(parent_dev),
            "candidates": candidates,
            "fresh_opened": False,
        }
        args.manifest.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        args.dev_result.write_text(
            json.dumps({
                "parent": parent_dev,
                "candidates": candidates,
                "fresh_opened": False,
            }, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "status": payload["status"],
            "parent_dev_solved": parent_dev["solved"],
            "fresh_opened": False,
        }, sort_keys=True))
        return 2

    training_summary = {
        "selected_candidate": selected_name,
        "selected_rank": list(selected_rank),
        "selected_eligibility": selected_eligibility,
        "selected_training": selected_training,
        "parent_development": _compact(parent_dev),
        "candidate_tournament": candidates,
        "runtime": runtime,
        "fresh_opened": False,
    }
    metadata = save_r4_checkpoint(
        selected_model,
        args.checkpoint,
        parent_checkpoint_sha256=parent_metadata["checkpoint_sha256"],
        parent_state_dict_sha256=parent_metadata["state_dict_sha256"],
        predev_lock_sha256=predev_sha,
        training_summary=training_summary,
    )
    manifest = {
        **metadata,
        "schema_version": 1,
        "status": "R4_DEV_ELIGIBLE_FRESH_UNOPENED",
        "selected_candidate": selected_name,
        "selected_rank": list(selected_rank),
        "selected_eligibility": selected_eligibility,
        "parent_development": _compact(parent_dev),
        "dev_evaluation": _compact(selected_dev),
        "candidate_tournament": candidates,
        "fresh_opened": False,
    }
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.dev_result.write_text(
        json.dumps(selected_dev, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": manifest["status"],
        "selected_candidate": selected_name,
        "parent_dev_solved": parent_dev["solved"],
        "selected_dev_solved": selected_dev["solved"],
        "selected_dev_families": selected_dev["families"],
        "parameters": metadata["parameters"],
        "successor_parameters": metadata["successor_parameters"],
        "checkpoint_sha256": metadata["checkpoint_sha256"],
        "state_dict_sha256": metadata["state_dict_sha256"],
        "fresh_opened": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
