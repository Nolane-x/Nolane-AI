from pathlib import Path


def test_r27_workflow_uses_standalone_lock_verifier() -> None:
    workflow = Path('.github/workflows/r27-codeworld.yml').read_text(encoding='utf-8')
    assert 'python scripts/verify_r27_codeworld_phase_a_lock.py' in workflow
