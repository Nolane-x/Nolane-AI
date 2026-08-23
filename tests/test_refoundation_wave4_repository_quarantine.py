from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REF_WORKFLOW = "refoundation-epoch0-wave1.yml"


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


def test_wave4_all_historical_pull_request_workflows_skip_refoundation_heads() -> None:
    workflows = ROOT / ".github" / "workflows"
    offenders: list[str] = []
    for path in sorted((*workflows.glob("*.yml"), *workflows.glob("*.yaml"))):
        if path.name == REF_WORKFLOW:
            continue
        text = path.read_text(encoding="utf-8")
        if "pull_request:" not in text:
            continue
        isolated = (
            "github.head_ref" in text
            and "refoundation/" in text
            and (
                "REF0_PR_ISOLATION" in text
                or "REFOUNDATION_PR_ISOLATION" in text
                or "startsWith(github.head_ref" in text
            )
        )
        if not isolated:
            offenders.append(path.name)
    assert not offenders, f"historical PR workflows missing refoundation-head isolation: {offenders!r}"


def test_wave4_refoundation_workflow_gates_repository_audit_freshness() -> None:
    text = (ROOT / ".github" / "workflows" / REF_WORKFLOW).read_text(encoding="utf-8")
    assert "python -m nolane.repository.audit --check" in text
    assert "CURRENT/**" in text
    assert "archive/**" in text
    assert "nolane/repository/**" in text
