from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
import sys
from typing import Any, Mapping

import torch

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
MODEL_ROOT = HERE.parents[2]
R11_ROOT = MODEL_ROOT / "neural-vnext-native-r11"
R9_ROOT = MODEL_ROOT / "neural-vnext-native-r9"
R4_ROOT = MODEL_ROOT / "neural-vnext-native-r4"
R3_ROOT = MODEL_ROOT / "neural-vnext-native-r3"
R2_ROOT = MODEL_ROOT / "neural-vnext-native-r2"
NATIVE_ROOT = MODEL_ROOT / "neural-vnext-native"
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (ROOT, R11_ROOT, R9_ROOT, R4_ROOT, R3_ROOT, R2_ROOT, NATIVE_ROOT, R18_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from cogcoder.r18_benchmark import make_r18_task
from latent_goal_training import load_r4_checkpoint
from causal_runtime import evaluate_r11
from sequential_evidence_core import NativeR24SequentialEvidenceEnsemble
from sequential_evidence_training import (
    calibrate_temperature,
    collect_evidence_episodes,
    evaluate_r24,
    fit_action_guard,
    save_checkpoint,
    train_evidence_ensemble,
)


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _configure(seed: int) -> dict[str, Any]:
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
        "num_threads": int(torch.get_num_threads()),
    }


def _compact(result: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "rows"}


def _family_solved(result: Mapping[str, Any]) -> dict[str, int]:
    return {
        str(family): int(values["solved"])
        for family, values in result["families"].items()
    }


