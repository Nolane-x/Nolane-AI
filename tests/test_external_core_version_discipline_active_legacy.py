from __future__ import annotations

import subprocess
from pathlib import Path

from nolane.metadata.version_discipline import check_git_revision_discipline


def _run(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def _write(repo: Path, path: str, text: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _commit(repo: Path, message: str) -> str:
    _run(repo, "add", ".")
    _run(repo, "commit", "-qm", message)
    return _run(repo, "rev-parse", "HEAD")


def test_git_checker_tracks_explicit_active_legacy_semantic_surface(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "init", "-q")
    _run(repo, "config", "user.email", "version-gate@example.invalid")
    _run(repo, "config", "user.name", "Version Gate")

    _write(
        repo,
        "nolane/metadata/_component_specs.py",
        'COMPONENT_SPECS = (("external.architecture", "external_core", "architecture + ADR", "architecture-v1", ()),)\n',
    )
    _write(
        repo,
        "nolane/metadata/component_versions.py",
        '_COMPONENT_REVISIONS = {component_id: 0 for component_id, *_ in COMPONENT_SPECS}\n'
        '_COMPONENT_REVISIONS.update({"external.architecture": 5})\n',
    )
    _write(
        repo,
        "nolane/external_core/architecture.py",
        'COMPONENT_ID = "external.architecture"\nCOMPONENT_VERSION = "0.0.2"\nVALUE = 1\n',
    )
    _write(
        repo,
        "cogcoder/organization/adr.py",
        'COMPONENT_ID = "external.architecture"\nVALUE = 1\n',
    )
    base = _commit(repo, "base")

    _write(
        repo,
        "cogcoder/organization/adr.py",
        'COMPONENT_ID = "external.architecture"\nVALUE = 2\n',
    )
    _write(
        repo,
        "nolane/metadata/component_versions.py",
        '_COMPONENT_REVISIONS = {component_id: 0 for component_id, *_ in COMPONENT_SPECS}\n'
        '_COMPONENT_REVISIONS.update({"external.architecture": 6})\n',
    )
    head = _commit(repo, "active legacy ADR change")

    report = check_git_revision_discipline(repo, base, head)
    assert report.clean, report.to_state()
