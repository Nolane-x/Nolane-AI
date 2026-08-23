from __future__ import annotations

import pytest

from cogcoder.organization.planning import PlanNode
from cogcoder.refoundation.canonical_runtime import CanonicalOrganization


def test_canonical_runtime_does_not_publish_raw_taskgraph_write_surface() -> None:
    runtime = CanonicalOrganization.first_generation()
    assert not hasattr(runtime, "tasks")
    assert not hasattr(runtime, "planning")
    assert runtime.plan_revision == 0
    assert len(runtime.identities()) == 67


def test_task_creation_requires_an_authoritative_master_plan_node() -> None:
    runtime = CanonicalOrganization.first_generation()
    with pytest.raises(KeyError):
        runtime.add_task("task-1", title="orphan", plan_node_id="plan-1")

    revision = runtime.apply_plan_revision(
        actor_agent_id="planning.chief",
        reason="canonical task root",
        evidence_refs=("evidence-plan-1",),
        upsert_nodes=(PlanNode("plan-1", "Canonical plan root"),),
    )
    assert revision.version == 1
    task = runtime.add_task("task-1", title="bound task", plan_node_id="plan-1")
    assert task.plan_node_id == "plan-1"
    assert runtime.plan_revision == 1


def test_lease_completion_path_is_authoritative_through_lease_coordinator() -> None:
    runtime = CanonicalOrganization.first_generation()
    runtime.apply_plan_revision(
        actor_agent_id="planning.chief",
        reason="lease test",
        evidence_refs=("evidence-plan",),
        upsert_nodes=(PlanNode("plan-1", "Lease plan"),),
    )
    runtime.add_task("task-1", title="lease task", plan_node_id="plan-1")

    lease = runtime.grant_task_lease(
        "task-1",
        "coding.backend.01",
        token=4,
        evidence_refs=("evidence-lease",),
    )
    assert runtime.current_task_lease("task-1").lease_id == lease.lease_id
    assert runtime.task("task-1").leased_to == "coding.backend.01"

    renewed = runtime.heartbeat_task_lease(
        "task-1",
        "coding.backend.01",
        lease_id=lease.lease_id,
        epoch=lease.epoch,
        token=5,
    )
    assert renewed.renewal_count == 1

    completed = runtime.complete_task(
        "task-1",
        "coding.backend.01",
        lease_id=lease.lease_id,
        epoch=lease.epoch,
        output_artifact_ids=("artifact-1",),
    )
    assert completed.completed_by == "coding.backend.01"
    with pytest.raises(KeyError):
        runtime.current_task_lease("task-1")


def test_canonical_runtime_state_is_roundtrippable_through_accepted_state_loader() -> None:
    runtime = CanonicalOrganization.first_generation()
    state = runtime.to_state()
    restored = CanonicalOrganization.from_state(state)
    assert restored.to_state() == state
    assert restored.identity_source == "canonical-manifests"
