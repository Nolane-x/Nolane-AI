from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

_MANUAL_ONLY_POST_REFOUNDATION_WORKFLOWS = (
    "r21-integrity.yml",
    "r214-active-program-disambiguation.yml",
    "r218-transfer-governance.yml",
    "r219-autonomous-representation-discovery.yml",
    "r221-confidence-adaptive-evidence.yml",
    "r256-release-bundle.yml",
    "r259-budgeted-semantic-intervention-index.yml",
    "r262-release-bundle.yml",
    "r264-release-bundle.yml",
    "r265-post-merge-release-bundle.yml",
    "r266-post-merge-release-bundle.yml",
    "r267-1-post-merge-release-bundle.yml",
    "r268-post-merge-release-bundle.yml",
    "r269-post-merge-release-bundle.yml",
)


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


def test_wave5at_demonstrably_stale_historical_workflows_are_manual_only() -> None:
    workflows = ROOT / ".github" / "workflows"
    offenders: list[str] = []
    for name in _MANUAL_ONLY_POST_REFOUNDATION_WORKFLOWS:
        text = (workflows / name).read_text(encoding="utf-8")
        event_block = text.split("\njobs:", 1)[0]
        if "workflow_dispatch:" not in event_block:
            offenders.append(f"{name}:missing-workflow-dispatch")
        for automatic_event in ("push:", "pull_request:", "schedule:"):
            if f"\n  {automatic_event}" in event_block:
                offenders.append(f"{name}:automatic-{automatic_event[:-1]}")
    assert not offenders, offenders


def test_wave5at_archive_resolver_preserves_historical_lock_paths() -> None:
    from nolane.repository.audit import resolve_repository_path

    assert resolve_repository_path("cogcoder/r260_active_repository_probes.py", root=ROOT) == (
        "cogcoder/r260_active_repository_probes.py"
    )
    assert resolve_repository_path("R2_60_PHASE_A_RESULT.json", root=ROOT) == (
        "archive/root-history/historical_r_series/R2_60_PHASE_A_RESULT.json"
    )


def test_wave5at_r260_hosted_gate_uses_archive_aware_provenance_resolution() -> None:
    text = (ROOT / ".github" / "workflows" / "r260-active-repository-probes.yml").read_text(
        encoding="utf-8"
    )
    assert "resolve_repository_path" in text
    assert "HEAD:{resolved_path}" in text


def test_wave5as_current_status_records_repository_surface_closure() -> None:
    status = (ROOT / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")
    assert "Wave 5AS" in status
    assert "repository surface" in status.lower()
    assert "historical root artifacts" in status.lower()
