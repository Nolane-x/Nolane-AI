from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from cogcoder.organization.coordination_leases import LeaseCoordinator
from cogcoder.organization.planning import PlanningControlPlane
from cogcoder.organization.tasks import TaskGraph
from cogcoder.organization.types import canonical_digest


class CanonicalAuthorityTarget(str, Enum):
    """Declared Refoundation targets; this module does not perform cutover writes."""

    MASTER_PLAN_GRAPH = "master_plan_graph"
    LEASE_COORDINATOR = "lease_coordinator"


@dataclass(frozen=True, slots=True)
class AuthorityDriftFinding:
    code: str
    detail: str
    task_id: str | None = None
    task_graph_holder: str | None = None
    coordinator_holder: str | None = None
    coordinator_epoch: int | None = None

    def to_state(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "detail": self.detail,
            "task_id": self.task_id,
            "task_graph_holder": self.task_graph_holder,
            "coordinator_holder": self.coordinator_holder,
            "coordinator_epoch": self.coordinator_epoch,
        }


@dataclass(frozen=True, slots=True)
class AuthorityReconciliationReport:
    plan_target: CanonicalAuthorityTarget
    lease_target: CanonicalAuthorityTarget
    task_graph_plan_version: int
    master_plan_revision: int
    plan_clock_aligned: bool
    lease_truth_aligned: bool
    active_lease_epochs: Mapping[str, int]
    findings: tuple[AuthorityDriftFinding, ...]
    destructive_cutover_allowed: bool
    digest: str

    @property
    def finding_codes(self) -> tuple[str, ...]:
        return tuple(row.code for row in self.findings)

    def payload(self) -> dict[str, Any]:
        return {
            "plan_target": self.plan_target.value,
            "lease_target": self.lease_target.value,
            "task_graph_plan_version": self.task_graph_plan_version,
            "master_plan_revision": self.master_plan_revision,
            "plan_clock_aligned": self.plan_clock_aligned,
            "lease_truth_aligned": self.lease_truth_aligned,
            "active_lease_epochs": dict(sorted((str(k), int(v)) for k, v in self.active_lease_epochs.items())),
            "findings": [row.to_state() for row in self.findings],
            "destructive_cutover_allowed": self.destructive_cutover_allowed,
        }

    def __post_init__(self) -> None:
        if canonical_digest(self.payload()) != self.digest:
            raise ValueError("authority reconciliation report digest mismatch")
        if self.destructive_cutover_allowed:
            raise ValueError("observation-only reconciliation cannot authorize destructive cutover")


class RefoundationAuthorityAuditor:
    """Read-only audit of the two historically duplicated authority surfaces.

    The accepted runtime carries both TaskGraph.plan_version and
    MasterPlanGraph revisions, plus both TaskGraph.leased_to and coordination
    lease receipts.  Epoch 0 records drift before any source-of-truth cutover.
    """

    def __init__(self, *, tasks: TaskGraph, planning: PlanningControlPlane, leases: LeaseCoordinator) -> None:
        self.tasks = tasks
        self.planning = planning
        self.leases = leases

    def audit(self) -> AuthorityReconciliationReport:
        task_plan = int(self.tasks.plan_version)
        master_plan = int(self.planning.graph.version)
        findings: list[AuthorityDriftFinding] = []

        plan_aligned = task_plan == master_plan
        if not plan_aligned:
            code = "historical_plan_clock_offset" if (task_plan, master_plan) == (1, 0) else "plan_clock_drift"
            findings.append(
                AuthorityDriftFinding(
                    code=code,
                    detail=(
                        f"TaskGraph plan_version={task_plan} while MasterPlanGraph revision={master_plan}; "
                        "the refoundation does not assume those counters are semantically interchangeable"
                    ),
                )
            )

        active_epochs: dict[str, int] = {}
        lease_aligned = True
        for task in sorted(self.tasks.tasks(), key=lambda row: row.task_id):
            try:
                current = self.leases.current(task.task_id)
            except KeyError:
                current = None

            if current is None:
                if task.leased_to is not None:
                    lease_aligned = False
                    findings.append(
                        AuthorityDriftFinding(
                            code="taskgraph_lease_without_coordinator_receipt",
                            detail="TaskGraph has a projected active holder but LeaseCoordinator has no active receipt",
                            task_id=task.task_id,
                            task_graph_holder=task.leased_to,
                        )
                    )
                continue

            active_epochs[task.task_id] = current.epoch
            if task.leased_to != current.agent_id:
                lease_aligned = False
                findings.append(
                    AuthorityDriftFinding(
                        code="lease_holder_mismatch",
                        detail="TaskGraph lease holder differs from the canonical-target coordination lease receipt",
                        task_id=task.task_id,
                        task_graph_holder=task.leased_to,
                        coordinator_holder=current.agent_id,
                        coordinator_epoch=current.epoch,
                    )
                )

        payload = {
            "plan_target": CanonicalAuthorityTarget.MASTER_PLAN_GRAPH.value,
            "lease_target": CanonicalAuthorityTarget.LEASE_COORDINATOR.value,
            "task_graph_plan_version": task_plan,
            "master_plan_revision": master_plan,
            "plan_clock_aligned": plan_aligned,
            "lease_truth_aligned": lease_aligned,
            "active_lease_epochs": dict(sorted(active_epochs.items())),
            "findings": [row.to_state() for row in findings],
            "destructive_cutover_allowed": False,
        }
        return AuthorityReconciliationReport(
            plan_target=CanonicalAuthorityTarget.MASTER_PLAN_GRAPH,
            lease_target=CanonicalAuthorityTarget.LEASE_COORDINATOR,
            task_graph_plan_version=task_plan,
            master_plan_revision=master_plan,
            plan_clock_aligned=plan_aligned,
            lease_truth_aligned=lease_aligned,
            active_lease_epochs=active_epochs,
            findings=tuple(findings),
            destructive_cutover_allowed=False,
            digest=canonical_digest(payload),
        )
