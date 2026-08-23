from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REF_WORKFLOW = "refoundation-epoch0-wave1.yml"
_JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_.-]+):\s*$")


def _historical_root_candidates() -> tuple[Path, ...]:
    rows: list[Path] = []
    for path in ROOT.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if (
            (name.startswith("R") and len(name) > 1 and name[1].isdigit())
            or name.startswith("CURRENT_ONE_WEIGHT_")
            or name == "CURRENT_STATUS.md"
            or name == "CHECKPOINT_MANIFEST.json"
        ):
            rows.append(path)
    return tuple(sorted(rows, key=lambda p: p.name))


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _workflow_job_blocks(text: str) -> dict[str, str]:
    lines = text.splitlines()
    try:
        jobs_index = next(index for index, line in enumerate(lines) if line.strip() == "jobs:" and not line.startswith(" "))
    except StopIteration:
        return {}
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines[jobs_index + 1 :]:
        match = _JOB_HEADER.match(line)
        if match:
            current = match.group(1)
            blocks[current] = [line]
            continue
        if current is not None:
            blocks[current].append(line)
    return {name: "\n".join(rows) for name, rows in blocks.items()}


def test_wave4_current_and_archive_authority_files_exist() -> None:
    required = (
        ROOT / "CURRENT" / "REPOSITORY_AUTHORITY.md",
        ROOT / "CURRENT" / "NATIVE_DEBT.json",
        ROOT / "CURRENT" / "NATIVE_DEBT.md",
        ROOT / "archive" / "README.md",
        ROOT / "archive" / "INDEX.json",
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    assert not missing, f"missing Wave-4 authority files: {missing!r}"

    status = (ROOT / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 3" in status and ("accepted" in status.lower() or "merged" in status.lower())
    assert "Wave 4" in status and "quarantine" in status.lower()


def test_wave4_archive_index_covers_every_ambiguous_historical_root_artifact() -> None:
    index_path = ROOT / "archive" / "INDEX.json"
    assert index_path.is_file(), "archive/INDEX.json is required before root history can be trusted"
    payload = _load_json(index_path)
    assert payload["schema_version"] == "nolane-repository-history-v1"
    assert payload["component_version"] == "0.0.0"
    entries = payload["entries"]
    indexed = {row["original_path"] for row in entries}
    actual = {path.name for path in _historical_root_candidates()}
    assert indexed == actual, {
        "missing": sorted(actual - indexed),
        "stale": sorted(indexed - actual),
    }
    for row in entries:
        assert row["authority"] == "historical"
        assert row["delete_allowed"] is False
        assert row["move_status"] in {"quarantined_in_place", "moved"}
        assert row["sha256"] and len(row["sha256"]) == 64
        assert row["archive_target"].startswith("archive/")


def test_wave4_reference_audit_is_exhaustive_deterministic_and_fail_closed() -> None:
    from nolane.repository.audit import build_archive_index

    first = build_archive_index(ROOT)
    second = build_archive_index(ROOT)
    assert first == second
    assert first["reference_audit_policy"] == "exact-plus-family-dynamic-fail-closed-v1"

    entries = first["entries"]
    assert entries
    for row in entries:
        audit = row["reference_audit"]
        assert audit["decision"] in {"safe_to_move", "quarantined_in_place"}
        assert audit["reference_count"] == len(audit["references"])
        assert audit["blockers"] == sorted(set(audit["blockers"]))
        for ref in audit["references"]:
            assert ref["path"] != row["original_path"]
            assert isinstance(ref["line"], int) and ref["line"] >= 1
            assert ref["kind"] in {
                "active_source",
                "test",
                "workflow",
                "script",
                "documentation",
                "repository_metadata",
            }
        if row["category"] in {"historical_checkpoint_pointer", "legacy_weight_pointer"}:
            assert audit["decision"] == "quarantined_in_place"
            assert "protected_provenance_pointer" in audit["blockers"]
        if audit["decision"] == "safe_to_move":
            assert audit["reference_count"] == 0
            assert not audit["blockers"]
        else:
            assert audit["blockers"] or audit["reference_count"] > 0


def test_wave4_native_debt_is_exhaustive_against_implementation_ledger() -> None:
    from cogcoder.refoundation.implementation_status import (
        ImplementationStatus,
        build_component_implementation_ledger,
    )

    path = ROOT / "CURRENT" / "NATIVE_DEBT.json"
    assert path.is_file(), "CURRENT/NATIVE_DEBT.json must expose remaining migration debt"
    payload = _load_json(path)
    assert payload["schema_version"] == "nolane-native-debt-v1"
    expected = {
        component_id: row
        for component_id, row in build_component_implementation_ledger().items()
        if row.status is not ImplementationStatus.CANONICAL_NATIVE
    }
    actual = {row["component_id"]: row for row in payload["components"]}
    assert set(actual) == set(expected), {
        "missing": sorted(set(expected) - set(actual)),
        "stale": sorted(set(actual) - set(expected)),
    }
    for component_id, expected_row in expected.items():
        row = actual[component_id]
        assert row["component_version"] == expected_row.component_version
        assert row["implementation_status"] == expected_row.status.value
        assert row["canonical_write_authority"] is False
        assert row["legacy_sources"] == list(expected_row.legacy_sources)


def test_wave4_repository_audit_materialization_is_fresh_and_deterministic(tmp_path: Path) -> None:
    from nolane.repository.audit import (
        build_archive_index,
        build_native_debt,
        render_native_debt_markdown,
        stale_paths,
        write_materialized_audit,
    )

    archive = build_archive_index(ROOT)
    debt = build_native_debt()
    assert archive == build_archive_index(ROOT)
    assert debt == build_native_debt()
    assert render_native_debt_markdown(debt) == render_native_debt_markdown(debt)

    written = write_materialized_audit(source_root=ROOT, output_root=tmp_path)
    assert written == 3
    assert stale_paths(source_root=ROOT, output_root=tmp_path) == ()
    assert write_materialized_audit(source_root=ROOT, output_root=tmp_path) == 0

    assert stale_paths(source_root=ROOT, output_root=ROOT) == ()


def test_wave4_all_historical_pull_request_workflow_jobs_skip_refoundation_heads() -> None:
    workflows = ROOT / ".github" / "workflows"
    offenders: list[str] = []
    for path in sorted((*workflows.glob("*.yml"), *workflows.glob("*.yaml"))):
        if path.name == REF_WORKFLOW:
            continue
        text = path.read_text(encoding="utf-8")
        if "pull_request:" not in text:
            continue
        blocks = _workflow_job_blocks(text)
        if not blocks:
            offenders.append(f"{path.name}:<no-jobs-parsed>")
            continue
        for job_name, block in blocks.items():
            if "github.head_ref" not in block or "refoundation/" not in block:
                offenders.append(f"{path.name}:{job_name}")
    assert not offenders, f"historical PR workflow jobs missing refoundation-head isolation: {offenders!r}"


def test_wave4_workflow_isolation_rewriter_preserves_existing_conditions_and_is_idempotent() -> None:
    from nolane.repository.workflow_isolation import isolate_workflow_text

    source = """name: sample\non:\n  pull_request:\n  push:\n\njobs:\n  plain:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo plain\n  conditional:\n    if: ${{ github.actor != 'blocked' }}\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo conditional\n  folded:\n    if: >-\n      github.repository_owner == 'Nolane-x' &&\n      github.event_name != 'workflow_dispatch'\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo folded\n"""
    isolated = isolate_workflow_text(source)
    blocks = _workflow_job_blocks(isolated)
    assert set(blocks) == {"plain", "conditional", "folded"}
    assert all("github.head_ref" in block and "refoundation/" in block for block in blocks.values())
    assert "github.actor != 'blocked'" in blocks["conditional"]
    assert "github.repository_owner == 'Nolane-x'" in blocks["folded"]
    assert "github.event_name != 'workflow_dispatch'" in blocks["folded"]
    assert isolate_workflow_text(isolated) == isolated

    non_pr = "name: push-only\non:\n  push:\n\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
    assert isolate_workflow_text(non_pr) == non_pr


def test_wave4_refoundation_workflow_gates_repository_audit_freshness() -> None:
    text = (ROOT / ".github" / "workflows" / REF_WORKFLOW).read_text(encoding="utf-8")
    assert "python -m nolane.repository.audit --check" in text
    assert "CURRENT/**" in text
    assert "archive/**" in text
    assert "nolane/repository/**" in text
