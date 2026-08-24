from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_wave5h_temporary_bootstrap_workflow_is_absent() -> None:
    assert not (ROOT / ".github" / "workflows" / "refoundation-wave5h-bootstrap.yml").exists()
