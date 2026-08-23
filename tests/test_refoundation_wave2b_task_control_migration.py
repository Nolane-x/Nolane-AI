from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT


EXPECTED_DESTINATIONS = {
    "cogcoder/organization/tasks.py": "nolane/organization/tasks.py",
    "cogcoder/organization/scheduler.py": "nolane/organization/lifecycle.py",
    "cogcoder/organization/coordination_leases.py": "nolane/organization/coordination_leases.py",
    "cogcoder/organization/coordination_delivery.py": "nolane/organization/coordination_delivery.py",
    "cogcoder/organization/coordination_conflicts.py": "nolane/organization/coordination_conflicts.py",
    "cogcoder/organization/coordination.py": "nolane/organization/coordination.py",
}


def test_native_task_control_keeps_exact_migration_destinations() -> None:
    census = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT).to_census()
    for source, destination in EXPECTED_DESTINATIONS.items():
        assert census.get(source).canonical_destination == destination
        assert not census.get(source).as_legacy_path_record().destructive_action_allowed


def test_task_control_legacy_bridges_import_cleanly_in_fresh_interpreter() -> None:
    code = "; ".join(
        (
            "from cogcoder.organization.tasks import TaskGraph",
            "from cogcoder.organization.scheduler import WakeSleepScheduler",
            "from cogcoder.organization.coordination_leases import LeaseCoordinator",
            "from cogcoder.organization.coordination_delivery import DeliveryCoordinator",
            "from cogcoder.organization.coordination_conflicts import ConflictCoordinator",
            "from cogcoder.organization.coordination import CoordinationControlPlane",
            "assert TaskGraph.__module__ == 'nolane.organization.tasks'",
            "assert WakeSleepScheduler.__module__ == 'nolane.organization.lifecycle'",
            "assert LeaseCoordinator.__module__ == 'nolane.organization.coordination_leases'",
            "assert DeliveryCoordinator.__module__ == 'nolane.organization.coordination_delivery'",
            "assert ConflictCoordinator.__module__ == 'nolane.organization.coordination_conflicts'",
            "assert CoordinationControlPlane.__module__ == 'nolane.organization.coordination'",
        )
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path.cwd(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
