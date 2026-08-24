from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_wave5g_acceptance_has_no_write_enabled_bootstrap_workflow() -> None:
    bootstrap = ROOT / ".github" / "workflows" / "refoundation-wave5g-bootstrap.yml"
    assert not bootstrap.exists(), "temporary write-enabled Wave-5G bootstrap must be removed before acceptance"
