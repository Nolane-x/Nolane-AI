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

from cogcoder.r18_benchmark import make_r18_task, oracle_plan
from latent_goal_training import load_r4_checkpoint
from causal_runtime import evaluate_r11
from advantage_core import NativeR20AdvantageConsensus
from advantage_training import (
    calibrate_threshold,
    evaluate_r20,
    save_checkpoint,
    train_policy,
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
    return {k: v for k, v in result.items() if k != "rows"}


def _family_solved(result: Mapping[str, Any]) -> dict[str, int]:
    return {str(f): int(v["solved"]) for f, v in result["families"].items()}


def _eligibility(parent: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    pf = _family_solved(parent)
    cf = _family_solved(candidate)
    visible = ("conditional_regimes", "regime_switch", "causal_prerequisites")
    visible_exact = all(cf[f] == pf[f] for f in visible)
    implicit = cf["implicit_goal_regimes"] - pf["implicit_goal_regimes"]
    total = int(candidate["solved"]) - int(parent["solved"])
    return {
        "eligible": bool(visible_exact and implicit > 0 and total > 0),
        "visible_target_families_exact": visible_exact,
        "implicit_goal_delta_vs_parent": implicit,
        "total_solved_delta_vs_parent": total,
        "family_solved_delta_vs_parent": {f: cf[f] - pf[f] for f in pf},
    }


def _rank(candidate: Mapping[str, Any], name: str) -> tuple[int, int, int, int, str]:
    return (
        int(candidate["families"]["implicit_goal_regimes"]["solved"]),
        int(candidate["solved"]),
        -int(candidate["overrides_vs_r11"]),
        -int(candidate["steps"]),
        str(name),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=ROOT / "PREDEV_LOCK.json")
    parser.add_argument("--parent-checkpoint", type=Path, default=R4_ROOT / "accepted" / "r4.pt")
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dev-result", required=True, type=Path)
    args = parser.parse_args()

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("schema_version") != 1:
        raise ValueError("unsupported R20 lock")
    if lock.get("candidate") != "Neural-vNext-Native-R20-AdvantageConsensus":
        raise ValueError("unexpected R20 candidate")
    if lock["fresh_isolation"]["status"] != "UNOPENED":
        raise ValueError("R20 fresh must be unopened")
    if lock["benchmark"]["fresh_indices"] != [280, 319]:
        raise ValueError("R20 must reserve fresh:280..319")

    training = lock["training"]
    benchmark = lock["benchmark"]
    runtime = _configure(int(training["seed"]))

    parent, parent_metadata = load_r4_checkpoint(args.parent_checkpoint)
    if parent_metadata["checkpoint_sha256"] != lock["learned_parent"]["checkpoint_sha256"]:
        raise ValueError("accepted R4 checkpoint mismatch")
    if parent_metadata["state_dict_sha256"] != lock["learned_parent"]["state_dict_sha256"]:
        raise ValueError("accepted R4 state mismatch")
    for parameter in parent.parameters():
        parameter.requires_grad_(False)
    parent.eval()

    families = tuple(str(v) for v in benchmark["families"])
    dev_indices = tuple(int(v) for v in benchmark["development_indices"])
    train_indices = tuple(int(v) for v in benchmark["hidden_training_indices"])
    calibration_indices = tuple(int(v) for v in benchmark["calibration_indices"])

    parent_dev = evaluate_r11(
        parent,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=dev_indices,
        horizon=1,
    )
    print(json.dumps({
        "status": "R20_R11_BASELINE_FRESH_UNOPENED",
        "parent_dev_solved": parent_dev["solved"],
        "parent_dev_families": parent_dev["families"],
        "dev_indices": list(dev_indices),
    }, sort_keys=True))

    torch.manual_seed(int(training["seed"]))
    model = NativeR20AdvantageConsensus(
        parent,
        ensemble_size=int(training["ensemble_size"]),
        posterior_embedding_dim=int(training["posterior_embedding_dim"]),
        hidden_dim=int(training["hidden_dim"]),
    )
    summary = train_policy(
        model,
        make_task=make_r18_task,
        oracle_plan=oracle_plan,
        indices=train_indices,
        seed=int(training["seed"]),
        learning_rate=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
        pairwise_weight=float(training["pairwise_weight"]),
        max_grad_norm=float(training["max_grad_norm"]),
    )

    candidates = []
    selected = None
    calibrations = {}
    for cfg in training["candidate_configs"]:
        name = str(cfg["name"])
        calibration = calibrate_threshold(
            model,
            make_task=make_r18_task,
            oracle_plan=oracle_plan,
            indices=calibration_indices,
            max_support=int(cfg["max_support"]),
            minimum_precision=float(training["minimum_calibration_precision"]),
            minimum_count=int(training["minimum_calibration_count"]),
        )
        calibrations[name] = calibration
        threshold = calibration["threshold"]
        dev = evaluate_r20(
            model,
            make_task=make_r18_task,
            families=families,
            split="dev",
            indices=dev_indices,
            max_support=int(cfg["max_support"]),
            threshold=None if threshold is None else float(threshold),
        )
        eligibility = _eligibility(parent_dev, dev)
        rank = _rank(dev, name)
        row = {
            "name": name,
            "max_support": int(cfg["max_support"]),
            "calibration": calibration,
            "development": _compact(dev),
            "eligibility": eligibility,
            "rank": list(rank),
        }
        candidates.append(row)
        print(json.dumps({
            "candidate": name,
            "max_support": int(cfg["max_support"]),
            "calibration": calibration,
            "dev_solved": dev["solved"],
            "dev_families": dev["families"],
            "overrides_vs_r11": dev["overrides_vs_r11"],
            "eligibility": eligibility,
            "rank": list(rank),
            "fresh_opened": False,
        }, sort_keys=True))
        if eligibility["eligible"] and (selected is None or rank > selected["rank"]):
            selected = {
                "name": name,
                "max_support": int(cfg["max_support"]),
                "threshold": threshold,
                "dev": dev,
                "eligibility": eligibility,
                "rank": rank,
            }

    predev_sha = _sha256_file(args.lock)
    metadata = save_checkpoint(
        model,
        args.checkpoint,
        parent_checkpoint_sha256=parent_metadata["checkpoint_sha256"],
        parent_state_dict_sha256=parent_metadata["state_dict_sha256"],
        r11_authority_blob_sha=lock["accepted_r11_parent"]["accepted_authority_blob_sha"],
        predev_lock_sha256=predev_sha,
        training_summary=summary,
        calibrations=calibrations,
    )

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    status = "R20_DEV_ELIGIBLE_FRESH_UNOPENED" if selected is not None else "R20_DEV_REJECTED_FRESH_UNOPENED"
    manifest = {
        **metadata,
        "schema_version": 1,
        "status": status,
        "runtime": runtime,
        "parent_development": _compact(parent_dev),
        "candidate_tournament": candidates,
        "selected_candidate": None if selected is None else selected["name"],
        "selected_config": None if selected is None else {
            "max_support": selected["max_support"],
            "threshold": selected["threshold"],
        },
        "selected_eligibility": None if selected is None else selected["eligibility"],
        "dev_evaluation": None if selected is None else _compact(selected["dev"]),
        "fresh_opened": False,
    }
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.dev_result.write_text(json.dumps({
        "parent": parent_dev,
        "candidates": candidates,
        "selected": None if selected is None else {
            "name": selected["name"],
            "max_support": selected["max_support"],
            "threshold": selected["threshold"],
            "eligibility": selected["eligibility"],
            "development": selected["dev"],
        },
        "fresh_opened": False,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": status,
        "selected_candidate": None if selected is None else selected["name"],
        "parent_dev_solved": parent_dev["solved"],
        "selected_dev_solved": None if selected is None else selected["dev"]["solved"],
        "selected_dev_families": None if selected is None else selected["dev"]["families"],
        "parameters": metadata["parameters"],
        "successor_parameters": metadata["successor_parameters"],
        "checkpoint_sha256": metadata["checkpoint_sha256"],
        "successor_state_dict_sha256": metadata["successor_state_dict_sha256"],
        "fresh_opened": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
