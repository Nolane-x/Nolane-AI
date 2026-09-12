from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.evidence import EvidenceRecord
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionBudget,
    InferenceRequest,
)
from nolane.external_core.execution_workspace import RepositoryWorkspace
from nolane.external_core.integration import ChangeCandidate
from nolane.external_core.planning import PlanNode
from nolane.memory.skills import SkillScope


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
    _git(source, "config", "user.email", "context-frontier-authority@example.invalid")
    _git(source, "config", "user.name", "Context Frontier Authority")
    (source / "README.md").write_text("context frontier authority base\n", encoding="utf-8")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "base")
    return RepositoryWorkspace.create(
        source_repo=source,
        revision="HEAD",
        workspace_root=tmp_path / "workspace",
    )


def _promoted_personal_skill(runtime: OrganizationRuntime, owner_agent_id: str):
    owner = runtime.registry.get(owner_agent_id)
    skill = runtime.evolution.propose(
        owner_agent_id=owner.agent_id,
        region=owner.region,
        name="request-bound-skill-frontier",
        body="a skill used by inference must remain authorized until its decision is persisted",
    )
    evidence = EvidenceRecord(
        "skill-frontier-independent-verification",
        "memory.context-compiler.01",
        True,
        false_accepts=0,
        regressions=0,
    )
    authority = runtime.learning_substrate.learning_authority
    lease = authority.issue(
        subject_kind="skill",
        subject_id=skill.skill_id,
        operation_class="skill.verify",
        producer_agent_id=skill.owner_agent_id,
        evidence=evidence,
        subject_digest=runtime.evolution.verification_subject_digest(skill.skill_id),
    )
    runtime.evolution.verify(
        skill.skill_id,
        evidence,
        authority_lease_id=lease.lease_id,
    )
    runtime.learning_substrate.record_skill_validation(
        skill.skill_id,
        regression_evidence_ids=("skill-frontier-regression-a", "skill-frontier-regression-b"),
        causal_ablation_evidence_ids=("skill-frontier-causal-ablation",),
        regression_evidence_families={
            "skill-frontier-regression-a": "skill-frontier-family-a",
            "skill-frontier-regression-b": "skill-frontier-family-b",
        },
        causal_ablation_evidence_families={
            "skill-frontier-causal-ablation": "skill-frontier-causal-family",
        },
    )
    return runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)


def test_completion_revalidates_authoritative_context_frontier_after_inference_before_persisting_decision(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-post-inference-context-frontier"

    runtime.planning.apply_revision(
        actor_agent_id="nolane.central",
        reason="establish authoritative execution plan",
        evidence_refs=("context-frontier-initial-plan",),
        upsert_nodes=(PlanNode("P1", "authoritative execution plan"),),
    )
    initial_plan_version = runtime.planning.graph.version

    runtime.tasks.add_task(task_id, title="context frontier authority", plan_node_id="P1")
    runtime.tasks.lease(task_id, identity.agent_id)
    workspace = _workspace(tmp_path)

    class _PlanMutatingCompletionBackend:
        backend_id = "post-inference-context-frontier-backend-v1"
        checkpoint_digest = "post-inference-context-frontier-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            runtime.planning.apply_revision(
                actor_agent_id="nolane.central",
                reason="change governing plan during inference",
                evidence_refs=("context-frontier-plan-amendment",),
                upsert_nodes=(PlanNode("P1", "amended authoritative execution plan"),),
            )
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.complete(
                    reason="stale completion after authoritative context frontier changed",
                ),
            )

    runtime.execution.bind_backend(identity.agent_id, _PlanMutatingCompletionBackend())
    session = runtime.execution.start(
        agent_id=identity.agent_id,
        task_id=task_id,
        workspace=workspace,
        action_schema=("filesystem.read_text",),
        budget=ExecutionBudget(
            max_steps=8,
            max_tool_calls=8,
            max_external_core_calls=8,
            max_compute_units=8,
        ),
    )

    try:
        session_before = runtime.execution.get_session(session.session_id)
        execution_before = runtime.execution.to_state()
        workspace_digest_before = workspace.digest

        with pytest.raises(
            (RuntimeError, ValueError, PermissionError),
            match="context.*frontier|authoritative.*frontier|plan.*authority|context.*authority",
        ):
            runtime.execution.step(session.session_id)

        assert runtime.planning.graph.version == initial_plan_version + 1
        assert runtime.planning.graph.get("P1").title == "amended authoritative execution plan"

        task = runtime.tasks.get(task_id)
        assert task.completed_by is None
        assert task.aborted_by is None
        assert task.leased_to == identity.agent_id

        assert runtime.execution.get_session(session.session_id) == session_before
        assert runtime.execution.to_state() == execution_before
        assert runtime.execution.get_session(session.session_id).decision_receipt_ids == ()
        assert runtime.execution.get_session(session.session_id).step_receipt_ids == ()
        assert runtime.execution.get_session(session.session_id).terminal_receipt_id is None
        assert runtime.execution.terminal_receipts() == ()

        assert workspace.digest == workspace_digest_before
        assert workspace.active_execution_epoch_id == session.workspace_epoch_id
        assert workspace.active_execution_epoch_owner == session.session_id
    finally:
        workspace.close()


