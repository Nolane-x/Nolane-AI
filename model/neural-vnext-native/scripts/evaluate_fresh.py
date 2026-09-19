from __future__ import annotations

import argparse
from hashlib import sha1, sha256
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
REPO_ROOT = HERE.parents[3]
MODEL_ROOT = HERE.parents[2]
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from cogcoder.r18_benchmark import make_r18_task  # noqa: E402
from native_training import evaluate_policy, load_checkpoint  # noqa: E402


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return sha1(header + payload).hexdigest()


def load_fresh_lock(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported PRE_FRESH_LOCK schema")
    if payload.get("status") != "FROZEN_FRESH_UNOPENED":
        raise ValueError("fresh court requires FROZEN_FRESH_UNOPENED lock status")
    court = payload.get("fresh_court")
    if not isinstance(court, dict) or court.get("opened") is not False:
        raise ValueError("fresh court lock must state opened=false")
    return payload


def verify_source_blobs(lock: Mapping[str, Any], repo_root: Path) -> None:
    rows = lock.get("frozen_source_git_blobs")
    if not isinstance(rows, dict) or not rows:
        raise ValueError("PRE_FRESH_LOCK is missing frozen source blob identities")
    for relative, expected in rows.items():
        path = repo_root / str(relative)
        if not path.is_file():
            raise ValueError(f"frozen source file missing: {relative}")
        actual = git_blob_sha(path)
        if actual != str(expected):
            raise ValueError(
                f"frozen source blob mismatch for {relative}: expected {expected}, got {actual}"
            )


def verify_checkpoint(lock: Mapping[str, Any], checkpoint: Path) -> tuple[Any, dict[str, Any]]:
    model, metadata = load_checkpoint(checkpoint)
    frozen = lock.get("frozen_candidate")
    if not isinstance(frozen, dict):
        raise ValueError("PRE_FRESH_LOCK is missing frozen_candidate")
    expected = {
        "checkpoint_sha256": str(frozen["checkpoint_sha256"]),
        "state_dict_sha256": str(frozen["state_dict_sha256"]),
        "predev_lock_sha256": str(frozen["predev_lock_sha256"]),
        "parameters": int(frozen["parameters"]),
    }
    actual = {
        "checkpoint_sha256": str(metadata["checkpoint_sha256"]),
        "state_dict_sha256": str(metadata["state_dict_sha256"]),
        "predev_lock_sha256": str(metadata["predev_lock_sha256"]),
        "parameters": int(metadata["parameters"]),
    }
    if actual != expected:
        raise ValueError(f"frozen checkpoint authority mismatch: expected {expected}, got {actual}")
    summary = metadata.get("training_summary")
    if not isinstance(summary, dict):
        raise ValueError("checkpoint training_summary is unavailable")
    if summary.get("selected_candidate") != frozen.get("selected_candidate"):
        raise ValueError("selected candidate mismatch")
    if summary.get("fresh_opened") is not False:
        raise ValueError("checkpoint metadata must attest fresh_opened=false")
    return model, metadata


def expected_identities(lock: Mapping[str, Any]) -> set[tuple[str, int]]:
    court = lock["fresh_court"]
    families = tuple(str(value) for value in court["families"])
    start = int(court["index_start"])
    end = int(court["index_end"])
    if start < 0 or end < start:
        raise ValueError("invalid fresh index range")
    return {
        (family, index)
        for family in families
        for index in range(start, end + 1)
    }


def verify_court_rows(lock: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> None:
    expected = expected_identities(lock)
    observed: list[tuple[str, int]] = []
    for row in rows:
        if row.get("split") != "fresh":
            raise ValueError("fresh court contains a non-fresh row")
        observed.append((str(row["family"]), int(row["index"])))
    if len(observed) != len(set(observed)):
        raise ValueError("fresh court contains duplicate identities")
    if set(observed) != expected:
        missing = sorted(expected - set(observed))
        extra = sorted(set(observed) - expected)
        raise ValueError(f"fresh identity mismatch: missing={missing}, extra={extra}")
    expected_count = int(lock["fresh_court"]["episodes_expected"])
    if len(observed) != expected_count:
        raise ValueError(
            f"fresh episode count mismatch: expected {expected_count}, got {len(observed)}"
        )


def promotion_gate(lock: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    gate = lock["promotion_gate"]
    minimum_total = int(gate["minimum_total_solved"])
    minimum_rate = float(gate["minimum_total_solve_rate"])
    minimum_family = int(gate["minimum_solved_per_family"])
    total_ok = int(result["solved"]) >= minimum_total
    rate_ok = float(result["solve_rate"]) >= minimum_rate
    family_results = {
        str(family): int(row["solved"]) >= minimum_family
        for family, row in result["families"].items()
    }
    family_ok = all(family_results.values())
    accepted = bool(total_ok and rate_ok and family_ok)
    return {
        "accepted": accepted,
        "minimum_total_solved": minimum_total,
        "actual_total_solved": int(result["solved"]),
        "total_solved_pass": total_ok,
        "minimum_total_solve_rate": minimum_rate,
        "actual_total_solve_rate": float(result["solve_rate"]),
        "total_solve_rate_pass": rate_ok,
        "minimum_solved_per_family": minimum_family,
        "family_pass": family_results,
        "all_families_pass": family_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open the frozen Neural vNext Native fresh court exactly once."
    )
    parser.add_argument("--lock", type=Path, default=ROOT / "PRE_FRESH_LOCK.json")
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()

    lock = load_fresh_lock(args.lock)
    verify_source_blobs(lock, REPO_ROOT)
    model, metadata = verify_checkpoint(lock, args.checkpoint)

    court = lock["fresh_court"]
    families = tuple(str(value) for value in court["families"])
    indices = (int(court["index_start"]), int(court["index_end"]))

    fresh = evaluate_policy(
        model,
        make_task=make_r18_task,
        families=families,
        split="fresh",
        indices=indices,
    )
    verify_court_rows(lock, fresh["rows"])
    gate = promotion_gate(lock, fresh)

    payload = {
        "schema_version": 1,
        "status": "FRESH_ACCEPTED" if gate["accepted"] else "FRESH_REJECTED",
        "pre_fresh_lock_sha256": _sha256_file(args.lock),
        "freeze_source_head": lock["freeze_source_head"],
        "checkpoint_sha256": metadata["checkpoint_sha256"],
        "state_dict_sha256": metadata["state_dict_sha256"],
        "parameters": metadata["parameters"],
        "selected_candidate": metadata["training_summary"]["selected_candidate"],
        "fresh": fresh,
        "promotion_gate": gate,
        "post_fresh_tuning_allowed": False,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "solved": fresh["solved"],
                "episodes": fresh["episodes"],
                "solve_rate": fresh["solve_rate"],
                "families": fresh["families"],
                "checkpoint_sha256": metadata["checkpoint_sha256"],
                "state_dict_sha256": metadata["state_dict_sha256"],
                "promotion_gate": gate,
            },
            sort_keys=True,
        )
    )
    return 0 if gate["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
