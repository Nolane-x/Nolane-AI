from __future__ import annotations

from pathlib import Path


def test_wave5aj_write_enabled_bootstrap_artifacts_are_absent() -> None:
    root = Path(__file__).resolve().parents[1]
    assert not (root / ".github" / "workflows" / "refoundation-wave5aj-authority-carrier.yml").exists()
    assert not (root / ".github" / "refoundation-wave5aj-trigger.txt").exists()
