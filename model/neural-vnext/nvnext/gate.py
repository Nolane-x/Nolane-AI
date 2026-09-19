from __future__ import annotations

from collections import Counter
from typing import Mapping, Sequence

EXPECTED_FAMILIES = (
    "causal_prerequisites",
    "conditional_regimes",
    "implicit_goal_regimes",
    "regime_switch",
)


def _fresh_bounds(lock: Mapping[str, object]) -> tuple[tuple[int, int], tuple[int, int]]:
    fresh = lock.get("confirmatory_fresh")
    if not isinstance(fresh, Mapping):
        raise ValueError("predevelopment lock is missing confirmatory_fresh")
    result: list[tuple[int, int]] = []
    for name in ("block_1_indices", "block_2_indices"):
        bounds = fresh.get(name)
        if (
            not isinstance(bounds, list)
            or len(bounds) != 2
            or type(bounds[0]) is not int
            or type(bounds[1]) is not int
            or bounds[0] > bounds[1]
        ):
            raise ValueError(f"{name} must be an exact inclusive integer range")
        result.append((bounds[0], bounds[1]))
    return result[0], result[1]


def _expected_pairs(lock: Mapping[str, object]) -> set[tuple[int, str]]:
    blocks = _fresh_bounds(lock)
    indices = [
        index
        for start, end in blocks
        for index in range(start, end + 1)
    ]
    return {(index, family) for index in indices for family in EXPECTED_FAMILIES}


def _normalize_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    lock: Mapping[str, object],
    label: str,
) -> dict[tuple[int, str], dict[str, object]]:
    fresh = lock.get("confirmatory_fresh")
    if not isinstance(fresh, Mapping):
        raise ValueError("predevelopment lock is missing confirmatory_fresh")
    episodes_expected = fresh.get("episodes_expected")
    if type(episodes_expected) is not int or episodes_expected < 1:
        raise ValueError("episodes_expected must be a positive exact integer")
    if len(rows) != episodes_expected:
        raise ValueError(f"{label} must contain exactly {episodes_expected} fresh episodes")

    expected = _expected_pairs(lock)
    if len(expected) != episodes_expected:
        raise ValueError("fresh lock ranges/families do not match episodes_expected")

    normalized: dict[tuple[int, str], dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"{label} rows must be mappings")
        index = row.get("index")
        family = row.get("family")
        solved = row.get("solved")
        if type(index) is not int:
            raise ValueError(f"{label} index must be an exact integer")
        if family not in EXPECTED_FAMILIES:
            raise ValueError(f"{label} contains an unknown family: {family}")
        if type(solved) is not bool:
            raise ValueError(f"{label} solved must be an exact boolean")
        steps = row.get("steps")
        if steps is not None and (type(steps) is not int or steps < 0):
            raise ValueError(f"{label} steps must be an exact non-negative integer")
        key = (index, str(family))
        if key not in expected:
            raise ValueError(f"{label} touches an unregistered fresh episode: {key}")
        if key in normalized:
            raise ValueError(f"{label} contains duplicate fresh episode: {key}")
        normalized[key] = {"solved": solved, "steps": steps}
    if set(normalized) != expected:
        missing = sorted(expected - set(normalized))
        raise ValueError(f"{label} is missing registered fresh episodes: {missing[:4]}")
    return normalized


def evaluate_frozen_fresh_gate(
    parent_rows: Sequence[Mapping[str, object]],
    candidate_rows: Sequence[Mapping[str, object]],
    *,
    predev_lock: Mapping[str, object],
    candidate_manifest: Mapping[str, object],
) -> dict[str, object]:
    if candidate_manifest.get("status") != "FROZEN_BEFORE_FRESH":
        raise ValueError("candidate must be frozen before fresh evaluation")
    if not isinstance(candidate_manifest.get("state_dict_sha256"), str):
        raise ValueError("candidate manifest is missing frozen tensor authority")
    if not isinstance(candidate_manifest.get("bundle_sha256"), str):
        raise ValueError("candidate manifest is missing frozen bundle authority")

    parent = _normalize_rows(parent_rows, lock=predev_lock, label="parent")
    candidate = _normalize_rows(candidate_rows, lock=predev_lock, label="candidate")
    if set(parent) != set(candidate):
        raise ValueError("parent and candidate fresh identities must match exactly")

    parent_solved = sum(int(row["solved"]) for row in parent.values())
    candidate_solved = sum(int(row["solved"]) for row in candidate.values())
    families: dict[str, list[int]] = {}
    regressions: list[str] = []
    for family in EXPECTED_FAMILIES:
        p = sum(int(parent[key]["solved"]) for key in parent if key[1] == family)
        c = sum(int(candidate[key]["solved"]) for key in candidate if key[1] == family)
        families[family] = [p, c]
        if c < p:
            regressions.append(family)

    parent_steps = sum(
        int(row["steps"])
        for row in parent.values()
        if row["steps"] is not None
    )
    candidate_steps = sum(
        int(row["steps"])
        for row in candidate.values()
        if row["steps"] is not None
    )
    all_steps_reported = all(row["steps"] is not None for row in parent.values()) and all(
        row["steps"] is not None for row in candidate.values()
    )

    promotion = predev_lock.get("promotion_gates")
    if not isinstance(promotion, Mapping):
        raise ValueError("predevelopment lock is missing promotion_gates")
    minimum_gain = promotion.get("candidate_solved_minimum_gain_over_parent")
    regressions_allowed = promotion.get("family_regressions_allowed")
    if type(minimum_gain) is not int or type(regressions_allowed) is not int:
        raise ValueError("promotion gate counts must be exact integers")

    gain = candidate_solved - parent_solved
    passed = gain >= minimum_gain and len(regressions) <= regressions_allowed
    episodes = len(parent)
    result: dict[str, object] = {
        "status": "PASS_FROZEN_CONFIRMATORY_FRESH" if passed else "FAIL_FROZEN_CONFIRMATORY_FRESH",
        "candidate": predev_lock.get("candidate"),
        "parent": predev_lock.get("parent"),
        "episodes": episodes,
        "parent_solved": parent_solved,
        "candidate_solved": candidate_solved,
        "candidate_solved_gain": gain,
        "gain_pp": 100.0 * gain / episodes,
        "families": families,
        "family_regressions": regressions,
        "promotion_gate": {
            "minimum_solved_gain": minimum_gain,
            "family_regressions_allowed": regressions_allowed,
            "passed": passed,
        },
        "candidate_state_dict_sha256": candidate_manifest["state_dict_sha256"],
        "candidate_bundle_sha256": candidate_manifest["bundle_sha256"],
        "predev_lock_sha256": candidate_manifest.get("predev_lock_sha256"),
        "weights_modified_after_fresh": False,
        "thresholds_modified_after_fresh": False,
    }
    if all_steps_reported:
        result["parent_steps"] = parent_steps
        result["candidate_steps"] = candidate_steps

    blocks: list[dict[str, object]] = []
    for start, end in _fresh_bounds(predev_lock):
        keys = [key for key in parent if start <= key[0] <= end]
        blocks.append(
            {
                "indices": [start, end],
                "episodes": len(keys),
                "parent_solved": sum(int(parent[key]["solved"]) for key in keys),
                "candidate_solved": sum(int(candidate[key]["solved"]) for key in keys),
            }
        )
    result["blocks"] = blocks
    return result
