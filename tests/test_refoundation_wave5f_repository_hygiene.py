from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_wave5f_repository_tracks_no_python_bytecode() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    offenders = sorted(
        path
        for path in tracked
        if path.endswith(".pyc") or "/__pycache__/" in f"/{path}"
    )
    assert offenders == [], "tracked Python bytecode is forbidden: " + "; ".join(offenders)
