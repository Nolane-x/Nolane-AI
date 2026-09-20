from __future__ import annotations

import argparse
from hashlib import sha1, sha256
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
MODEL_ROOT = HERE.parents[2]
R4_ROOT = MODEL_ROOT / "neural-vnext-native-r4"
R3_ROOT = MODEL_ROOT / "neural-vnext-native-r3"
R2_ROOT = MODEL_ROOT / "neural-vnext-native-r2"
NATIVE_ROOT = MODEL_ROOT / "neural-vnext-native"
R18_ROOT = MODEL_ROOT / "r1.8"
REPO_ROOT = HERE.parents[3]
for path in (ROOT, R4_ROOT, R3_ROOT, R2_ROOT, NATIVE_ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from cogcoder.r18_benchmark import make_r18_task
from latent_goal_training import evaluate_r4
from consistency_training import evaluate_r5, load_r5_checkpoint

CANDIDATE_IDENTITY = "Neural-vNext-Native-R5-PublicConsistency"
LOCKED_FAMILIES = (
    "conditional_regimes",
    "regime_switch",
    "implicit_goal_regimes",
    "causal_prerequisites",
)
VISIBLE_FAMILIES = (
    "conditional_regimes",
    "regime_switch",
    "causal_prerequisites",
)
FRESH_START = 160
FRESH_END = 199
FRESH_EPISODES = 160
LOCKED_GATE = {
    "minimum_total_solved_delta_vs_parent": 1,
    "target_family": "implicit_goal_regimes",
    "minimum_target_family_solved_delta": 1,
    "visible_target_families": list(VISIBLE_FAMILIES),
    "required_visible_family_solved_delta": 0,
    "all_requirements_must_pass": True,
}


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    return sha1(
        f"blob {len(payload)}\0".encode("ascii") + payload
    ).hexdigest()


def _exact_int(value: Any, *, field: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{field} must be an exact integer")
    return value


def load_lock(path: Path) -> dict[str, Any]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(lock, dict) or lock.get("schema_version") != 1:
        raise ValueError("unsupported R5 PRE_FRESH_LOCK schema")
    if lock.get("status") != "FROZEN_FRESH_UNOPENED":
        raise ValueError("R5 fresh court requires FROZEN_FRESH_UNOPENED")
    if lock.get("candidate") != CANDIDATE_IDENTITY:
        raise ValueError("unexpected R5 fresh candidate identity")
    court = lock.get("fresh_court")
    if not isinstance(court, dict) or court.get("opened") is not False:
        raise ValueError("R5 fresh court lock must attest opened=false")
    if tuple(court.get("families", ())) != LOCKED_FAMILIES:
        raise ValueError("R5 fresh families differ from preregistration")
    if court.get("index_start") != FRESH_START or court.get("index_end") != FRESH_END:
        raise ValueError("R5 fresh indices differ from preregistration")
    if court.get("episodes_expected") != FRESH_EPISODES:
        raise ValueError("R5 fresh episode count differs from preregistration")
    if lock.get("promotion_gate") != LOCKED_GATE:
        raise ValueError("R5 promotion gate differs from preregistration")
    frozen = lock.get("frozen_candidate")
    if not isinstance(frozen, dict) or frozen.get("fresh_opened") is not False:
        raise ValueError("R5 frozen candidate must attest fresh_opened=false")
    authority = lock.get("candidate_authority")
    if not isinstance(authority, dict):
        raise ValueError("R5 candidate authority missing")
    if authority.get("mode") != "frozen_workflow_artifact" or authority.get("status") != "VERIFIED":
        raise ValueError("R5 requires verified frozen-workflow-artifact authority")
    if authority.get("checkpoint_sha256") != frozen.get("checkpoint_sha256"):
        raise ValueError("R5 authority checkpoint differs from frozen candidate")
    if authority.get("state_dict_sha256") != frozen.get("state_dict_sha256"):
        raise ValueError("R5 authority state differs from frozen candidate")
    if authority.get("selected_candidate") != frozen.get("selected_candidate"):
        raise ValueError("R5 authority selected candidate differs from frozen candidate")
    reproduction = lock.get("source_training_reproducibility")
    if not isinstance(reproduction, dict):
        raise ValueError("R5 reproduction disclosure missing")
    if reproduction.get("status") != "BITWISE_REPRODUCED_WORKFLOW_LEVEL":
        raise ValueError("R5 reproduction status changed")
    if reproduction.get("exact_inner_files_reproduced") is not True:
        raise ValueError("R5 exact dev files must remain reproduced")
    if reproduction.get("cross_host_guarantee_claimed") is not False:
        raise ValueError("R5 must not claim universal cross-host bitwise reproducibility")
    return lock


def verify_source_blobs(lock: Mapping[str, Any], repo_root: Path) -> None:
    rows = lock.get("frozen_source_git_blobs")
    if not isinstance(rows, dict) or not rows:
        raise ValueError("R5 PRE_FRESH_LOCK is missing frozen source blobs")
    for relative, expected in rows.items():
        path = repo_root / relative
        if not path.is_file():
            raise ValueError(f"frozen source file missing: {relative}")
        actual = git_blob_sha(path)
        if actual != expected:
            raise ValueError(
                f"frozen source blob mismatch for {relative}: expected {expected}, got {actual}"
            )


def verify_reproduction_evidence(lock: Mapping[str, Any], repo_root: Path) -> None:
    path = repo_root / "model/neural-vnext-native-r5/evidence/DEV_REPRO_001.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    reproduction = lock["source_training_reproducibility"]
    if evidence.get("status") != "R5_DEV_BITWISE_REPRODUCED_WORKFLOW_LEVEL":
        raise ValueError("R5 dev reproduction evidence status changed")
    if evidence.get("canonical_workflow_run_id") != reproduction.get("canonical_workflow_run_id"):
        raise ValueError("R5 canonical dev run evidence mismatch")
    if evidence.get("fresh_opened") is not False:
        raise ValueError("R5 dev evidence must attest fresh unopened")


def verify_checkpoint(
    lock: Mapping[str, Any],
    checkpoint: Path,
) -> tuple[Any, dict[str, Any]]:
    model, metadata = load_r5_checkpoint(checkpoint)
    frozen = lock["frozen_candidate"]
    expected = {
        "checkpoint_sha256": frozen["checkpoint_sha256"],
        "state_dict_sha256": frozen["state_dict_sha256"],
        "parameters": frozen["parameters"],
        "successor_parameters": frozen["successor_parameters"],
        "parent_checkpoint_sha256": frozen["parent_checkpoint_sha256"],
        "parent_state_dict_sha256": frozen["parent_state_dict_sha256"],
        "predev_lock_sha256": frozen["predev_lock_sha256"],
    }
    actual = {key: metadata.get(key) for key in expected}
    if actual != expected:
        raise ValueError(f"R5 frozen checkpoint authority mismatch: expected {expected}, got {actual}")
    summary = metadata.get("training_summary")
    if not isinstance(summary, dict):
        raise ValueError("R5 checkpoint training summary missing")
    for key in ("selected_candidate", "selected_rank", "selected_eligibility", "parent_development"):
        if summary.get(key) != frozen[key]:
            raise ValueError(f"R5 frozen {key} evidence mismatch")
    tournament = summary.get("candidate_tournament")
    if not isinstance(tournament, list):
        raise ValueError("R5 candidate tournament missing")
    selected = [
        row for row in tournament
        if isinstance(row, dict) and row.get("name") == frozen["selected_candidate"]
    ]
    if len(selected) != 1:
        raise ValueError("R5 selected candidate must be unique in tournament")
    if selected[0].get("development") != frozen["development"]:
        raise ValueError("R5 frozen development evidence mismatch")
    if selected[0].get("eligibility") != frozen["selected_eligibility"]:
        raise ValueError("R5 frozen eligibility evidence mismatch")
    if summary.get("fresh_opened") is not False:
        raise ValueError("R5 checkpoint must attest fresh unopened")
    return model, metadata


def expected_identities(lock: Mapping[str, Any]) -> set[tuple[str, int]]:
    court = lock["fresh_court"]
    expected = {
        (str(family), index)
        for family in court["families"]
        for index in range(_exact_int(court["index_start"], field="fresh index_start"), _exact_int(court["index_end"], field="fresh index_end") + 1)
    }
    if len(expected) != _exact_int(court["episodes_expected"], field="fresh episodes"):
        raise ValueError("R5 fresh Cartesian cardinality mismatch")
    return expected


def verify_rows(
    lock: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> None:
    observed: list[tuple[str, int]] = []
    for row in rows:
        if row.get("split") != "fresh":
            raise ValueError(f"{label} contains non-fresh row")
        family = row.get("family")
        index = _exact_int(row.get("index"), field=f"{label} fresh index")
        if not isinstance(family, str):
            raise ValueError(f"{label} family must be a string")
        observed.append((family, index))
    if len(observed) != len(set(observed)):
        raise ValueError(f"{label} contains duplicate fresh identities")
    if set(observed) != expected_identities(lock):
        raise ValueError(f"{label} fresh identities differ from locked Cartesian court")


def promotion_gate(
    lock: Mapping[str, Any],
    *,
    parent: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    gate = lock["promotion_gate"]
    parent_families = parent["families"]
    candidate_families = candidate["families"]
    parent_total = _exact_int(parent["solved"], field="parent solved")
    candidate_total = _exact_int(candidate["solved"], field="candidate solved")
    total_delta = candidate_total - parent_total
    family_delta = {
        family: _exact_int(candidate_families[family]["solved"], field=f"candidate {family} solved")
        - _exact_int(parent_families[family]["solved"], field=f"parent {family} solved")
        for family in parent_families
    }
    target = str(gate["target_family"])
    visible_pass = {
        family: family_delta[family] == gate["required_visible_family_solved_delta"]
        for family in gate["visible_target_families"]
    }
    target_delta = family_delta[target]
    accepted = bool(
        total_delta >= gate["minimum_total_solved_delta_vs_parent"]
        and target_delta >= gate["minimum_target_family_solved_delta"]
        and all(visible_pass.values())
    )
    return {
        "accepted": accepted,
        "parent_total_solved": parent_total,
        "candidate_total_solved": candidate_total,
        "total_solved_delta_vs_parent": total_delta,
        "minimum_total_solved_delta_vs_parent": gate["minimum_total_solved_delta_vs_parent"],
        "family_solved_delta_vs_parent": family_delta,
        "target_family": target,
        "target_family_solved_delta_vs_parent": target_delta,
        "minimum_target_family_solved_delta": gate["minimum_target_family_solved_delta"],
        "visible_target_family_required_delta": gate["required_visible_family_solved_delta"],
        "visible_target_family_pass": visible_pass,
        "all_visible_target_families_exact": all(visible_pass.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=ROOT / "PRE_FRESH_LOCK.json")
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()

    lock = load_lock(args.lock)
    verify_source_blobs(lock, REPO_ROOT)
    verify_reproduction_evidence(lock, REPO_ROOT)
    model, metadata = verify_checkpoint(lock, args.checkpoint)

    court = lock["fresh_court"]
    families = tuple(str(value) for value in court["families"])
    indices = (court["index_start"], court["index_end"])
    parent = evaluate_r4(
        model.parent,
        make_task=make_r18_task,
        families=families,
        split="fresh",
        indices=indices,
    )
    candidate = evaluate_r5(
        model,
        make_task=make_r18_task,
        families=families,
        split="fresh",
        indices=indices,
    )
    verify_rows(lock, parent["rows"], label="parent")
    verify_rows(lock, candidate["rows"], label="candidate")
    gate = promotion_gate(lock, parent=parent, candidate=candidate)
    payload = {
        "schema_version": 1,
        "status": "FRESH_ACCEPTED" if gate["accepted"] else "FRESH_REJECTED",
        "candidate": CANDIDATE_IDENTITY,
        "pre_fresh_lock_sha256": _sha256_file(args.lock),
        "checkpoint_sha256": metadata["checkpoint_sha256"],
        "state_dict_sha256": metadata["state_dict_sha256"],
        "parameters": metadata["parameters"],
        "successor_parameters": metadata["successor_parameters"],
        "selected_candidate": metadata["training_summary"]["selected_candidate"],
        "parent_fresh": parent,
        "candidate_fresh": candidate,
        "promotion_gate": gate,
        "post_fresh_tuning_allowed": False,
        "fresh_block_reuse_for_promotion_allowed": False,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": payload["status"],
        "parent_solved": parent["solved"],
        "candidate_solved": candidate["solved"],
        "candidate_families": candidate["families"],
        "promotion_gate": gate,
        "checkpoint_sha256": metadata["checkpoint_sha256"],
        "state_dict_sha256": metadata["state_dict_sha256"],
    }, sort_keys=True))
    return 0 if gate["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
