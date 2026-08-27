from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_wave5f_acceptance_has_no_write_enabled_temporary_workflows() -> None:
    temporary = (
        ROOT / ".github" / "workflows" / "refoundation-wave5f-bootstrap.yml",
        ROOT / ".github" / "workflows" / "refoundation-wave5f-bytecode-cleanup.yml",
    )
    present = [path.relative_to(ROOT).as_posix() for path in temporary if path.exists()]
    assert present == [], "temporary write-enabled Wave-5F workflows must be removed before acceptance: " + ", ".join(present)
