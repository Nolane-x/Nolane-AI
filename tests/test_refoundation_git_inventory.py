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


def test_generated_inventory_is_zero_loss_fail_closed_by_default() -> None:
    inventory = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT)
    census = inventory.to_census()

    for record in census.records():
        # Inventory coverage is not permission to delete. Classification and
        # parity/migration/history receipts remain separate requirements.
        assert not record.as_legacy_path_record().destructive_action_allowed


def test_git_inventory_digest_is_deterministic() -> None:
    first = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT)
    second = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT)
    assert first.digest == second.digest
