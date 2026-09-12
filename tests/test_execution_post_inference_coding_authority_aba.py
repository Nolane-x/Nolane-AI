from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.coding_profiles import CodingDomain, CodingWorkRequest
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
    _git(source, "config", "user.email", "coding-authority-aba@example.invalid")
    _git(source, "config", "user.name", "Coding Authority ABA")
    (source / "README.md").write_text("coding authority ABA base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def _work_request(runtime: OrganizationRuntime, task_id: str) -> CodingWorkRequest:
    return CodingWorkRequest(
        work_id="work-request-bound-coding-authority-aba",
        task_id=task_id,
        plan_node_id="P1",
        requirement_refs=(),
        architecture_version=runtime.architecture.graph.version,
        plan_version=runtime.planning.graph.version,
        requested_domains=(CodingDomain.CROSS_SYSTEM,),
        scope_hints=("cross-system",),
        acceptance_refs=(),
        priority=80,
        requester_agent_id="coding.chief",
        evidence_refs=("coding-authority-aba-evidence",),
    )


def test_coding_assignment_aba_during_inference_rejects_before_persistence(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.get("coding.chief")
    task_id = "task-request-bound-coding-authority-aba"
    runtime.tasks.add_task(
        task_id,
        title="request-bound coding authority ABA",
        plan_node_id="P1",
    )
    runtime.tasks.lease(task_id, identity.agent_id)
    workspace = _workspace(tmp_path)
    work = _work_request(runtime, task_id)

    assignment_a = runtime.coding.request_work(
        work,
        override_agent_id="coding.chief",
        override_actor_id="nolane.central",
    )
    assert assignment_a.selected_agent_id == "coding.chief"
    initial_coding_digest = runtime.coding.digest
    observed_digests: dict[str, str] = {}

    class _CodingAuthorityABABackend:
        backend_id = "request-bound-coding-authority-aba-backend-v1"
        checkpoint_digest = "request-bound-coding-authority-aba-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            assignment_b = runtime.coding.request_work(
                work,
                override_agent_id="coding.backend.01",
                override_actor_id="nolane.central",
            )
            assert assignment_b.selected_agent_id == "coding.backend.01"
            observed_digests["middle"] = runtime.coding.digest

            assignment_a_again = runtime.coding.request_work(
                work,
                override_agent_id="coding.chief",
                override_actor_id="nolane.central",
            )
            assert assignment_a_again == assignment_a
            observed_digests["final"] = runtime.coding.digest

            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.wait(
                    reason="decision computed across reversible coding routing authority"
                ),
            )

    runtime.execution.bind_backend(identity.agent_id, _CodingAuthorityABABackend())
    session = runtime.execution.start(
        agent_id=identity.agent_id,
        task_id=task_id,
        workspace=workspace,
        action_schema=("filesystem.read_text",),
        budget=ExecutionBudget(
            max_steps=4,
            max_tool_calls=4,
            max_external_core_calls=4,
            max_compute_units=4,
        ),
    )

    try:
        execution_state_before = runtime.execution.to_state()
        session_before = runtime.execution.get_session(session.session_id)
        workspace_digest_before = workspace.digest

        with pytest.raises(
            PermissionError,
            match="context.*authority|authority.*artifact|coding",
        ):
            runtime.execution.step(session.session_id)

        assert observed_digests["middle"] != initial_coding_digest
        assert observed_digests["final"] != initial_coding_digest

        assert runtime.execution.to_state() == execution_state_before
        assert runtime.execution.get_session(session.session_id) == session_before
        current = runtime.execution.get_session(session.session_id)
        assert current.step_index == 0
        assert current.counters.steps == 0
        assert current.decision_receipt_ids == ()
        assert current.step_receipt_ids == ()
        assert current.terminal_receipt_id is None

        task = runtime.tasks.get(task_id)
        assert task.leased_to == identity.agent_id
        assert task.completed_by is None
        assert task.aborted_by is None

        assert workspace.digest == workspace_digest_before
        assert workspace.active_execution_epoch_id == session.workspace_epoch_id
        assert workspace.active_execution_epoch_owner == session.session_id
    finally:
        workspace.close()
