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
R2_ROOT = MODEL_ROOT / "neural-vnext-native-r2"
NATIVE_ROOT = MODEL_ROOT / "neural-vnext-native"
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (ROOT, R2_ROOT, NATIVE_ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from cogcoder.r18_benchmark import make_r18_task, oracle_plan  # noqa: E402
from native_core import state_dict_sha256  # noqa: E402
from successor_training import (  # noqa: E402
    evaluate_successor as evaluate_r2,
    load_successor_checkpoint,
)
from attributed_core import NativeR3AttributedBeliefPolicy  # noqa: E402
from attributed_training import (  # noqa: E402
    evaluate_r3,
    load_lock,
    save_r3_checkpoint,
    train_r3_policy,
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
        "deterministic_algorithms": bool(
            torch.are_deterministic_algorithms_enabled()
        ),
        "mkldnn_enabled": bool(torch.backends.mkldnn.enabled),
        "float32_matmul_precision": str(torch.get_float32_matmul_precision()),
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
    parent_families = _family_solved(parent)
    candidate_families = _family_solved(candidate)
    visible_families = (
        "conditional_regimes",
        "regime_switch",
        "causal_prerequisites",
    )
    visible_exact = all(
        candidate_families[family] == parent_families[family]
        for family in visible_families
    )
    implicit_delta = (
        candidate_families["implicit_goal_regimes"]
        - parent_families["implicit_goal_regimes"]
    )
    total_delta = int(candidate["solved"]) - int(parent["solved"])
    deltas = {
        family: candidate_families[family] - parent_families[family]
        for family in parent_families
    }
    return {
        "eligible": bool(
            visible_exact
            and implicit_delta > 0
            and total_delta > 0
        ),
        "visible_target_families_exact": visible_exact,
        "implicit_goal_delta_vs_parent": implicit_delta,
        "total_solved_delta_vs_parent": total_delta,
        "family_solved_delta_vs_parent": deltas,
    }


def _rank(
    result: Mapping[str, Any],
    name: str,
) -> tuple[int, int, int, str]:
    return (
        int(result["families"]["implicit_goal_regimes"]["solved"]),
        int(result["solved"]),
        -int(result["steps"]),
        str(name),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Train Neural vNext Native R3 action-attributed hidden-goal memory "
            "on a frozen accepted R2 checkpoint. Fresh remains forbidden."
        )
    )
    parser.add_argument("--lock", type=Path, default=ROOT / "PREDEV_LOCK.json")
    parser.add_argument(
        "--parent-checkpoint",
        type=Path,
        default=R2_ROOT / "accepted" / "successor.pt",
    )
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
        raise ValueError("R3 training split must be train")
    if benchmark["development_split"] != "dev":
        raise ValueError("R3 development split must be dev")
    if benchmark["fresh_split"] != "fresh":
        raise ValueError("R3 fresh split must be fresh")
    if benchmark["fresh_indices"] != [80, 119]:
        raise ValueError("R3 must reserve untouched fresh:80..119")
    if lock["fresh_isolation"]["status"] != "UNOPENED":
        raise ValueError("R3 fresh court must remain unopened")

    seed = int(training["seed"])
    runtime = _configure_deterministic_runtime(seed)
    parent, parent_metadata = load_successor_checkpoint(args.parent_checkpoint)
    actual_parent_checkpoint = str(parent_metadata["checkpoint_sha256"])
    actual_parent_state = str(parent_metadata["state_dict_sha256"])
    if actual_parent_checkpoint != str(parent_lock["checkpoint_sha256"]):
        raise ValueError(
            "accepted R2 checkpoint hash mismatch: "
            f"{actual_parent_checkpoint}"
        )
    if actual_parent_state != str(parent_lock["state_dict_sha256"]):
        raise ValueError(
            "accepted R2 state hash mismatch: "
            f"{actual_parent_state}"
        )
    for parameter in parent.parameters():
        parameter.requires_grad_(False)
    parent.eval()

    families = tuple(str(value) for value in benchmark["families"])
    train_indices = tuple(
        int(value) for value in benchmark["hidden_training_indices"]
    )
    dev_indices = tuple(
        int(value) for value in benchmark["development_indices"]
    )

    parent_dev = evaluate_r2(
        parent,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=dev_indices,
    )
    print(
        json.dumps(
            {
                "status": "R3_PARENT_BASELINE_FRESH_UNOPENED",
                "parent_dev_solved": parent_dev["solved"],
                "parent_dev_families": parent_dev["families"],
                "dev_indices": list(dev_indices),
            },
            sort_keys=True,
        )
    )

    candidates: list[dict[str, Any]] = []
    selected_model: NativeR3AttributedBeliefPolicy | None = None
    selected_name: str | None = None
    selected_dev: dict[str, Any] | None = None
    selected_training: dict[str, Any] | None = None
    selected_eligibility: dict[str, Any] | None = None
    selected_rank: tuple[int, int, int, str] | None = None

    for candidate_index, cfg in enumerate(training["candidates"]):
        name = str(cfg["name"])
        torch.manual_seed(seed + candidate_index)
        model = NativeR3AttributedBeliefPolicy(
            copy.deepcopy(parent),
            attribution_token_dim=int(architecture["attribution_token_dim"]),
            attribution_hidden_dim=int(architecture["attribution_hidden_dim"]),
            attribution_length=int(architecture["attribution_trace_length"]),
        )
        if state_dict_sha256(model.parent.state_dict()) != actual_parent_state:
            raise ValueError(f"candidate {name} changed frozen R2 parent at init")

        train_summary = train_r3_policy(
            model,
            make_task=make_r18_task,
            oracle_plan=oracle_plan,
            families=("implicit_goal_regimes",),
            train_indices=train_indices,
            seed=seed + candidate_index,
            expert_epochs=int(cfg["expert_epochs"]),
            dagger_teacher_mix=[
                float(value) for value in cfg["dagger_teacher_mix"]
            ],
            learning_rate=float(cfg["learning_rate"]),
            weight_decay=float(training["weight_decay"]),
            max_grad_norm=float(training["max_grad_norm"]),
            residual_l2_weight=float(cfg["residual_l2_weight"]),
        )
        if state_dict_sha256(model.parent.state_dict()) != actual_parent_state:
            raise ValueError(f"candidate {name} mutated frozen R2 parent")

        dev = evaluate_r3(
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
        print(
            json.dumps(
                {
                    "candidate": name,
                    "dev_solved": dev["solved"],
                    "dev_families": dev["families"],
                    "eligibility": eligibility,
                    "rank": list(rank),
                    "fresh_opened": False,
                },
                sort_keys=True,
            )
        )
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
            "status": "R3_DEV_NO_ELIGIBLE_CANDIDATE_FRESH_UNOPENED",
            "parent_checkpoint_sha256": actual_parent_checkpoint,
            "parent_state_dict_sha256": actual_parent_state,
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
            json.dumps(
                {
                    "parent": parent_dev,
                    "candidates": [
                        {
                            "name": row["name"],
                            "development": row["development"],
                            "eligibility": row["eligibility"],
                        }
                        for row in candidates
                    ],
                    "fresh_opened": False,
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": payload["status"],
                    "parent_dev_solved": parent_dev["solved"],
                    "fresh_opened": False,
                },
                sort_keys=True,
            )
        )
        return 2

    assert selected_name is not None
    assert selected_dev is not None
    assert selected_training is not None
    assert selected_eligibility is not None
    assert selected_rank is not None

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
    checkpoint_metadata = save_r3_checkpoint(
        selected_model,
        args.checkpoint,
        parent_checkpoint_sha256=actual_parent_checkpoint,
        parent_state_dict_sha256=actual_parent_state,
        predev_lock_sha256=predev_sha,
        training_summary=training_summary,
    )
    manifest = {
        **checkpoint_metadata,
        "schema_version": 1,
        "status": "R3_DEV_ELIGIBLE_FRESH_UNOPENED",
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
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "selected_candidate": selected_name,
                "parent_dev_solved": parent_dev["solved"],
                "selected_dev_solved": selected_dev["solved"],
                "selected_dev_families": selected_dev["families"],
                "parameters": checkpoint_metadata["parameters"],
                "successor_parameters": checkpoint_metadata[
                    "successor_parameters"
                ],
                "checkpoint_sha256": checkpoint_metadata["checkpoint_sha256"],
                "state_dict_sha256": checkpoint_metadata["state_dict_sha256"],
                "fresh_opened": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
