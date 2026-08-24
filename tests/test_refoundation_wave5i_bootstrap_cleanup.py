from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_wave5i_temporary_authority_workflow_is_absent() -> None:
    assert not (
        ROOT / ".github" / "workflows" / "refoundation-wave5i-authority.yml"
    ).exists()