def test_integration_authority_change_during_inference_rejects_before_persistence(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.identities()[0]
    task_id = "task-request-bound-context-integration-authority"
    runtime.tasks.add_task(
        task_id,
        title="request-bound context integration authority",
        plan_node_id="P1",
    )
    runtime.tasks.lease(task_id, identity.agent_id)
    workspace = _workspace(tmp_path)
    integration_version_before = runtime.integration.graph.version

    class _IntegrationMutatingBackend:
        backend_id = "request-bound-context-integration-authority-backend-v1"
        checkpoint_digest = "request-bound-context-integration-authority-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            runtime.integration.add_candidate(
                actor_agent_id="integration.chief",
                candidate=ChangeCandidate(
                    candidate_id="candidate-request-bound-context-authority",
                    producer_agent_id="integration.chief",
                    task_refs=(task_id,),
                    plan_refs=(),
                    requirement_refs=(),
                    architecture_version_expected=runtime.architecture.graph.version,
                    changed_component_refs=(),
                    changed_interface_refs=(),
                ),
            )
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.wait(
                    reason="stale decision after request-bound integration authority changed"
                ),
            )

    runtime.execution.bind_backend(identity.agent_id, _IntegrationMutatingBackend())
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
            match="context.*authority|authority.*artifact|artifact.*authority",
        ):
            runtime.execution.step(session.session_id)

        assert runtime.integration.graph.version == integration_version_before + 1
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


def test_skill_quarantine_during_inference_rejects_before_persistence(
    tmp_path: Path,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.get("memory.chief")
    skill = _promoted_personal_skill(runtime, identity.agent_id)
    assert tuple(
        row.skill_id
        for row in runtime.evolution.skills_for(identity.agent_id, region=identity.region)
    ) == (skill.skill_id,)

    task_id = "task-request-bound-skill-frontier-authority"
    runtime.tasks.add_task(
        task_id,
        title="request-bound skill frontier authority",
        plan_node_id="P1",
    )
    runtime.tasks.lease(task_id, identity.agent_id)
    workspace = _workspace(tmp_path)

    class _SkillRevokingBackend:
        backend_id = "request-bound-skill-frontier-authority-backend-v1"
        checkpoint_digest = "request-bound-skill-frontier-authority-checkpoint-v1"

        def decide(self, request: InferenceRequest) -> AgentDecisionReceipt:
            runtime.evolution.quarantine(
                skill.skill_id,
                reason="revoke an applicable skill while inference is in flight",
            )
            return AgentDecisionReceipt.create(
                backend_id=self.backend_id,
                request=request,
                action=ExecutionAction.wait(
                    reason="decision computed from a skill that is no longer authorized",
                ),
            )

    runtime.execution.bind_backend(identity.agent_id, _SkillRevokingBackend())
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
            match="context.*authority|skill.*frontier|authority.*artifact",
        ):
            runtime.execution.step(session.session_id)

        assert runtime.evolution.get(skill.skill_id).quarantined is True
        assert runtime.evolution.skills_for(identity.agent_id, region=identity.region) == ()
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


def test_public_memory_context_authority_snapshot_matches_actual_compiled_memory_capsule_without_side_effects() -> None:
    runtime = OrganizationRuntime.first_generation()
    identity = runtime.registry.get("memory.chief")

    authority_before = dict(
        runtime.memory_context.authoritative_artifacts(identity.agent_id)
    )["memory-intelligence-state"]
    full_digest_before = runtime.memory_context.digest

    compiled = runtime.memory_context.compile_context(identity.agent_id)
    capsule = compiled.capsule

    assert runtime.memory_context.digest != full_digest_before

    state_before_snapshot = runtime.memory_context.to_state()
    snapshot = runtime.memory_context.authoritative_artifacts(
        identity.agent_id,
        task_id=capsule.task_id,
    )

    assert snapshot == tuple(capsule.authoritative_artifacts)
    assert dict(snapshot)["memory-intelligence-state"] == authority_before
    assert runtime.memory_context.to_state() == state_before_snapshot
