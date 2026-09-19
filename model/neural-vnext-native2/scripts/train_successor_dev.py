from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
MODEL_ROOT = HERE.parents[2]
PARENT_ROOT = MODEL_ROOT / "neural-vnext-native"
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (ROOT, PARENT_ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from successor_training import (  # noqa: E402
    reproduce_accepted_parent,
    save_successor_checkpoint,
    sha256_file,
    train_successor_candidate,
)


def _rank(dev: Mapping[str, Any]) -> tuple[int, int, int]:
    families = dev["families"]
    solved = int(dev["solved"])
    worst = min(int(row["solved"]) for row in families.values())
    steps = int(dev["steps"])
    return solved, worst, -steps


def _compact(dev: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in dev.items() if key != "rows"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reproduce the accepted Neural vNext Native parent, freeze it, "
            "train preregistered Native-2 residual candidates on train only, "
            "and select by dev only. Fresh is forbidden."
        )
    )
    parser.add_argument("--lock", type=Path, default=ROOT / "PREDEV_LOCK.json")
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dev-result", required=True, type=Path)
    args = parser.parse_args()

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("schema_version") != 1:
        raise ValueError("unsupported Native-2 PREDEV lock")
    if lock["fresh_isolation"]["status"] != "UNOPENED":
        raise ValueError("Native-2 dev trainer requires fresh UNOPENED")
    if lock["fresh_isolation"]["reserved_successor_fresh_indices"] != [40, 79]:
        raise ValueError("Native-2 must reserve untouched fresh 40..79")
    if lock["training"]["parent_hash_must_match_before_successor_training"] is not True:
        raise ValueError("parent reproduction hash gate must be enabled")

    parent, parent_report = reproduce_accepted_parent()
    expected_parent = str(lock["parent"]["state_dict_sha256"])
    if parent_report["parent_state_dict_sha256"] != expected_parent:
        raise ValueError("Native-2 parent authority mismatch")

    parent_state = {
        name: tensor.detach().cpu().clone()
        for name, tensor in parent.state_dict().items()
    }
    parent_dev = parent_report["parent_dev"]
    parent_rank = _rank(parent_dev)

    benchmark = lock["benchmark"]
    families = tuple(str(value) for value in benchmark["families"])
    dev_indices = tuple(int(value) for value in benchmark["development_indices"])
    seed = int(lock["training"]["seed"])
    parent_architecture = json.loads(
        (PARENT_ROOT / "PREDEV_LOCK.json").read_text(encoding="utf-8")
    )["architecture"]

    tournament: list[dict[str, Any]] = []
    best_model = None
    best_name = None
    best_rank = None
    best_dev = None
    best_training = None

    print(
        json.dumps(
            {
                "status": "NATIVE2_PARENT_REPRODUCED_FRESH_UNOPENED",
                "parent_state_dict_sha256": parent_report["parent_state_dict_sha256"],
                "parent_dev_solved": parent_dev["solved"],
                "parent_dev_episodes": parent_dev["episodes"],
                "parent_rank": list(parent_rank),
                "families": parent_dev["families"],
            },
            sort_keys=True,
        )
    )

    for candidate in lock["training"]["residual_candidates"]:
        model, training_report, dev = train_successor_candidate(
            parent_state=parent_state,
            parent_architecture=parent_architecture,
            candidate=candidate,
            benchmark_families=families,
            dev_indices=(dev_indices[0], dev_indices[1]),
            seed=seed,
            weight_decay=float(lock["training"]["weight_decay"]),
            max_grad_norm=float(lock["training"]["max_grad_norm"]),
        )
        rank = _rank(dev)
        row = {
            "name": str(candidate["name"]),
            "rank": list(rank),
            "development": _compact(dev),
            "training": training_report,
            "improves_parent": rank > parent_rank,
        }
        tournament.append(row)
        print(
            json.dumps(
                {
                    "status": "NATIVE2_DEV_CANDIDATE_COMPLETE_FRESH_UNOPENED",
                    "candidate": candidate["name"],
                    "rank": list(rank),
                    "dev_solved": dev["solved"],
                    "dev_episodes": dev["episodes"],
                    "families": dev["families"],
                    "improves_parent": rank > parent_rank,
                    "parameter_counts": training_report["parameters"],
                },
                sort_keys=True,
            )
        )
        if (
            best_rank is None
            or rank > best_rank
            or (rank == best_rank and str(candidate["name"]) < str(best_name))
        ):
            best_model = model
            best_name = str(candidate["name"])
            best_rank = rank
            best_dev = dev
            best_training = training_report

    if best_model is None or best_dev is None or best_rank is None or best_name is None:
        raise RuntimeError("Native-2 tournament produced no candidate")

    improvement = best_rank > parent_rank
    summary = {
        "status": (
            "NATIVE2_DEV_IMPROVED_FRESH_UNOPENED"
            if improvement
            else "NATIVE2_DEV_NO_IMPROVEMENT_FRESH_UNOPENED"
        ),
        "seed": seed,
        "parent": parent_report,
        "parent_rank": list(parent_rank),
        "selected_candidate": best_name,
        "selected_rank": list(best_rank),
        "improves_parent": improvement,
        "selection_rule": lock["training"]["selection_rule"],
        "tournament": tournament,
        "fresh_opened": False,
    }
    manifest = save_successor_checkpoint(
        best_model,
        args.checkpoint,
        lock_sha256=sha256_file(args.lock),
        selected_candidate=best_name,
        training_summary=summary,
        dev_result=best_dev,
        parent_state_dict_sha256=parent_report["parent_state_dict_sha256"],
    )
    manifest["parent_dev"] = _compact(parent_dev)
    manifest["selected_dev"] = _compact(best_dev)
    manifest["improves_parent"] = improvement
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
                "status": summary["status"],
                "selected_candidate": best_name,
                "selected_rank": list(best_rank),
                "parent_rank": list(parent_rank),
                "improves_parent": improvement,
                "checkpoint_sha256": manifest["checkpoint_sha256"],
                "state_dict_sha256": manifest["state_dict_sha256"],
                "parameter_counts": manifest["parameter_counts"],
                "dev_solved": best_dev["solved"],
                "dev_episodes": best_dev["episodes"],
                "dev_solve_rate": best_dev["solve_rate"],
                "families": best_dev["families"],
                "fresh_opened": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
