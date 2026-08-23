from __future__ import annotations

from cogcoder.organization.authority import AuthorityGraph
from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.coordination_leases import LeaseCoordinator
from cogcoder.organization.events import EventLedger
from cogcoder.organization.planning import PlanningControlPlane
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.requirements import RequirementsControlPlane
from cogcoder.organization.tasks import TaskGraph
from cogcoder.refoundation.reconciliation import (
    CanonicalAuthorityTarget,
    RefoundationAuthorityAuditor,
)


def _substrate():
    registry = AgentRegistry(build_first_generation_blueprint())
    events = EventLedger()
    authority = AuthorityGraph(registry)
    authority.claim_owner("requirements", "requirements.chief")
    authority.claim_owner("master-plan", "planning.chief")
    tasks = TaskGraph(ledger=events, registry=registry, authority=authority)
    requirements = RequirementsControlPlane(registry=registry, authority=authority, ledger=events)
    planning = PlanningControlPlane(
        registry=registry,
        authority=authority,
        ledger=events,
        tasks=tasks,
        requirements=requirements,
    )
    leases = LeaseCoordinator(registry=registry, tasks=tasks, events=events)
    return registry, events, authority, tasks, planning, leases


def test_auditor_declares_master_plan_and_lease_coordinator_as_cutover_targets() -> None:
    *_, tasks, planning, leases = _substrate()
    report = RefoundationAuthorityAuditor(tasks=tasks, planning=planning, leases=leases).audit()

    assert report.plan_target is CanonicalAuthorityTarget.MASTER_PLAN_GRAPH
    assert report.lease_target is CanonicalAuthorityTarget.LEASE_COORDINATOR
    assert report.destructive_cutover_allowed is False


def test_fresh_legacy_runtime_exposes_historical_plan_clock_offset_without_mutation() -> None:
    *_, tasks, planning, leases = _substrate()
    report = RefoundationAuthorityAuditor(tasks=tasks, planning=planning, leases=leases).audit()

    # TaskGraph historically bootstraps plan_version at 1 while MasterPlanGraph
    # has zero accepted revisions. Wave 2 records this instead of guessing that
    # the two integers mean the same thing.
    assert report.task_graph_plan_version == 1
    assert report.master_plan_revision == 0
    assert report.plan_clock_aligned is False
    assert "historical_plan_clock_offset" in report.finding_codes


def test_direct_taskgraph_lease_is_detected_when_coordinator_has_no_receipt() -> None:
    *_, tasks, planning, leases = _substrate()
    tasks.add_task("task-1", title="legacy direct lease", plan_node_id="plan-1")
    tasks.lease("task-1", "coding.backend.01")

    report = RefoundationAuthorityAuditor(tasks=tasks, planning=planning, leases=leases).audit()
    finding = next(row for row in report.findings if row.code == "taskgraph_lease_without_coordinator_receipt")
    assert finding.task_id == "task-1"
    assert finding.task_graph_holder == "coding.backend.01"
    assert finding.coordinator_holder is None
    assert not report.lease_truth_aligned


def test_coordinator_grant_produces_aligned_projected_taskgraph_lease() -> None:
    *_, tasks, planning, leases = _substrate()
    tasks.add_task("task-1", title="coordinated lease", plan_node_id="plan-1")
    lease = leases.grant("task-1", "coding.backend.01", token=7, evidence_refs=("ev-lease",))

    report = RefoundationAuthorityAuditor(tasks=tasks, planning=planning, leases=leases).audit()
    task_findings = tuple(row for row in report.findings if row.task_id == "task-1" and "lease" in row.code)
    assert task_findings == ()
    assert report.lease_truth_aligned
    assert report.active_lease_epochs == {"task-1": lease.epoch}


def test_audit_is_read_only_and_digest_stable() -> None:
    *_, tasks, planning, leases = _substrate()
    tasks.add_task("task-1", title="audit", plan_node_id="plan-1")
    before_tasks = tasks.to_state()
    before_plan = planning.to_state()
    before_leases = leases.to_state()

    first = RefoundationAuthorityAuditor(tasks=tasks, planning=planning, leases=leases).audit()
    second = RefoundationAuthorityAuditor(tasks=tasks, planning=planning, leases=leases).audit()

    assert first.digest == second.digest
    assert tasks.to_state() == before_tasks
    assert planning.to_state() == before_plan
    assert leases.to_state() == before_leases
