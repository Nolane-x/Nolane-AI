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


def _family_solved(result: Mapping[str, Any]) -> dict[str, int]:
    return {
        str(family): int(row["solved"])
        for family, row in result["families"].items()
    }


def _find_candidate(training: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    for candidate in training["candidate_curricula"]:
        if str(candidate["name"]) == str(name):
            return candidate
    raise ValueError(f"phase-1 replay candidate {name!r} missing from lock")


def _assert_phase1_replay(
    lock: Mapping[str, Any],
    replay: Mapping[str, Any],
) -> None:
    expected = lock["training"]["phase1_replay"]
    if list(replay["indices"]) != list(expected["expected_dev_block"]):
        raise ValueError("phase-1 replay dev block mismatch")
    if int(replay["solved"]) != int(expected["expected_total_solved"]):
        raise RuntimeError(
            "phase-1 replay total mismatch: "
            f"expected {expected['expected_total_solved']}, got {replay['solved']}"
        )
    actual_families = _family_solved(replay)
    expected_families = {
        str(key): int(value)
        for key, value in expected["expected_family_solved"].items()
    }
    if actual_families != expected_families:
        raise RuntimeError(
            "phase-1 replay family mismatch: "
            f"expected {expected_families}, got {actual_families}"
        )


def _phase2_eligibility(
    phase1: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    phase1_families = _family_solved(phase1)
    candidate_families = _family_solved(candidate)
    total_improved = int(candidate["solved"]) > int(phase1["solved"])
    implicit_improved = (
        candidate_families["implicit_goal_regimes"]
        > phase1_families["implicit_goal_regimes"]
    )
    visible_exact = all(
        candidate_families[family] == phase1_families[family]
        for family in ("conditional_regimes", "causal_prerequisites")
    )
    regime_non_regression = (
        candidate_families["regime_switch"]
        >= phase1_families["regime_switch"]
    )
    deltas = {
        family: candidate_families[family] - phase1_families[family]
        for family in phase1_families
    }
    eligible = bool(
        total_improved
        and implicit_improved
        and visible_exact
        and regime_non_regression
    )
    return {
        "eligible": eligible,
        "total_improved": total_improved,
        "implicit_goal_improved": implicit_improved,
        "visible_target_families_exact": visible_exact,
        "regime_switch_non_regression": regime_non_regression,
        "family_solved_delta_vs_phase1": deltas,
    }


def _phase2_rank(
    result: Mapping[str, Any],
    name: str,
) -> tuple[int, int, int, str]:
    return (
        int(result["solved"]),
        int(result["families"]["implicit_goal_regimes"]["solved"]),
        -int(result["steps"]),
        str(name),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Train Neural vNext Native R2 phase 2. Reproduce the frozen accepted "
            "parent and phase-1 general transition residual, then train only a "
            "hard-gated hidden-target residual. Fresh remains forbidden."
        )
    )
    parser.add_argument("--lock", type=Path, default=ROOT / "PREDEV_LOCK.json")
    parser.add_argument("--parent-checkpoint", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dev-result", required=True, type=Path)
    args = parser.parse_args()

    lock = load_lock(args.lock)
    if int(lock.get("schema_version", -1)) != 2:
        raise ValueError("R2 phase-2 trainer requires PREDEV schema version 2")
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
    phase1_train_indices = tuple(
        int(value) for value in benchmark["successor_training_indices"]
    )
    phase1_dev_indices = tuple(
        int(value) for value in benchmark["phase1_development_indices"]
    )
    phase2_dev_indices = tuple(
        int(value) for value in benchmark["phase2_development_indices"]
    )
    hidden_train_indices = tuple(
        int(value) for value in benchmark["hidden_specialist_training_indices"]
    )

    parent_phase1_dev = evaluate_policy(
        parent,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=phase1_dev_indices,
    )
    parent_phase2_dev = evaluate_policy(
        parent,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=phase2_dev_indices,
    )

    phase1_cfg = _find_candidate(
        training,
        str(training["phase1_replay"]["selected_candidate"]),
    )
    torch.manual_seed(seed)
    phase1_model = NativeR2TransitionPolicy(
        copy.deepcopy(parent),
        trace_token_dim=int(architecture["transition_token_dim"]),
        trace_hidden_dim=int(architecture["trace_hidden_dim"]),
        trace_length=int(architecture["transition_trace_length"]),
    )
    if state_dict_sha256(phase1_model.parent.state_dict()) != actual_parent_state:
        raise ValueError("phase-1 construction changed frozen parent")

    phase1_training = train_successor_policy(
        phase1_model,
        make_task=make_r18_task,
        oracle_plan=oracle_plan,
        families=families,
        train_indices=phase1_train_indices,
        seed=seed,
        expert_epochs=int(phase1_cfg["expert_epochs"]),
        dagger_teacher_mix=[
            float(value) for value in phase1_cfg["dagger_teacher_mix"]
        ],
        learning_rate=float(phase1_cfg["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
        max_grad_norm=float(training["max_grad_norm"]),
        residual_l2_weight=float(phase1_cfg["residual_l2_weight"]),
        training_scope="general",
    )
    if state_dict_sha256(phase1_model.parent.state_dict()) != actual_parent_state:
        raise ValueError("phase-1 training mutated frozen parent")

    phase1_replay = evaluate_successor(
        phase1_model,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=phase1_dev_indices,
    )
    _assert_phase1_replay(lock, phase1_replay)

    phase1_phase2_dev = evaluate_successor(
        phase1_model,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=phase2_dev_indices,
    )
    print(
        json.dumps(
            {
                "status": "R2_PHASE1_REPLAY_VERIFIED_FRESH_UNOPENED",
                "phase1_block_solved": phase1_replay["solved"],
                "phase2_block_solved": phase1_phase2_dev["solved"],
                "phase2_families": phase1_phase2_dev["families"],
                "parent_phase2_solved": parent_phase2_dev["solved"],
            },
            sort_keys=True,
        )
    )

    phase1_state = copy.deepcopy(phase1_model.state_dict())
    candidates: list[dict[str, Any]] = []
    selected_model: NativeR2TransitionPolicy | None = None
    selected_name: str | None = None
    selected_dev: dict[str, Any] | None = None
    selected_training: dict[str, Any] | None = None
    selected_eligibility: dict[str, Any] | None = None
    selected_rank: tuple[int, int, int, str] | None = None

    for hidden_cfg in training["hidden_specialists"]:
        name = str(hidden_cfg["name"])
        model = copy.deepcopy(phase1_model)
        if model.state_dict().keys() != phase1_state.keys():
            raise ValueError("phase-2 candidate state topology drifted")
        train_summary = train_successor_policy(
            model,
            make_task=make_r18_task,
            oracle_plan=oracle_plan,
            families=("implicit_goal_regimes",),
            train_indices=hidden_train_indices,
            seed=seed,
            expert_epochs=int(hidden_cfg["expert_epochs"]),
            dagger_teacher_mix=[
                float(value) for value in hidden_cfg["dagger_teacher_mix"]
            ],
            learning_rate=float(hidden_cfg["learning_rate"]),
            weight_decay=float(training["weight_decay"]),
            max_grad_norm=float(training["max_grad_norm"]),
            residual_l2_weight=float(hidden_cfg["residual_l2_weight"]),
            training_scope="hidden_target",
        )
        if state_dict_sha256(model.parent.state_dict()) != actual_parent_state:
            raise ValueError(f"candidate {name} mutated frozen parent")

        dev = evaluate_successor(
            model,
            make_task=make_r18_task,
            families=families,
            split="dev",
            indices=phase2_dev_indices,
        )
        eligibility = _phase2_eligibility(phase1_phase2_dev, dev)
        rank = _phase2_rank(dev, name)
        row = {
            "name": name,
            "rank": list(rank[:-1]),
            "eligibility": eligibility,
            "development": _compact(dev),
            "training": train_summary,
        }
        candidates.append(row)
        print(
            json.dumps(
                {
                    "status": "R2_PHASE2_CANDIDATE_COMPLETE_FRESH_UNOPENED",
                    "candidate": name,
                    "phase1_dev_solved": phase1_phase2_dev["solved"],
                    "candidate_dev_solved": dev["solved"],
                    "eligibility": eligibility,
                    "families": dev["families"],
                    "successor_parameters": model.successor_parameter_count(),
                    "full_parameters": model.full_parameter_count(),
                },
                sort_keys=True,
            )
        )

        if not eligibility["eligible"]:
            continue
        better = selected_rank is None or rank[:-1] > selected_rank[:-1]
        lexical = (
            selected_rank is not None
            and rank[:-1] == selected_rank[:-1]
            and name < selected_rank[-1]
        )
        if better or lexical:
            selected_model = model
            selected_name = name
            selected_dev = dev
            selected_training = train_summary
            selected_eligibility = eligibility
            selected_rank = rank

    if selected_model is None:
        best = max(
            candidates,
            key=lambda row: (
                int(row["development"]["solved"]),
                int(
                    row["development"]["families"]["implicit_goal_regimes"]["solved"]
                ),
                -int(row["development"]["steps"]),
                str(row["name"]),
            ),
        )
        raise RuntimeError(
            "no phase-2 hidden-target candidate satisfied preregistered gate; "
            f"best observed={best['name']} solved={best['development']['solved']}"
        )

    training_summary = {
        "seed": seed,
        "deterministic_runtime": runtime,
        "parent_phase1_dev": _compact(parent_phase1_dev),
        "parent_phase2_dev": _compact(parent_phase2_dev),
        "phase1_candidate": str(phase1_cfg["name"]),
        "phase1_training": phase1_training,
        "phase1_replay_dev": _compact(phase1_replay),
        "phase1_on_phase2_dev": _compact(phase1_phase2_dev),
        "selected_candidate": selected_name,
        "selected_rank": list(selected_rank[:-1]),
        "selected_eligibility": selected_eligibility,
        "selected_training": selected_training,
        "phase2_tournament": candidates,
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
    manifest["selected_rank"] = list(selected_rank[:-1])
    manifest["selected_eligibility"] = selected_eligibility
    manifest["parent_phase2_dev_evaluation"] = _compact(parent_phase2_dev)
    manifest["phase1_phase2_dev_evaluation"] = _compact(phase1_phase2_dev)
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
                "status": "R2_PHASE2_TOURNAMENT_COMPLETE_FRESH_UNOPENED",
                "selected_candidate": selected_name,
                "selected_rank": list(selected_rank[:-1]),
                "selected_eligibility": selected_eligibility,
                "parent_phase2_dev_solved": parent_phase2_dev["solved"],
                "phase1_phase2_dev_solved": phase1_phase2_dev["solved"],
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
