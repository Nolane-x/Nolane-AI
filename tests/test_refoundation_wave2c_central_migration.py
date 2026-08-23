from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from cogcoder.refoundation.inventory import GitSnapshotInventory
from cogcoder.refoundation.manifests import FIRST_GENERATION_SNAPSHOT


EXPECTED_CENTRAL_DESTINATIONS = {
    "cogcoder/organization/central.py": "nolane/organization/central.py",
    "cogcoder/organization/central_access.py": "nolane/organization/central_access.py",
    "cogcoder/organization/central_conflicts.py": "nolane/organization/central_conflicts.py",
    "cogcoder/organization/central_resources.py": "nolane/organization/central_resources.py",
    "cogcoder/organization/central_state.py": "nolane/organization/central_state.py",
}


def test_native_central_keeps_exact_fail_closed_migration_destinations() -> None:
    census = GitSnapshotInventory.capture(Path.cwd(), FIRST_GENERATION_SNAPSHOT).to_census()
    for source, destination in EXPECTED_CENTRAL_DESTINATIONS.items():
        row = census.get(source)
        assert row.canonical_destination == destination
        assert not row.as_legacy_path_record().destructive_action_allowed


def test_central_legacy_imports_resolve_to_canonical_units_in_fresh_interpreter() -> None:
    code = "; ".join(
        (
            "from cogcoder.organization.central import CentralControlPlane",
            "from cogcoder.organization.central_access import CentralCoreAccessPolicy",
            "from cogcoder.organization.central_conflicts import CentralConflictRegistry",
            "from cogcoder.organization.central_resources import CentralResourceArbiter",
            "from cogcoder.organization.central_state import CentralCapabilityMap",
            "assert CentralControlPlane.__module__ == 'nolane.organization.central'",
            "assert CentralCoreAccessPolicy.__module__ == 'nolane.organization.central_access'",
            "assert CentralConflictRegistry.__module__ == 'nolane.organization.central_conflicts'",
            "assert CentralResourceArbiter.__module__ == 'nolane.organization.central_resources'",
            "assert CentralCapabilityMap.__module__ == 'nolane.organization.central_state'",
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
