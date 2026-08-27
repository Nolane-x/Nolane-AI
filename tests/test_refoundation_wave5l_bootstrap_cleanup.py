from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_wave5l_temporary_authority_carrier_is_removed() -> None:
    assert not (ROOT / ".github/workflows/refoundation-wave5l-authority-carrier.yml").exists()
