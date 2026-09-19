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
from attributed_training import (  # noqa: E402
    evaluate_r3,
    load_r3_checkpoint,
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
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    base = _family_solved(baseline)
    current = _family_solved(candidate)
    visible = ("conditional_regimes", "regime_switch", "causal_prerequisites")
    visible_exact = all(current[family] == base[family] for family in visible)
    implicit_delta = current["implicit_goal_regimes"] - base["implicit_goal_regimes"]
    total_delta = int(candidate["solved"]) - int(baseline["solved"])
    deltas = {family: current[family] - base[family] for family in base}
    return {
        "eligible": bool(visible_exact and implicit_delta > 0 and total_delta > 0),
        "visible_target_families_exact": visible_exact,
        "implicit_goal_delta_vs_phase1": implicit_delta,
        "total_solved_delta_vs_phase1": total_delta,
        "family_solved_delta_vs_phase1": deltas,
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
        description=(
            "Continue the exact frozen R3 Phase-1 candidate on a new train block "
            "and select only on a new dev block. Fresh remains forbidden."
        )
    )
    parser.add_argument(
        "--lock",
        type=Path,
        default=ROOT / "PHASE2_LOCK.json",
    )
    parser.add_argument("--phase1-checkpoint", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dev-result", required=True, type=Path)
    args = parser.parse_args()

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("schema_version") != 1:
        raise ValueError("unsupported R3 Phase-2 lock")
    if lock.get("candidate") != "Neural-vNext-Native-R3-AttributedBelief-Phase2":
        raise ValueError("unexpected R3 Phase-2 candidate identity")
    if lock["fresh_isolation"]["status"] != "UNOPENED":
        raise ValueError("R3 Phase-2 fresh court must remain unopened")
    if lock["benchmark"]["fresh_indices"] != [80, 119]:
        raise ValueError("R3 Phase-2 must reserve fresh:80..119")

    phase1_authority = lock["phase1_authority"]
    if _sha256_file(args.phase1_checkpoint) != phase1_authority["checkpoint_sha256"]:
        raise ValueError("R3 Phase-1 checkpoint file hash mismatch")

    phase1_model, phase1_metadata = load_r3_checkpoint(args.phase1_checkpoint)
    if phase1_metadata["state_dict_sha256"] != phase1_authority["state_dict_sha256"]:
        raise ValueError("R3 Phase-1 state hash mismatch")
    if (
        phase1_metadata["training_summary"]["selected_candidate"]
        != phase1_authority["selected_candidate"]
    ):
        raise ValueError("R3 Phase-1 selected-candidate authority mismatch")
    if phase1_metadata["training_summary"]["fresh_opened"] is not False:
        raise ValueError("R3 Phase-1 checkpoint must attest fresh unopened")

    parent_state = state_dict_sha256(phase1_model.parent.state_dict())
    expected_parent_state = lock["frozen_r2_parent"]["state_dict_sha256"]
    if parent_state != expected_parent_state:
        raise ValueError("embedded frozen R2 parent state mismatch")

    training = lock["training"]
    benchmark = lock["benchmark"]
    seed = int(training["seed"])
    runtime = _configure_deterministic_runtime(seed)
    families = tuple(str(value) for value in benchmark["families"])
    train_indices = tuple(int(v) for v in benchmark["phase2_training_indices"])
    dev_indices = tuple(int(v) for v in benchmark["phase2_development_indices"])

    phase1_dev = evaluate_r3(
        phase1_model,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=dev_indices,
    )
    print(
        json.dumps(
            {
                "status": "R3_PHASE2_BASELINE_FRESH_UNOPENED",
                "phase1_dev_solved": phase1_dev["solved"],
                "phase1_dev_families": phase1_dev["families"],
                "dev_indices": list(dev_indices),
            },
            sort_keys=True,
        )
    )

    candidates: list[dict[str, Any]] = []
    selected_model = None
    selected_name = None
    selected_dev = None
    selected_training = None
    selected_eligibility = None
    selected_rank = None

    for candidate_index, cfg in enumerate(training["candidates"]):
        name = str(cfg["name"])
        model = copy.deepcopy(phase1_model)
        train_summary = train_r3_policy(
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
        if state_dict_sha256(model.parent.state_dict()) != expected_parent_state:
            raise ValueError(f"candidate {name} mutated frozen R2 parent")

        dev = evaluate_r3(
            model,
            make_task=make_r18_task,
            families=families,
            split="dev",
            indices=dev_indices,
        )
        eligibility = _eligibility(phase1_dev, dev)
        rank = _rank(dev, name)
        candidates.append(
            {
                "name": name,
                "training": train_summary,
                "development": _compact(dev),
                "eligibility": eligibility,
                "rank": list(rank),
            }
        )
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

    lock_sha = _sha256_file(args.lock)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    if selected_model is None:
        payload = {
            "schema_version": 1,
            "status": "R3_PHASE2_NO_ELIGIBLE_CANDIDATE_FRESH_UNOPENED",
            "phase1_checkpoint_sha256": phase1_authority["checkpoint_sha256"],
            "phase1_state_dict_sha256": phase1_authority["state_dict_sha256"],
            "phase2_lock_sha256": lock_sha,
            "runtime": runtime,
            "phase1_development": _compact(phase1_dev),
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
                    "phase1": phase1_dev,
                    "candidates": candidates,
                    "fresh_opened": False,
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": payload["status"], "fresh_opened": False}))
        return 2

    training_summary = {
        "selected_candidate": selected_name,
        "selected_rank": list(selected_rank),
        "selected_eligibility": selected_eligibility,
        "selected_training": selected_training,
        "phase1_authority": phase1_authority,
        "phase1_development": _compact(phase1_dev),
        "candidate_tournament": candidates,
        "runtime": runtime,
        "fresh_opened": False,
    }
    metadata = save_r3_checkpoint(
        selected_model,
        args.checkpoint,
        parent_checkpoint_sha256=lock["frozen_r2_parent"]["checkpoint_sha256"],
        parent_state_dict_sha256=expected_parent_state,
        predev_lock_sha256=lock_sha,
        training_summary=training_summary,
    )
    manifest = {
        **metadata,
        "schema_version": 1,
        "status": "R3_PHASE2_DEV_ELIGIBLE_FRESH_UNOPENED",
        "selected_candidate": selected_name,
        "selected_rank": list(selected_rank),
        "selected_eligibility": selected_eligibility,
        "phase1_development": _compact(phase1_dev),
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
                "phase1_dev_solved": phase1_dev["solved"],
                "selected_dev_solved": selected_dev["solved"],
                "selected_dev_families": selected_dev["families"],
                "parameters": metadata["parameters"],
                "successor_parameters": metadata["successor_parameters"],
                "checkpoint_sha256": metadata["checkpoint_sha256"],
                "state_dict_sha256": metadata["state_dict_sha256"],
                "fresh_opened": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
