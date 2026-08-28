from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _historical_root_names() -> tuple[str, ...]:
    rows: list[str] = []
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
            rows.append(name)
    return tuple(sorted(rows))


def test_wave5as_root_surface_contains_no_historical_release_artifacts() -> None:
    assert _historical_root_names() == ()


def test_wave5as_archive_index_is_a_complete_moved_provenance_ledger() -> None:
    payload = json.loads((ROOT / "archive" / "INDEX.json").read_text(encoding="utf-8"))
    entries = payload["entries"]
    assert entries
    assert all(row["move_status"] == "moved" for row in entries)
    assert all(row["delete_allowed"] is False for row in entries)
    assert all(not row["reference_audit"]["blockers"] for row in entries)
    for row in entries:
        target = ROOT / row["archive_target"]
        assert target.is_file(), row["archive_target"]
        assert hashlib.sha256(target.read_bytes()).hexdigest() == row["sha256"]


def test_wave5as_r22_integrity_is_not_an_automatic_main_gate() -> None:
    text = (ROOT / ".github" / "workflows" / "r22-integrity.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "branches: [main]" not in text


def test_wave5as_current_status_records_repository_surface_closure() -> None:
    status = (ROOT / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AS" in status
    assert "repository surface" in status.lower()
    assert "historical root artifacts" in status.lower()