def _eligibility(
    parent: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    parent_families = _family_solved(parent)
    candidate_families = _family_solved(candidate)
    visible = ("conditional_regimes", "regime_switch", "causal_prerequisites")
    visible_exact = all(
        candidate_families[family] == parent_families[family]
        for family in visible
    )
    implicit_delta = (
        candidate_families["implicit_goal_regimes"]
        - parent_families["implicit_goal_regimes"]
    )
    total_delta = int(candidate["solved"]) - int(parent["solved"])
    return {
        "eligible": bool(visible_exact and implicit_delta > 0 and total_delta > 0),
        "visible_target_families_exact": visible_exact,
        "implicit_goal_delta_vs_parent": implicit_delta,
        "total_solved_delta_vs_parent": total_delta,
        "family_solved_delta_vs_parent": {
            family: candidate_families[family] - parent_families[family]
            for family in parent_families
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=ROOT / "PREDEV_LOCK.json")
    parser.add_argument(
        "--parent-checkpoint",
        type=Path,
        default=R4_ROOT / "accepted" / "r4.pt",
    )
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dev-result", required=True, type=Path)
    args = parser.parse_args()

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("candidate") != "Neural-vNext-Native-R24-SequentialEvidenceFilter":
        raise ValueError("unexpected R24 candidate")
    if (
        lock["fresh_isolation"]["status"] != "UNOPENED"
        or lock["benchmark"]["fresh_indices"] != [280, 319]
    ):
        raise ValueError("R24 fresh isolation changed")

    training = lock["training"]
    architecture = lock["architecture"]
    benchmark = lock["benchmark"]
    runtime = _configure(int(training["seed"]))

    parent, parent_metadata = load_r4_checkpoint(args.parent_checkpoint)
    if (
        parent_metadata["checkpoint_sha256"]
        != lock["learned_parent"]["checkpoint_sha256"]
        or parent_metadata["state_dict_sha256"]
        != lock["learned_parent"]["state_dict_sha256"]
    ):
        raise ValueError("accepted R4 authority mismatch")
    for parameter in parent.parameters():
        parameter.requires_grad_(False)
    parent.eval()

    families = tuple(str(value) for value in benchmark["families"])
    dev_indices = tuple(int(value) for value in benchmark["development_indices"])
    parent_dev = evaluate_r11(
        parent,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=dev_indices,
        horizon=1,
    )
    print(
        json.dumps(
            {
                "status": "R24_R11_BASELINE_FRESH_UNOPENED",
                "parent_dev_solved": parent_dev["solved"],
                "parent_dev_families": parent_dev["families"],
                "dev_indices": list(dev_indices),
            },
            sort_keys=True,
        )
    )

    ensemble_size = int(architecture["ensemble_size"])
    train_episodes = collect_evidence_episodes(
        parent,
        make_task=make_r18_task,
        indices=tuple(benchmark["hidden_training_indices"]),
        ensemble_size=ensemble_size,
    )
    fit_episodes = collect_evidence_episodes(
        parent,
        make_task=make_r18_task,
        indices=tuple(benchmark["temperature_fit_indices"]),
        ensemble_size=ensemble_size,
    )

    torch.manual_seed(int(training["seed"]))
    model = NativeR24SequentialEvidenceEnsemble(
        ensemble_size=ensemble_size,
        hidden_dim=int(architecture["hidden_dim"]),
    )
    if model.parameter_count() != int(architecture["expected_successor_parameters"]):
        raise AssertionError("R24 parameter count changed after preregistration")

    train_summary = train_evidence_ensemble(
        model,
        train_episodes,
        seed=int(training["seed"]),
        epochs=int(training["epochs"]),
        learning_rate=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
    )
    temperature_calibration = calibrate_temperature(
        model,
        fit_episodes,
        candidates=[
            float(value) for value in training["temperature_candidates"]
        ],
    )
    temperature = float(temperature_calibration["selected_temperature"])

    action_guard = fit_action_guard(
        parent,
        model,
        make_task=make_r18_task,
        indices=tuple(benchmark["action_guard_validation_indices"]),
        temperature=temperature,
        thresholds=[
            float(value)
            for value in training["confidence_threshold_candidates"]
        ],
        max_support=int(training["max_support"]),
        minimum_evidence_steps=int(training["minimum_evidence_steps"]),
        minimum_precision=float(training["minimum_override_precision"]),
        minimum_override_rows=int(training["minimum_override_rows"]),
    )
    threshold = (
        None
        if not action_guard["enabled"]
        else float(action_guard["selected"]["threshold"])
    )

    candidate = evaluate_r24(
        parent,
        model,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=dev_indices,
        temperature=temperature,
        threshold=threshold,
        max_support=int(training["max_support"]),
        minimum_evidence_steps=int(training["minimum_evidence_steps"]),
        max_overrides_per_episode=int(training["max_overrides_per_episode"]),
    )
    eligibility = _eligibility(parent_dev, candidate)

    metadata = save_checkpoint(
        model,
        args.checkpoint,
        parent_checkpoint_sha256=parent_metadata["checkpoint_sha256"],
        parent_state_dict_sha256=parent_metadata["state_dict_sha256"],
        r11_authority_blob_sha=lock["accepted_r11_parent"][
            "accepted_authority_blob_sha"
        ],
        predev_lock_sha256=_sha256_file(args.lock),
        training_summary=train_summary,
        temperature_calibration=temperature_calibration,
        action_guard=action_guard,
    )

    status = (
        "R24_DEV_ELIGIBLE_CONFIRMATION_UNOPENED_FRESH_UNOPENED"
        if eligibility["eligible"]
        else "R24_DEV_REJECTED_CONFIRMATION_FRESH_UNOPENED"
    )
    selected_config = {
        "temperature": temperature,
        "guard_enabled": bool(action_guard["enabled"]),
        "threshold": threshold,
        "max_support": int(training["max_support"]),
        "minimum_evidence_steps": int(training["minimum_evidence_steps"]),
        "max_overrides_per_episode": int(training["max_overrides_per_episode"]),
    }
    manifest = {
        **metadata,
        "schema_version": 1,
        "status": status,
        "runtime": runtime,
        "private_label_boundary": {
            "private_goal_used_only_on_train_split": True,
            "inference_private_goal_use": False,
            "exact_public_support_hard_mask": True,
        },
        "parent_development": _compact(parent_dev),
        "dev_evaluation": _compact(candidate),
        "selected_candidate": "sequential_evidence_filter",
        "selected_config": selected_config,
        "selected_eligibility": eligibility,
        "confirmation_opened": False,
        "fresh_opened": False,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.dev_result.write_text(
        json.dumps(
            {
                "parent": parent_dev,
                "candidate": candidate,
                "temperature_calibration": temperature_calibration,
                "action_guard": action_guard,
                "selected_config": selected_config,
                "eligibility": eligibility,
                "confirmation_opened": False,
                "fresh_opened": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": status,
                "parent_dev_solved": parent_dev["solved"],
                "candidate_dev_solved": candidate["solved"],
                "candidate_dev_families": candidate["families"],
                "eligibility": eligibility,
                "selected_config": selected_config,
                "action_guard": action_guard,
                "successor_parameters": metadata["successor_parameters"],
                "physical_parameters": metadata["physical_parameters"],
                "checkpoint_sha256": metadata["checkpoint_sha256"],
                "state_dict_sha256": metadata["state_dict_sha256"],
                "confirmation_opened": False,
                "fresh_opened": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
