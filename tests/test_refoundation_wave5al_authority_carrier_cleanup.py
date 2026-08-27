from pathlib import Path


def test_wave5al_write_enabled_authority_carrier_is_not_part_of_accepted_tree() -> None:
    root = Path(__file__).resolve().parents[1]
    carrier = root / ".github" / "workflows" / "refoundation-wave5al-authority-carrier.yml"
    assert not carrier.exists()
