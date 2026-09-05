from __future__ import annotations

import json

from nolane.metadata import version_discipline_cli
from nolane.metadata.version_discipline import VersionDisciplineReport


def test_cli_emits_deterministic_json_and_check_exit(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        version_discipline_cli,
        "check_git_revision_discipline",
        lambda repo_root, base, head: VersionDisciplineReport(()),
    )
    assert version_discipline_cli.main(["--base", "base", "--head", "head", "--json", "--check"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"clean": True, "findings": []}
