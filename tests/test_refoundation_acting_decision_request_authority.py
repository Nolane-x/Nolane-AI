from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionBudget,
    InferenceRequest,
)
from nolane.external_core.execution_workspace import RepositoryWorkspace


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
    _git(source, "config", "user.email", "decision-authority@example.invalid")
    _git(source, "config", "user.name", "Decision Authority")
    (source / "README.md").write_text("base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def _forge_receipt(receipt: AgentDecisionReceipt, field: str) -> AgentDecisionReceipt:
    replacements: dict[str, object] = {
        "request_digest": "0" * 64,
        "agent_id": "agent-substituted",
        "backend_id": "backend-substituted",
        "neural_version": "neural-substituted",
        "checkpoint_digest": "checkpoint-substituted",
        "encoder_version": "encoder-substituted",
        "context_digest": "1" * 64,
        "action_schema_digest": "2" * 64,
        "step_index": receipt.step_index + 1,
    }
    forged = replace(receipt, **{field: replacements[field]}, receipt_id="", digest="")
    digest = canonical_digest(forged.payload())
    forged = replace(forged, receipt_id="decision-" + digest[:24], digest=digest)
    # Prove the hostile object is internally canonical. The rejection under test
    # must therefore come from current-request authority re-attestation, not from
    # receipt self-integrity validation.
    assert AgentDecisionReceipt.from_state(forged.to_state()) == forged
    return forged


class _SubstitutingDecisionBackend:
    backend_id = "decision-authority-fixture-v1"
    checkpoint_digest = "decision-authority-checkpoint-v1"

    def __init__(self, mismatch: str) -> None:
        self.mismatch = mismatch
        self.calls = 0

    def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
        self.calls += 1
        canonical = AgentDecisionReceipt.create(
            backend_id=self.backend_id,
            request=request,
            action=ExecutionAction.complete(reason="hostile receipt must never gain authority"),
        )
        return _forge_receipt(canonical, self.mismatch)


class _StaleRequestBackend:
    backend_id = "stale-request-fixture-v1"
    checkpoint_digest = "stale-request-checkpoint-v1"

    def __init__(self) -> None:
        self.calls = 0

    def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
        self.calls += 1
        stale = replace(
            request,
            context_digest=canonical_digest(
                {"source": "different inference request", "live": request.context_digest}
            ),
        )
        return AgentDecisionReceipt.create(
            backend_id=self.backend_id,
            request=stale,
            action=ExecutionAction.complete(reason="stale request receipt must never gain authority"),
        )


def _start_runtime(tmp_path: Path, backend: object):
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-decision-request-authority"
    runtime.tasks.add_task(task_id, title="decision request authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)
    workspace = _workspace(tmp_path)
    runtime.execution.bind_backend(identity.agent_id, backend)  # type: ignore[arg-type]
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
    return runtime, workspace, session


@pytest.mark.parametrize(
    "mismatch",
    (
        "request_digest",
        "agent_id",
        "backend_id",
        "neural_version",
        "checkpoint_digest",
        "encoder_version",
        "context_digest",
        "action_schema_digest",
        "step_index",
    ),
)
def test_control_plane_rejects_self_consistent_decision_receipt_not_bound_to_live_request(
    tmp_path: Path,
    mismatch: str,
) -> None:
    backend = _SubstitutingDecisionBackend(mismatch)
    runtime, workspace, session = _start_runtime(tmp_path, backend)
    before_control = runtime.execution.to_state()
    before_workspace = workspace.digest
    try:
        with pytest.raises(ValueError, match="decision receipt authority mismatch"):
            runtime.execution.step(session.session_id)

        assert backend.calls == 1
        assert runtime.execution.to_state() == before_control
        assert runtime.execution.get_session(session.session_id) == session
        assert workspace.digest == before_workspace
    finally:
        workspace.close()


def test_control_plane_rejects_receipt_copied_from_different_inference_request_before_state_change(
    tmp_path: Path,
) -> None:
    backend = _StaleRequestBackend()
    runtime, workspace, session = _start_runtime(tmp_path, backend)
    before_control = runtime.execution.to_state()
    before_workspace = workspace.digest
    try:
        with pytest.raises(ValueError, match="decision receipt authority mismatch"):
            runtime.execution.step(session.session_id)

        assert backend.calls == 1
        assert runtime.execution.to_state() == before_control
        assert runtime.execution.get_session(session.session_id) == session
        assert workspace.digest == before_workspace
    finally:
        workspace.close()
