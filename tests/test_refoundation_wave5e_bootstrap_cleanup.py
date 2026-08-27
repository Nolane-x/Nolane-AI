from pathlib import Path


def test_wave5e_acceptance_has_no_write_enabled_bootstrap_workflows() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden = (
        root / ".github" / "workflows" / "refoundation-wave5e-bootstrap.yml",
        root / ".github" / "workflows" / "refoundation-wave5e-crosswave-fix.yml",
    )
    present = [str(path.relative_to(root)) for path in forbidden if path.exists()]
    assert not present, f"temporary write-enabled Wave-5E workflows must be removed before acceptance: {present}"
