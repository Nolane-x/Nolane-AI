from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_wave5h_temporary_workflows_are_absent() -> None:
    workflows = ROOT / ".github" / "workflows"
    assert not (workflows / "refoundation-wave5h-bootstrap.yml").exists()
    assert not (workflows / "refoundation-wave5h-audit-refresh.yml").exists()
