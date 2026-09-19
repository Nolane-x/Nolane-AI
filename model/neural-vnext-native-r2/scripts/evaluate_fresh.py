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
PARENT_ROOT = MODEL_ROOT / "neural-vnext-native"
R18_ROOT = MODEL_ROOT / "r1.8"
for path in (ROOT, PARENT_ROOT, R18_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from cogcoder.r18_benchmark import make_r18_task  # noqa: E402
from native_training import evaluate_policy  # noqa: E402
from successor_training import evaluate_successor, load_successor_checkpoint  # noqa: E402


CANDIDATE_IDENTITY = "Neural-vNext-Native-R2-TransitionTrace"
LOCKED_FRESH_FAMILIES = (
    "conditional_regimes",
    "regime_switch",
    "implicit_goal_regimes",
    "causal_prerequisites",
)
LOCKED_FRESH_INDEX_START = 40
LOCKED_FRESH_INDEX_END = 79
LOCKED_FRESH_EPISODES = 160
LOCKED_PROMOTION_GATE = {
    "minimum_total_solved_delta_vs_parent": 1,
    "maximum_family_solved_regression": 0,
    "target_family": "implicit_goal_regimes",
    "minimum_target_family_solved_delta": 1,
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
    header = f"blob {len(payload)}\0".encode("ascii")
    return sha1(header + payload).hexdigest()


def _exact_int(value: Any, *, field: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{field} must be an exact integer")
    return value


def load_fresh_lock(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported R2 PRE_FRESH_LOCK schema")
    if payload.get("status") != "FROZEN_FRESH_UNOPENED":
        raise ValueError("R2 fresh court requires FROZEN_FRESH_UNOPENED")
    if payload.get("candidate") != CANDIDATE_IDENTITY:
        raise ValueError("unexpected R2 fresh candidate identity")
    court = payload.get("fresh_court")
    if not isinstance(court, dict) or court.get("opened") is not False:
        raise ValueError("R2 fresh court lock must attest opened=false")
    if tuple(court.get("families", ())) != LOCKED_FRESH_FAMILIES:
        raise ValueError("R2 fresh families differ from preregistered identities")
    if court.get("index_start") != LOCKED_FRESH_INDEX_START:
        raise ValueError("R2 fresh index_start differs from preregistration")
    if court.get("index_end") != LOCKED_FRESH_INDEX_END:
        raise ValueError("R2 fresh index_end differs from preregistration")
    if court.get("episodes_expected") != LOCKED_FRESH_EPISODES:
        raise ValueError("R2 fresh episode count differs from preregistration")
    if payload.get("promotion_gate") != LOCKED_PROMOTION_GATE:
        raise ValueError("R2 promotion gate differs from preregistration")
    frozen = payload.get("frozen_candidate")
    if not isinstance(frozen, dict):
        raise ValueError("R2 PRE_FRESH_LOCK is missing frozen_candidate")
    if frozen.get("fresh_opened") is not False:
        raise ValueError("frozen candidate must attest fresh_opened=false")

    authority = payload.get("candidate_authority")
    if not isinstance(authority, dict):
        raise ValueError("R2 PRE_FRESH_LOCK is missing candidate_authority")
    if authority.get("mode") != "frozen_workflow_artifact":
        raise ValueError("R2 fresh court requires frozen_workflow_artifact authority")
    if authority.get("status") != "VERIFIED":
        raise ValueError("R2 frozen artifact authority must be VERIFIED")
    _exact_int(authority.get("workflow_run_id"), field="authority workflow_run_id")
    _exact_int(authority.get("artifact_id"), field="authority artifact_id")
    digest = authority.get("artifact_digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:") or len(digest) != 71:
        raise ValueError("R2 candidate authority requires an artifact sha256 digest")
    if authority.get("checkpoint_sha256") != frozen.get("checkpoint_sha256"):
        raise ValueError("R2 authority checkpoint hash differs from frozen candidate")
    if authority.get("state_dict_sha256") != frozen.get("state_dict_sha256"):
        raise ValueError("R2 authority state hash differs from frozen candidate")
    if authority.get("selected_candidate") != frozen.get("selected_candidate"):
        raise ValueError("R2 authority selected candidate differs from frozen candidate")
    if authority.get("fresh_opened") is not False:
        raise ValueError("R2 candidate authority must attest fresh_opened=false")

    source_repro = payload.get("source_training_reproducibility")
    if not isinstance(source_repro, dict):
        raise ValueError("R2 PRE_FRESH_LOCK must disclose source training reproducibility")
    if source_repro.get("status") != "FAILED_CROSS_HOST_DISCLOSED":
        raise ValueError("R2 source-training negative result must remain disclosed")
    failures = source_repro.get("failed_attempts")
    if not isinstance(failures, list) or not failures:
        raise ValueError("R2 source-training disclosure requires failed attempts")
    for failure in failures:
        if not isinstance(failure, dict):
            raise ValueError("R2 failed reproduction attempt must be a mapping")
        _exact_int(failure.get("workflow_run_id"), field="failed workflow_run_id")
    if source_repro.get("cross_host_bitwise_reproducible") is not False:
        raise ValueError("R2 must not claim cross-host bitwise source reproducibility")
    if source_repro.get("cross_host_behaviorally_reproducible") is not False:
        raise ValueError("R2 must not claim cross-host behavioral source reproducibility")
    return payload


def verify_source_blobs(lock: Mapping[str, Any], repo_root: Path) -> None:
    rows = lock.get("frozen_source_git_blobs")
    if not isinstance(rows, dict) or not rows:
        raise ValueError("R2 PRE_FRESH_LOCK is missing frozen source blobs")
    for relative, expected in rows.items():
        if not isinstance(relative, str) or not relative:
            raise ValueError("frozen source path must be a non-empty string")
        if not isinstance(expected, str) or len(expected) != 40:
            raise ValueError(f"invalid frozen blob identity for {relative}")
        path = repo_root / relative
        if not path.is_file():
            raise ValueError(f"frozen source file missing: {relative}")
        actual = git_blob_sha(path)
        if actual != expected:
            raise ValueError(
                f"frozen source blob mismatch for {relative}: "
                f"expected {expected}, got {actual}"
            )


def verify_checkpoint(
    lock: Mapping[str, Any],
    checkpoint: Path,
) -> tuple[Any, dict[str, Any]]:
    model, metadata = load_successor_checkpoint(checkpoint)
    frozen = lock["frozen_candidate"]
    expected = {
        "checkpoint_sha256": str(frozen["checkpoint_sha256"]),
        "state_dict_sha256": str(frozen["state_dict_sha256"]),
        "predev_lock_sha256": str(frozen["predev_lock_sha256"]),
        "parameters": _exact_int(frozen["parameters"], field="parameters"),
        "successor_parameters": _exact_int(
            frozen["successor_parameters"],
            field="successor_parameters",
        ),
        "parent_checkpoint_sha256": str(frozen["parent_checkpoint_sha256"]),
        "parent_state_dict_sha256": str(frozen["parent_state_dict_sha256"]),
    }
    actual = {
        "checkpoint_sha256": str(metadata["checkpoint_sha256"]),
        "state_dict_sha256": str(metadata["state_dict_sha256"]),
        "predev_lock_sha256": str(metadata["predev_lock_sha256"]),
        "parameters": _exact_int(metadata["parameters"], field="checkpoint parameters"),
        "successor_parameters": _exact_int(
            metadata["successor_parameters"],
            field="checkpoint successor_parameters",
        ),
        "parent_checkpoint_sha256": str(metadata["parent_checkpoint_sha256"]),
        "parent_state_dict_sha256": str(metadata["parent_state_dict_sha256"]),
    }
    if actual != expected:
        raise ValueError(
            f"frozen R2 checkpoint authority mismatch: expected {expected}, got {actual}"
        )

    summary = metadata.get("training_summary")
    if not isinstance(summary, dict):
        raise ValueError("R2 checkpoint training_summary is unavailable")
    if summary.get("selected_candidate") != frozen.get("selected_candidate"):
        raise ValueError("R2 selected candidate mismatch")
    if summary.get("fresh_opened") is not False:
        raise ValueError("R2 checkpoint metadata must attest fresh_opened=false")

    expected_rank = frozen.get("selected_rank")
    if not isinstance(expected_rank, list) or len(expected_rank) != 3:
        raise ValueError("R2 frozen candidate is missing selected_rank")
    observed_rank = summary.get("selected_rank")
    if observed_rank != expected_rank:
        raise ValueError(
            f"R2 selected rank mismatch: expected {expected_rank}, got {observed_rank}"
        )

    expected_eligibility = frozen.get("selected_eligibility")
    if not isinstance(expected_eligibility, dict) or expected_eligibility.get("eligible") is not True:
        raise ValueError("R2 frozen candidate must carry eligible development authority")
    if summary.get("selected_eligibility") != expected_eligibility:
        raise ValueError("R2 selected eligibility mismatch")

    expected_dev = frozen.get("development")
    if not isinstance(expected_dev, dict):
        raise ValueError("R2 frozen candidate is missing development evidence")
    tournament = summary.get("phase2_tournament")
    if not isinstance(tournament, list):
        raise ValueError("R2 checkpoint phase2 tournament is unavailable")
    selected_rows = [
        row for row in tournament
        if isinstance(row, dict) and row.get("name") == frozen.get("selected_candidate")
    ]
    if len(selected_rows) != 1:
        raise ValueError("R2 selected candidate is not unique in phase2 tournament")
    observed_dev = selected_rows[0].get("development")
    observed_eligibility = selected_rows[0].get("eligibility")
    if observed_dev != expected_dev:
        raise ValueError("R2 frozen development evidence mismatch")
    if observed_eligibility != expected_eligibility:
        raise ValueError("R2 tournament eligibility evidence mismatch")

    if summary.get("phase1_on_phase2_dev") != frozen.get("phase1_reference"):
        raise ValueError("R2 phase1 reference evidence mismatch")
    if summary.get("parent_phase2_dev") != frozen.get("parent_reference"):
        raise ValueError("R2 parent reference evidence mismatch")
    return model, metadata


def expected_identities(lock: Mapping[str, Any]) -> set[tuple[str, int]]:
    court = lock["fresh_court"]
    families_raw = court.get("families")
    if not isinstance(families_raw, list) or not families_raw:
        raise ValueError("fresh families must be a non-empty list")
    families: list[str] = []
    for value in families_raw:
        if not isinstance(value, str) or not value:
            raise ValueError("fresh family identities must be non-empty strings")
        families.append(value)
    if len(families) != len(set(families)):
        raise ValueError("fresh families must be unique")

    start = _exact_int(court.get("index_start"), field="fresh index_start")
    end = _exact_int(court.get("index_end"), field="fresh index_end")
    if start < 0 or end < start:
        raise ValueError("invalid fresh index range")

    expected = {
        (family, index)
        for family in families
        for index in range(start, end + 1)
    }
    expected_count = _exact_int(
        court.get("episodes_expected"),
        field="fresh episodes_expected",
    )
    if len(expected) != expected_count:
        raise ValueError(
            f"fresh court cardinality mismatch: lock says {expected_count}, "
            f"Cartesian product has {len(expected)}"
        )
    return expected


def verify_court_rows(
    lock: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> None:
    expected = expected_identities(lock)
    observed: list[tuple[str, int]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"{label} court row must be a mapping")
        if row.get("split") != "fresh":
            raise ValueError(f"{label} court contains a non-fresh row")
        family = row.get("family")
        if not isinstance(family, str) or not family:
            raise ValueError(f"{label} court family identity must be a string")
        index = _exact_int(row.get("index"), field=f"{label} fresh index")
        observed.append((family, index))

    if len(observed) != len(set(observed)):
        raise ValueError(f"{label} court contains duplicate identities")
    observed_set = set(observed)
    if observed_set != expected:
        missing = sorted(expected - observed_set)
        extra = sorted(observed_set - expected)
        raise ValueError(
            f"{label} fresh identity mismatch: missing={missing}, extra={extra}"
        )


def promotion_gate(
    lock: Mapping[str, Any],
    *,
    parent: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    gate = lock.get("promotion_gate")
    if not isinstance(gate, Mapping):
        raise ValueError("R2 PRE_FRESH_LOCK is missing promotion_gate")

    minimum_total_delta = _exact_int(
        gate.get("minimum_total_solved_delta_vs_parent"),
        field="minimum_total_solved_delta_vs_parent",
    )
    maximum_family_regression = _exact_int(
        gate.get("maximum_family_solved_regression"),
        field="maximum_family_solved_regression",
    )
    minimum_target_delta = _exact_int(
        gate.get("minimum_target_family_solved_delta"),
        field="minimum_target_family_solved_delta",
    )
    target_family = gate.get("target_family")
    if not isinstance(target_family, str) or not target_family:
        raise ValueError("promotion target_family must be a non-empty string")
    if minimum_total_delta < 1:
        raise ValueError("R2 promotion requires a positive total solved delta")
    if maximum_family_regression < 0:
        raise ValueError("maximum family regression must be non-negative")
    if minimum_target_delta < 1:
        raise ValueError("R2 promotion requires a positive target-family delta")

    parent_families = parent.get("families")
    candidate_families = candidate.get("families")
    if not isinstance(parent_families, Mapping) or not isinstance(
        candidate_families, Mapping
    ):
        raise ValueError("fresh results are missing family aggregates")
    if set(parent_families) != set(candidate_families):
        raise ValueError("parent/candidate fresh family sets differ")
    if target_family not in parent_families:
        raise ValueError("target family is absent from fresh result")

    parent_total = _exact_int(parent.get("solved"), field="parent fresh solved")
    candidate_total = _exact_int(
        candidate.get("solved"),
        field="candidate fresh solved",
    )
    total_delta = candidate_total - parent_total
    total_pass = total_delta >= minimum_total_delta

    family_delta: dict[str, int] = {}
    family_pass: dict[str, bool] = {}
    for family in sorted(parent_families):
        p_row = parent_families[family]
        c_row = candidate_families[family]
        if not isinstance(p_row, Mapping) or not isinstance(c_row, Mapping):
            raise ValueError("fresh family aggregate must be a mapping")
        p_solved = _exact_int(
            p_row.get("solved"),
            field=f"parent {family} solved",
        )
        c_solved = _exact_int(
            c_row.get("solved"),
            field=f"candidate {family} solved",
        )
        delta = c_solved - p_solved
        family_delta[str(family)] = delta
        family_pass[str(family)] = delta >= -maximum_family_regression

    target_delta = family_delta[target_family]
    target_pass = target_delta >= minimum_target_delta
    no_excess_family_regression = all(family_pass.values())
    accepted = bool(total_pass and target_pass and no_excess_family_regression)

    return {
        "accepted": accepted,
        "parent_total_solved": parent_total,
        "candidate_total_solved": candidate_total,
        "total_solved_delta_vs_parent": total_delta,
        "minimum_total_solved_delta_vs_parent": minimum_total_delta,
        "total_delta_pass": total_pass,
        "maximum_family_solved_regression": maximum_family_regression,
        "family_solved_delta_vs_parent": family_delta,
        "family_regression_pass": family_pass,
        "all_family_regressions_pass": no_excess_family_regression,
        "target_family": target_family,
        "target_family_solved_delta_vs_parent": target_delta,
        "minimum_target_family_solved_delta": minimum_target_delta,
        "target_family_delta_pass": target_pass,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Open the frozen Neural vNext Native R2 fresh court once, "
            "evaluating the accepted frozen parent and the immutable successor "
            "on the exact same untouched fresh identities."
        )
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
    indices = (
        _exact_int(court["index_start"], field="fresh index_start"),
        _exact_int(court["index_end"], field="fresh index_end"),
    )

    parent_fresh = evaluate_policy(
        model.parent,
        make_task=make_r18_task,
        families=families,
        split="fresh",
        indices=indices,
    )
    candidate_fresh = evaluate_successor(
        model,
        make_task=make_r18_task,
        families=families,
        split="fresh",
        indices=indices,
    )
    verify_court_rows(lock, parent_fresh["rows"], label="parent")
    verify_court_rows(lock, candidate_fresh["rows"], label="candidate")
    gate = promotion_gate(
        lock,
        parent=parent_fresh,
        candidate=candidate_fresh,
    )

    payload = {
        "schema_version": 1,
        "status": "FRESH_ACCEPTED" if gate["accepted"] else "FRESH_REJECTED",
        "candidate": CANDIDATE_IDENTITY,
        "pre_fresh_lock_sha256": _sha256_file(args.lock),
        "freeze_source_head": lock["freeze_source_head"],
        "checkpoint_sha256": metadata["checkpoint_sha256"],
        "state_dict_sha256": metadata["state_dict_sha256"],
        "parameters": metadata["parameters"],
        "successor_parameters": metadata["successor_parameters"],
        "selected_candidate": metadata["training_summary"]["selected_candidate"],
        "parent_fresh": parent_fresh,
        "candidate_fresh": candidate_fresh,
        "promotion_gate": gate,
        "post_fresh_tuning_allowed": False,
        "fresh_block_reuse_for_promotion_allowed": False,
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
                "parent_solved": parent_fresh["solved"],
                "candidate_solved": candidate_fresh["solved"],
                "candidate_solve_rate": candidate_fresh["solve_rate"],
                "candidate_families": candidate_fresh["families"],
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
