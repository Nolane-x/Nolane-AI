from __future__ import annotations

from pathlib import Path


def test_wave5ai_write_enabled_authority_carrier_is_absent() -> None:
    root = Path(__file__).resolve().parents[1]
    assert not (root / ".github" / "workflows" / "refoundation-wave5ai-authority-carrier.yml").exists()
