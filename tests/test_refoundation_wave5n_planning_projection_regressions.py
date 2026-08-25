from __future__ import annotations

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.snapshot import OrganizationSnapshot
from cogcoder.organization.types import EventKind


def test_wave5n_task_creation_cannot_mutate_planning_projection() -> None:
    runtime = OrganizationRuntime.first_generation()

    assert runtime.planning.graph.version == runtime.tasks.plan_version == 0
    assert runtime.tasks.plan_nodes() == ()

    runtime.tasks.add_task(
        "task-projection-regression",
        title="Task projection regression",
        plan_node_id="plan-projection-regression",
    )

    assert runtime.planning.graph.version == runtime.tasks.plan_version == 0
    assert runtime.tasks.plan_nodes() == ()


def test_wave5n_plan_gap_proposal_does_not_advance_canonical_revision() -> None:
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task(
        "task-gap-regression",
        title="Gap regression",
        plan_node_id="plan-gap-regression",
    )

    proposal = runtime.report_plan_gap(
        source_agent_id="coding.backend.01",
        task_id="task-gap-regression",
        reason="A governed plan node is missing",
        suggested_nodes=("plan-gap-regression",),
        evidence_ids=("ev-gap-regression",),
    )

    assert proposal.kind is EventKind.PLAN_GAP_DETECTED
    assert runtime.planning.graph.version == runtime.tasks.plan_version == 0
    assert runtime.tasks.plan_nodes() == ()

    amendment = runtime.tasks.apply_plan_amendment(
        "planning.chief",
        proposal.event_id,
        added_nodes=("plan-gap-regression",),
    )

    assert amendment.kind is EventKind.PLAN_AMENDED
    assert runtime.planning.graph.version == runtime.tasks.plan_version == 1
    assert runtime.tasks.plan_nodes() == ("plan-gap-regression",)


def test_wave5n_task_only_state_round_trip_preserves_exact_runtime_digest() -> None:
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task(
        "task-snapshot-regression",
        title="Snapshot projection regression",
        plan_node_id="plan-snapshot-regression",
    )

    snapshot = OrganizationSnapshot.capture(runtime)
    restored = snapshot.restore()

    assert restored.tasks.to_state() == runtime.tasks.to_state()
    assert OrganizationSnapshot.capture(restored).digest == snapshot.digest
