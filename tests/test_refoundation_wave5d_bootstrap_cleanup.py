from pathlib import Path


def test_wave5d_acceptance_has_no_write_enabled_bootstrap_workflow() -> None:
    root = Path(__file__).resolve().parents[1]
    bootstrap = root / ".github" / "workflows" / "refoundation-wave5d-bootstrap.yml"
    assert not bootstrap.exists(), "temporary write-enabled Wave-5D bootstrap must be removed before acceptance"
