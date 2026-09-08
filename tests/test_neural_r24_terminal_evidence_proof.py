from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.execution_types import ExecutionBudget, InferenceRequest
from nolane.external_core.execution_workspace import RepositoryWorkspace


class _UnusedBackend:
    backend_id = "terminal-evidence-unused-backend-v1"
    checkpoint_digest = "terminal-evidence-unused-checkpoint-v1"

    def decide(self, request: InferenceRequest):
        raise AssertionError("terminal evidence fixture must terminate before inference")


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
    _git(source, "config", "user.email", "terminal-evidence@example.invalid")
    _git(source, "config", "user.name", "Terminal Evidence")
    (source / "README.md").write_text("terminal evidence base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def _terminal_runtime_state(tmp_path: Path) -> tuple[dict[str, Any], str]:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-terminal-evidence-proof"
    runtime.tasks.add_task(task_id, title="terminal evidence proof", plan_node_id="P1")
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
            reason="terminate before inference to isolate terminal evidence proof",
        )
        terminal = runtime.execution.step(session.session_id)
        assert terminal.receipt_id == runtime.execution.get_session(session.session_id).terminal_receipt_id
        return runtime.to_state(), session.session_id
    finally:
        workspace.close()


def _execution_rows(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    execution = state["execution"]
    assert len(execution["sessions"]) == 1
    assert len(execution["terminals"]) == 1
    return execution["sessions"][0], execution["terminals"][0]


def _terminal_evidence_rows(value: Any) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("kind") == "execution-terminal-evidence" and "artifact_id" in node:
                matches.append(node)
            for child in node.values():
                visit(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                visit(child)

    visit(value)
    return matches


def _terminal_evidence_row(state: dict[str, Any]) -> dict[str, Any]:
    matches = _terminal_evidence_rows(state)
    assert len(matches) == 1
    return matches[0]


def test_modern_terminal_binds_exact_terminal_evidence_artifact(tmp_path: Path) -> None:
    state, _ = _terminal_runtime_state(tmp_path)
    _session, terminal = _execution_rows(state)
    evidence = _terminal_evidence_row(state)

    assert terminal["execution_proof_version"] == 2
    assert terminal.get("terminal_evidence_artifact_id") == evidence["artifact_id"]
    assert terminal.get("terminal_evidence_digest") == evidence["digest"]


def test_restore_rejects_terminal_evidence_semantic_tampering(tmp_path: Path) -> None:
    state, _ = _terminal_runtime_state(tmp_path)
    _session, terminal = _execution_rows(state)
    evidence = _terminal_evidence_row(state)

    summary = json.loads(evidence["content"])
    summary["reason"] = "forged terminal evidence reason"
    evidence["content"] = json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    with pytest.raises(ValueError, match="terminal evidence|execution terminal evidence"):
        OrganizationRuntime.from_state(state)

    assert terminal["execution_proof_version"] == 2


def test_restore_rejects_terminal_evidence_binding_downgrade(tmp_path: Path) -> None:
    state, _ = _terminal_runtime_state(tmp_path)
    _session, terminal = _execution_rows(state)

    terminal.pop("terminal_evidence_artifact_id", None)
    terminal.pop("terminal_evidence_digest", None)

    with pytest.raises(ValueError, match="terminal evidence|execution terminal evidence"):
        OrganizationRuntime.from_state(state)
