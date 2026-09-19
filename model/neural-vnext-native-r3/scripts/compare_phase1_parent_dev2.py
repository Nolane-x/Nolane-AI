from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Mapping

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

from cogcoder.r18_benchmark import make_r18_task  # noqa: E402
from successor_training import evaluate_successor as evaluate_r2  # noqa: E402
from attributed_training import evaluate_r3, load_r3_checkpoint  # noqa: E402


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _compact(result: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key != "rows"}


def _family_solved(result: Mapping[str, Any]) -> dict[str, int]:
    return {
        str(family): int(row["solved"])
        for family, row in result["families"].items()
    }


def _identity_set(result: Mapping[str, Any]) -> set[tuple[str, str, int]]:
    rows = result.get("rows")
    if not isinstance(rows, list):
        raise ValueError("evaluation result is missing rows")
    identities: list[tuple[str, str, int]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("evaluation row must be a mapping")
        split = row.get("split")
        family = row.get("family")
        index = row.get("index")
        if split != "dev":
            raise ValueError("secondary comparison may contain only dev rows")
        if not isinstance(family, str) or not family:
            raise ValueError("invalid family identity")
        if type(index) is not int:
            raise ValueError("dev index must be an exact integer")
        identities.append((split, family, index))
    if len(identities) != len(set(identities)):
        raise ValueError("secondary dev comparison contains duplicate identities")
    return set(identities)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the exact frozen R3 Phase-1 candidate and its embedded "
            "accepted R2 parent on the already-opened Phase-2 development block. "
            "This script performs no training and never instantiates fresh tasks."
        )
    )
    parser.add_argument("--phase2-lock", type=Path, default=ROOT / "PHASE2_LOCK.json")
    parser.add_argument("--phase1-checkpoint", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()

    lock = json.loads(args.phase2_lock.read_text(encoding="utf-8"))
    if lock.get("schema_version") != 1:
        raise ValueError("unsupported R3 Phase-2 lock")
    if lock["fresh_isolation"]["status"] != "UNOPENED":
        raise ValueError("R3 fresh court must remain unopened")
    if lock["benchmark"]["fresh_indices"] != [80, 119]:
        raise ValueError("R3 must reserve fresh:80..119")
    if lock["benchmark"]["phase2_development_indices"] != [128, 159]:
        raise ValueError("unexpected secondary development block")

    authority = lock["phase1_authority"]
    actual_checkpoint_sha = _sha256_file(args.phase1_checkpoint)
    if actual_checkpoint_sha != authority["checkpoint_sha256"]:
        raise ValueError("R3 Phase-1 checkpoint hash mismatch")

    model, metadata = load_r3_checkpoint(args.phase1_checkpoint)
    if metadata["state_dict_sha256"] != authority["state_dict_sha256"]:
        raise ValueError("R3 Phase-1 state hash mismatch")
    if metadata["training_summary"]["selected_candidate"] != "attributed_broad":
        raise ValueError("unexpected frozen R3 Phase-1 candidate")
    if metadata["training_summary"]["fresh_opened"] is not False:
        raise ValueError("frozen R3 Phase-1 checkpoint must attest fresh unopened")

    families = tuple(str(v) for v in lock["benchmark"]["families"])
    indices = tuple(int(v) for v in lock["benchmark"]["phase2_development_indices"])

    parent = evaluate_r2(
        model.parent,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=indices,
    )
    candidate = evaluate_r3(
        model,
        make_task=make_r18_task,
        families=families,
        split="dev",
        indices=indices,
    )

    parent_ids = _identity_set(parent)
    candidate_ids = _identity_set(candidate)
    if parent_ids != candidate_ids:
        raise ValueError("R2 parent and R3 candidate were not evaluated on identical dev identities")
    expected_ids = {
        ("dev", family, index)
        for family in families
        for index in range(indices[0], indices[1] + 1)
    }
    if parent_ids != expected_ids:
        raise ValueError("secondary dev identities differ from the exact locked Cartesian product")

    parent_families = _family_solved(parent)
    candidate_families = _family_solved(candidate)
    family_delta = {
        family: candidate_families[family] - parent_families[family]
        for family in parent_families
    }
    visible = ("conditional_regimes", "regime_switch", "causal_prerequisites")
    visible_exact = all(family_delta[family] == 0 for family in visible)
    implicit_delta = family_delta["implicit_goal_regimes"]
    total_delta = int(candidate["solved"]) - int(parent["solved"])
    supports_freeze = bool(visible_exact and implicit_delta > 0 and total_delta > 0)

    payload = {
        "schema_version": 1,
        "status": "R3_PHASE1_SECONDARY_DEV_COMPARISON_COMPLETE",
        "claim_boundary": (
            "This is post-hoc secondary development evidence, not a preregistered "
            "promotion court. The exact Phase-1 candidate was already frozen before "
            "dev:128..159 was opened, but this comparison does not replace a future "
            "PRE_FRESH_LOCK or untouched fresh evaluation."
        ),
        "phase1_checkpoint_sha256": actual_checkpoint_sha,
        "phase1_state_dict_sha256": metadata["state_dict_sha256"],
        "selected_candidate": metadata["training_summary"]["selected_candidate"],
        "development_indices": list(indices),
        "parent": _compact(parent),
        "candidate": _compact(candidate),
        "family_solved_delta_vs_parent": family_delta,
        "total_solved_delta_vs_parent": total_delta,
        "implicit_goal_delta_vs_parent": implicit_delta,
        "visible_target_families_exact": visible_exact,
        "supports_freeze": supports_freeze,
        "fresh_opened": False,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": payload["status"],
        "parent_solved": parent["solved"],
        "candidate_solved": candidate["solved"],
        "family_delta": family_delta,
        "supports_freeze": supports_freeze,
        "fresh_opened": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
