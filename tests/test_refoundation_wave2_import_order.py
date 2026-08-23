from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_fresh(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path.cwd(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_legacy_native_bridges_import_cleanly_in_fresh_interpreter() -> None:
    completed = _run_fresh(
        "from cogcoder.organization.registry import AgentRegistry; "
        "from cogcoder.organization.authority import AuthorityGraph; "
        "from cogcoder.organization.events import EventLedger; "
        "assert AgentRegistry.__module__ == 'nolane.organization.identity'; "
        "assert AuthorityGraph.__module__ == 'nolane.organization.authority'; "
        "assert EventLedger.__module__ == 'nolane.organization.events'"
    )
    assert completed.returncode == 0, completed.stderr


def test_organization_package_root_keeps_runtime_api_lazy() -> None:
    completed = _run_fresh(
        "import sys; import nolane.organization as organization; "
        "assert 'nolane.organization.runtime' not in sys.modules; "
        "runtime_type = organization.OrganizationRuntime; "
        "build = organization.build_first_generation_runtime; "
        "assert 'nolane.organization.runtime' in sys.modules; "
        "assert runtime_type.__name__ == 'CanonicalOrganization'; "
        "assert callable(build)"
    )
    assert completed.returncode == 0, completed.stderr
