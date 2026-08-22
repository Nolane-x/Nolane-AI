from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .planning import PlanNodeStatus, PlanningControlPlane
from .requirements import RequirementStatus, RequirementsControlPlane
from .types import EventKind, canonical_digest


if not hasattr(EventKind, 'PLAN_RECONCILIATION_FINDING'):
    setattr(EventKind, 'PLAN_RECONCILIATION_FINDING', EventKind.PLAN_CHANGE_PROPOSED)


class DriftClass(str, Enum):
    ORPHAN_TASK = 'orphan_task'
    MISSING_TASK = 'missing_task'
    UNCOVERED_REQUIREMENT = 'uncovered_requirement'
    DEPENDENCY_DRIFT = 'dependency_drift'
    COMPLETION_DRIFT = 'completion_drift'
    STALE_PLAN_NODE = 'stale_plan_node'
    VERIFICATION_GAP = 'verification_gap'


@dataclass(frozen=True, slots=True)
class ReconciliationFinding:
    finding_id: str
    drift_class: DriftClass
    object_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    summary: str
    digest: str


class PlanReconciler:
    def __init__(self, requirements: RequirementsControlPlane, planning: PlanningControlPlane, tasks: Any) -> None:
        self.requirements = requirements
        self.planning = planning
        self.tasks = tasks

    def scan(self) -> tuple[ReconciliationFinding, ...]:
        rows: list[tuple[DriftClass, tuple[str, ...], str]] = []
        plan_nodes = {x.node_id: x for x in self.planning.graph.nodes()}
        tasks = tuple(self.tasks.tasks())

        for task in tasks:
            if task.plan_node_id not in plan_nodes:
                rows.append((DriftClass.ORPHAN_TASK, (task.task_id, task.plan_node_id), 'task references no authoritative plan node'))
                continue
            node = plan_nodes[task.plan_node_id]
            if task.completed_by is not None and node.status is not PlanNodeStatus.DONE:
                rows.append((DriftClass.COMPLETION_DRIFT, (task.task_id, node.node_id), 'task completed while plan node is not done'))

        covered_requirements = {req for node in plan_nodes.values() for req in node.requirement_refs}
        for requirement in self.requirements.graph.nodes():
            if requirement.status is RequirementStatus.ACTIVE and requirement.requirement_id not in covered_requirements:
                rows.append((DriftClass.UNCOVERED_REQUIREMENT, (requirement.requirement_id,), 'active requirement has no plan coverage'))

        for node in plan_nodes.values():
            if node.status is PlanNodeStatus.SUPERSEDED:
                continue
            for req_id in node.requirement_refs:
                try:
                    req = self.requirements.graph.get(req_id)
                except KeyError:
                    continue
                if req.status is RequirementStatus.SUPERSEDED:
                    rows.append((DriftClass.STALE_PLAN_NODE, (node.node_id, req_id), 'active plan node references superseded requirement'))

        findings: list[ReconciliationFinding] = []
        for index, (kind, refs, summary) in enumerate(sorted(rows, key=lambda x: (x[0].value, x[1])), 1):
            payload = {'drift_class': kind.value, 'object_refs': list(refs), 'summary': summary}
            findings.append(ReconciliationFinding(
                finding_id=f'reconcile-{index:08d}', drift_class=kind,
                object_refs=refs, evidence_refs=(), summary=summary, digest=canonical_digest(payload),
            ))
        return tuple(findings)
