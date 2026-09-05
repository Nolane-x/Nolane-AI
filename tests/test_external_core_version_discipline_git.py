from __future__ import annotations

import subprocess
from pathlib import Path

from nolane.metadata.version_discipline import VersionDisciplineCode, check_git_revision_discipline


def _run(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def _write(repo: Path, path: str, text: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _fixture_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "init", "-q")
    _run(repo, "config", "user.email", "version-gate@example.invalid")
    _run(repo, "config", "user.name", "Version Gate")
    _write(
        repo,
        "nolane/metadata/_component_specs.py",
        'COMPONENT_SPECS = (("external.integration", "external_core", "integration", "integration-v1", ()), ("external.planning", "external_core", "planning", "planning-v1", ()))\n',
    )
    _write(
        repo,
        "nolane/metadata/component_versions.py",
        '_COMPONENT_REVISIONS = {component_id: 0 for component_id, *_ in COMPONENT_SPECS}\n_COMPONENT_REVISIONS.update({"external.integration": 1, "external.planning": 1})\n',
    )
    _write(repo, "nolane/external_core/integration.py", 'COMPONENT_ID = "external.integration"\nVALUE = 1\n')
    _write(repo, "nolane/external_core/planning.py", 'COMPONENT_ID = "external.planning"\nVALUE = 1\n')
    _run(repo, "add", ".")
    _run(repo, "commit", "-qm", "base")
    return repo, _run(repo, "rev-parse", "HEAD")


def _head(repo: Path, message: str = "head") -> str:
    _run(repo, "add", ".")
    _run(repo, "commit", "-qm", message)
    return _run(repo, "rev-parse", "HEAD")


def _codes(report) -> set[str]:
    return {row.code.value for row in report.findings}


def test_git_checker_rejects_changed_component_without_bump(tmp_path: Path) -> None:
    repo, base = _fixture_repo(tmp_path)
    _write(repo, "nolane/external_core/integration.py", 'COMPONENT_ID = "external.integration"\nVALUE = 2\n')
    report = check_git_revision_discipline(repo, base, _head(repo))
    assert _codes(report) == {VersionDisciplineCode.SEMANTIC_CHANGE_WITHOUT_REVISION.value}


def test_git_checker_accepts_exact_owner_bump(tmp_path: Path) -> None:
    repo, base = _fixture_repo(tmp_path)
    _write(repo, "nolane/external_core/integration.py", 'COMPONENT_ID = "external.integration"\nVALUE = 2\n')
    _write(
        repo,
        "nolane/metadata/component_versions.py",
        '_COMPONENT_REVISIONS = {component_id: 0 for component_id, *_ in COMPONENT_SPECS}\n_COMPONENT_REVISIONS.update({"external.integration": 2, "external.planning": 1})\n',
    )
    assert check_git_revision_discipline(repo, base, _head(repo)).clean


def test_git_checker_rejects_unrelated_bump(tmp_path: Path) -> None:
    repo, base = _fixture_repo(tmp_path)
    _write(repo, "nolane/external_core/integration.py", 'COMPONENT_ID = "external.integration"\nVALUE = 2\n')
    _write(
        repo,
        "nolane/metadata/component_versions.py",
        '_COMPONENT_REVISIONS = {component_id: 0 for component_id, *_ in COMPONENT_SPECS}\n_COMPONENT_REVISIONS.update({"external.integration": 1, "external.planning": 2})\n',
    )
    report = check_git_revision_discipline(repo, base, _head(repo))
    assert _codes(report) == {
        VersionDisciplineCode.SEMANTIC_CHANGE_WITHOUT_REVISION.value,
        VersionDisciplineCode.REVISION_WITHOUT_SEMANTIC_CHANGE.value,
    }


def test_git_checker_tracks_shared_helper_to_all_importing_roots(tmp_path: Path) -> None:
    repo, base = _fixture_repo(tmp_path)
    _write(repo, "nolane/external_core/_shared.py", "VALUE = 1\n")
    _write(repo, "nolane/external_core/integration.py", 'from nolane.external_core._shared import VALUE\nCOMPONENT_ID = "external.integration"\n')
    _write(repo, "nolane/external_core/planning.py", 'from nolane.external_core._shared import VALUE\nCOMPONENT_ID = "external.planning"\n')
    baseline = _head(repo, "shared base")
    _write(repo, "nolane/external_core/_shared.py", "VALUE = 2\n")
    report = check_git_revision_discipline(repo, baseline, _head(repo, "shared changed"))
    assert _codes(report) == {VersionDisciplineCode.SEMANTIC_CHANGE_WITHOUT_REVISION.value}
    assert {row.component_id for row in report.findings} == {"external.integration", "external.planning"}
