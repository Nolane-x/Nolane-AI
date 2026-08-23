from __future__ import annotations

from pathlib import Path

from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT


def test_pinned_snapshot_inventory_reads_exact_git_tree() -> None:
    inventory = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT)
    paths = {row.path for row in inventory.entries}

    assert inventory.source_snapshot_sha == FIRST_GENERATION_SNAPSHOT
    assert len(paths) == len(inventory.entries)
    assert {
        "cogcoder/organization/blueprint.py",
        "cogcoder/organization/runtime.py",
        "cogcoder/organization/runtime_part15.py",
        "cogcoder/organization/execution.py",
        "CURRENT_STATUS.md",
        ".github/workflows/coding-agi-execution-bridge.yml",
    }.issubset(paths)
    assert len(inventory.digest) == 64


def test_generated_census_has_one_record_for_every_pinned_tracked_leaf() -> None:
    inventory = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT)
    census = inventory.to_census()
    report = census.coverage(row.path for row in inventory.entries)

    assert report.complete
    assert report.coverage_ratio == 1.0
    assert len(census.records()) == len(inventory.entries)


def test_active_facade_and_native_sources_receive_exact_canonical_destinations() -> None:
    census = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT).to_census()

    assert census.get("cogcoder/organization/runtime.py").canonical_destination == "nolane/runtime/__init__.py"
    assert census.get("cogcoder/organization/memory.py").canonical_destination == "nolane/memory/fabric.py"
    assert census.get("cogcoder/organization/execution_inference.py").canonical_destination == "nolane/neural/inference_bridge.py"
    assert census.get("cogcoder/organization/evaluation_claims.py").canonical_destination == "nolane/evaluation/claims.py"


def test_unfacaded_legacy_source_remains_non_destructive() -> None:
    census = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT).to_census()
    row = census.get("cogcoder/organization/runtime_part15.py")
    assert not row.as_legacy_path_record().destructive_action_allowed


def test_generated_inventory_is_zero_loss_fail_closed_by_default() -> None:
    inventory = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT)
    census = inventory.to_census()

    for record in census.records():
        assert not record.as_legacy_path_record().destructive_action_allowed


def test_git_inventory_digest_is_deterministic() -> None:
    first = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT)
    second = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT)
    assert first.digest == second.digest
