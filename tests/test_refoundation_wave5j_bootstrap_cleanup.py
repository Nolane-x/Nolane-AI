from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_wave5j_temporary_authority_carrier_is_absent() -> None:
    assert not (ROOT / ".github/workflows/refoundation-wave5j-authority.yml").exists()
