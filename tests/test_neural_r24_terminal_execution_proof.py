from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution_types import ExecutionBudget, InferenceRequest
from nolane.external_core.execution_workspace import RepositoryWorkspace


class _UnusedBackend:
    backend_id = "terminal-proof-unused-backend-v1"
    checkpoint_digest = "terminal-proof-unused-checkpoint-v1"

    def decide(self, request: InferenceRequest):
        raise AssertionError("terminal proof fixture must terminate before inference")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def _workspace(tmp_path: Path) -> RepositoryWorkspace:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init")
    _git(source, "config", "user.email", "terminal-proof@example.invalid")
    _git(source, "config", "user.name", "Terminal Proof")
    (source / "README.md").write_text("terminal proof base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def _terminal_runtime_state(tmp_path: Path) -> tuple[dict, str]:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-terminal-execution-proof"
    runtime.tasks.add_task(task_id, title="terminal execution proof", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)
    workspace = _workspace(tmp_path)
    try:
        runtime.execution.bind_backend(identity.agent_id, _UnusedBackend())
        session = runtime.execution.start(
            agent_id=identity.agent_id,
            task_id=task_id,
            workspace=workspace,
            action_schema=("complete",),
            budget=ExecutionBudget(
                max_steps=2,
                max_tool_calls=1,
                max_external_core_calls=1,
                max_compute_units=2,
            ),
        )
        runtime.tasks.abort(
            task_id,
            "nolane.central",
            reason="terminate before inference to isolate terminal proof",
        )
        terminal = runtime.execution.step(session.session_id)
        assert terminal.receipt_id == runtime.execution.get_session(session.session_id).terminal_receipt_id
        return runtime.to_state(), session.session_id
    finally:
        workspace.close()


def _execution_rows(state: dict) -> tuple[dict, dict]:
    execution = state["execution"]
    assert len(execution["sessions"]) == 1
    assert len(execution["terminals"]) == 1
    return execution["sessions"][0], execution["terminals"][0]


def _strip_terminal_proof(terminal: dict, session: dict) -> None:
    for field in (
        "execution_proof_version",
        "initial_workspace_digest",
        "current_workspace_digest",
        "external_core_registry_digest",
        "workspace_epoch_id",
        "terminal_evidence_artifact_id",
        "terminal_evidence_digest",
    ):
        terminal.pop(field, None)
    payload = {
        key: value
        for key, value in terminal.items()
        if key not in {"receipt_id", "digest"}
    }
    digest = canonical_digest(payload)
    terminal["digest"] = digest
    terminal["receipt_id"] = "terminal-" + digest[:24]
    session["terminal_receipt_id"] = terminal["receipt_id"]


def _strip_session_proof(session: dict) -> None:
    for field in (
        "workspace_provenance_version",
        "initial_workspace_digest",
        "current_workspace_digest",
        "execution_proof_version",
        "external_core_registry_digest",
        "workspace_epoch_id",
    ):
        session.pop(field, None)


def test_modern_terminal_persists_exact_execution_proof_v2(tmp_path: Path) -> None:
    state, _ = _terminal_runtime_state(tmp_path)
    session, terminal = _execution_rows(state)

    assert session["execution_proof_version"] == 2
    assert terminal.get("execution_proof_version") == 2
    assert terminal.get("initial_workspace_digest") == session["initial_workspace_digest"]
    assert terminal.get("current_workspace_digest") == session["current_workspace_digest"]
    assert terminal.get("external_core_registry_digest") == session["external_core_registry_digest"]
    assert terminal.get("workspace_epoch_id") == session["workspace_epoch_id"]


@pytest.mark.parametrize("forgery", ("workspace", "epoch"))
def test_restore_rejects_self_consistent_terminal_session_proof_rebinding(
    tmp_path: Path,
    forgery: str,
) -> None:
    state, _ = _terminal_runtime_state(tmp_path)
    session, _terminal = _execution_rows(state)

    if forgery == "workspace":
        forged = canonical_digest({"forged": "terminal workspace proof"})
        session["initial_workspace_digest"] = forged
        session["current_workspace_digest"] = forged
    else:
        session["workspace_epoch_id"] = "workspace-epoch-forged-terminal-proof"

    with pytest.raises(ValueError, match="terminal.*proof|execution terminal proof"):
        OrganizationRuntime.from_state(state)


def test_restore_rejects_self_consistent_terminal_proof_v2_to_v1_downgrade(
    tmp_path: Path,
) -> None:
    state, _ = _terminal_runtime_state(tmp_path)
    session, terminal = _execution_rows(state)
    _strip_terminal_proof(terminal, session)

    with pytest.raises(ValueError, match="terminal.*proof|execution terminal proof"):
        OrganizationRuntime.from_state(state)


def test_restore_keeps_true_historical_terminal_v1_readable(tmp_path: Path) -> None:
    state, session_id = _terminal_runtime_state(tmp_path)
    session, terminal = _execution_rows(state)
    _strip_terminal_proof(terminal, session)
    _strip_session_proof(session)

    restored = OrganizationRuntime.from_state(state)
    restored_session = restored.execution.get_session(session_id)
    restored_terminal = restored.execution.get_terminal_receipt(restored_session.terminal_receipt_id)
    restored_terminal_state = restored_terminal.to_state()
    assert "execution_proof_version" not in restored_terminal_state
    assert "workspace_epoch_id" not in restored_terminal_state
    assert "terminal_evidence_artifact_id" not in restored_terminal_state
    assert "terminal_evidence_digest" not in restored_terminal_state
