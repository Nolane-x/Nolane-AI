from __future__ import annotations

import json

import nolane.external_core.integration_admission_bundle as admission_bundle


def test_canonical_cli_json_executes_current_a10_v4_observation_audit(capsys) -> None:
    assert admission_bundle._main(["--json", "--observed-epoch", "7"]) == 0
    state = json.loads(capsys.readouterr().out)

    assert state["protocol"] == "external-integration-admission-audit-v4"
    assert state["observation_digest"].startswith("canonical-observation-v1-")
    assert state["findings"] == []
    assert state["digest"].startswith("admission-audit-v4-")


def test_canonical_cli_help_names_the_a10_v1_audit(capsys) -> None:
    try:
        admission_bundle._main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    help_text = capsys.readouterr().out
    assert "A10" in help_text
    assert "External Core v1" in help_text
    assert "A7" not in help_text
