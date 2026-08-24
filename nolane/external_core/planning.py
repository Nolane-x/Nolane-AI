from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from cogcoder.organization.types import EventKind
from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.requirements import RequirementsControlPlane

COMPONENT_ID = "external.planning"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.planning"

if not hasattr(EventKind, "PLAN_ROLLED_BACK"):
    setattr(EventKind, "PLAN_ROLLED_BACK", EventKind.PLAN_AMENDED)


class PlanNodeStatus(str, Enum):
    PLANNED = "planned"
    READY = "ready"
    ACTIVE = "active"
    BLOCKED = "blocked"
    DONE = "done"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class PlanNode:
    node_id: str
    title: str
    dependencies: tuple[str, ...] = ()
    requirement_refs: tuple[str, ...] = ()
    status: PlanNodeStatus = PlanNodeStatus.PLANNED

    def __post_init__(self) -> None:
        if not self.node_id.strip() or not self.title.strip():
            raise ValueError("plan node id and title must be non-empty")

    def to_state(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "title": self.title,
            "dependencies": list(self.dependencies),
            "requirement_refs": list(self.requirement_refs),
            "status": self.status.value,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "PlanNode":
        return cls(
            str(state["node_id"]),
            str(state["title"]),
            tuple(str(x) for x in state.get("dependencies", ())),
            tuple(str(x) for x in state.get("requirement_refs", ())),
            PlanNodeStatus(str(state.get("status", PlanNodeStatus.PLANNED.value))),
        )


@dataclass(frozen=True, slots=True)
class Milestone:
    milestone_id: str
    title: str
    node_ids: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {"milestone_id": self.milestone_id, "title": self.title, "node_ids": list(self.node_ids)}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "Milestone":
        return cls(str(state["milestone_id"]), str(state["title"]), tuple(str(x) for x in state.get("node_ids", ())))


@dataclass(frozen=True, slots=True)
class PlanRisk:
    risk_id: str
    description: str
    severity: int
    node_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not 0 <= int(self.severity) <= 100:
            raise ValueError("risk severity must be in [0,100]")

    def to_state(self) -> dict[str, Any]:
        return {"risk_id": self.risk_id, "description": self.description, "severity": self.severity, "node_ids": list(self.node_ids)}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "PlanRisk":
        return cls(str(state["risk_id"]), str(state["description"]), int(state["severity"]), tuple(str(x) for x in state.get("node_ids", ())))


@dataclass(frozen=True, slots=True)
class PlanRevision:
    version: int
    parent_version: int | None
    actor_agent_id: str
    reason: str
    evidence_refs: tuple[str, ...]
    graph_digest: str
    changed_node_ids: tuple[str, ...]
    source_revision: int | None = None

    def to_state(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "parent_version": self.parent_version,
            "actor_agent_id": self.actor_agent_id,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "graph_digest": self.graph_digest,
            "changed_node_ids": list(self.changed_node_ids),
            "source_revision": self.source_revision,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "PlanRevision":
        return cls(
            int(state["version"]),
            None if state.get("parent_version") is None else int(state["parent_version"]),
            str(state["actor_agent_id"]),
            str(state["reason"]),
            tuple(str(x) for x in state.get("evidence_refs", ())),
            str(state["graph_digest"]),
            tuple(str(x) for x in state.get("changed_node_ids", ())),
            None if state.get("source_revision") is None else int(state["source_revision"]),
        )


@dataclass(frozen=True, slots=True)
class PlanDelta:
    from_version: int
    to_version: int
    added_nodes: tuple[str, ...]
    removed_nodes: tuple[str, ...]
    changed_nodes: tuple[str, ...]
    affected_tasks: tuple[str, ...]

    def to_state(self) -> dict[str, Any]:
        return {
            "from_version": self.from_version,
            "to_version": self.to_version,
            "added_nodes": list(self.added_nodes),
            "removed_nodes": list(self.removed_nodes),
            "changed_nodes": list(self.changed_nodes),
            "affected_tasks": list(self.affected_tasks),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "PlanDelta":
        return cls(
            int(state["from_version"]),
            int(state["to_version"]),
            tuple(str(x) for x in state.get("added_nodes", ())),
            tuple(str(x) for x in state.get("removed_nodes", ())),
            tuple(str(x) for x in state.get("changed_nodes", ())),
            tuple(str(x) for x in state.get("affected_tasks", ())),
        )


@dataclass(frozen=True, slots=True)
class GapApplication:
    revision: PlanRevision
    event: Any


class MasterPlanGraph:
    def __init__(self, requirements: RequirementsControlPlane) -> None:
        self.requirements = requirements
        self._nodes: dict[str, PlanNode] = {}
        self._milestones: dict[str, Milestone] = {}
        self._risks: dict[str, PlanRisk] = {}
        self._revisions: list[PlanRevision] = []
        self._snapshots: dict[int, dict[str, Any]] = {}

    @property
    def version(self) -> int:
        return len(self._revisions)

    @property
    def digest(self) -> str:
        return canonical_digest({"version": self.version, **self._current_payload()})

    def _current_payload(self) -> dict[str, Any]:
        return {
            "nodes": [x.to_state() for x in self.nodes()],
            "milestones": [self._milestones[k].to_state() for k in sorted(self._milestones)],
            "risks": [self._risks[k].to_state() for k in sorted(self._risks)],
        }

    def nodes(self) -> tuple[PlanNode, ...]:
        return tuple(self._nodes[k] for k in sorted(self._nodes))

    def get(self, node_id: str) -> PlanNode:
        try:
            return self._nodes[str(node_id)]
        except KeyError as exc:
            raise KeyError(f"unknown plan node: {node_id}") from exc

    def _validate(self, nodes: Mapping[str, PlanNode], milestones: Mapping[str, Milestone], risks: Mapping[str, PlanRisk]) -> None:
        for node in nodes.values():
            for dep in node.dependencies:
                if dep not in nodes:
                    raise ValueError(f"unknown plan dependency: {dep}")
            for req in node.requirement_refs:
                try:
                    self.requirements.graph.get(req)
                except KeyError as exc:
                    raise ValueError(f"unknown requirement reference: {req}") from exc
        for milestone in milestones.values():
            if any(node_id not in nodes for node_id in milestone.node_ids):
                raise ValueError("milestone references unknown plan node")
        for risk in risks.values():
            if any(node_id not in nodes for node_id in risk.node_ids):
                raise ValueError("risk references unknown plan node")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(key: str) -> None:
            if key in visiting:
                raise ValueError("plan dependency cycle detected")
            if key in visited:
                return
            visiting.add(key)
            for dep in nodes[key].dependencies:
                visit(dep)
            visiting.remove(key)
            visited.add(key)

        for key in sorted(nodes):
            visit(key)

    def apply(
        self,
        *,
        actor_agent_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
        upsert_nodes: tuple[PlanNode, ...],
        milestones: tuple[Milestone, ...] = (),
        risks: tuple[PlanRisk, ...] = (),
    ) -> PlanRevision:
        reason = str(reason).strip()
        evidence = tuple(str(x).strip() for x in evidence_refs if str(x).strip())
        if not reason or not evidence or (not upsert_nodes and not milestones and not risks):
            raise ValueError("plan revision requires reason, evidence and at least one mutation")
        candidate_nodes = dict(self._nodes)
        candidate_milestones = dict(self._milestones)
        candidate_risks = dict(self._risks)
        changed: list[str] = []
        for node in upsert_nodes:
            candidate_nodes[node.node_id] = node
            changed.append(node.node_id)
        for row in milestones:
            candidate_milestones[row.milestone_id] = row
        for row in risks:
            candidate_risks[row.risk_id] = row
        self._validate(candidate_nodes, candidate_milestones, candidate_risks)
        next_version = self.version + 1
        payload = {
            "nodes": [candidate_nodes[k].to_state() for k in sorted(candidate_nodes)],
            "milestones": [candidate_milestones[k].to_state() for k in sorted(candidate_milestones)],
            "risks": [candidate_risks[k].to_state() for k in sorted(candidate_risks)],
        }
        digest = canonical_digest({"version": next_version, **payload})
        revision = PlanRevision(
            next_version,
            self.version or None,
            str(actor_agent_id),
            reason,
            evidence,
            digest,
            tuple(sorted(set(changed))),
        )
        self._nodes, self._milestones, self._risks = candidate_nodes, candidate_milestones, candidate_risks
        self._revisions.append(revision)
        self._snapshots[next_version] = payload
        return revision

    def rollback(self, *, actor_agent_id: str, source_revision: int, reason: str, evidence_refs: tuple[str, ...]) -> PlanRevision:
        if source_revision not in self._snapshots:
            raise KeyError(f"unknown source plan revision: {source_revision}")
        reason = str(reason).strip()
        evidence = tuple(str(x).strip() for x in evidence_refs if str(x).strip())
        if not reason or not evidence:
            raise ValueError("rollback requires reason and evidence")
        payload = self._snapshots[source_revision]
        nodes = {x.node_id: x for x in (PlanNode.from_state(v) for v in payload["nodes"])}
        milestones = {x.milestone_id: x for x in (Milestone.from_state(v) for v in payload["milestones"])}
        risks = {x.risk_id: x for x in (PlanRisk.from_state(v) for v in payload["risks"])}
        self._validate(nodes, milestones, risks)
        next_version = self.version + 1
        digest = canonical_digest({"version": next_version, **payload})
        changed = tuple(
            sorted(
                set(self._nodes) ^ set(nodes)
                | {k for k in set(self._nodes) & set(nodes) if self._nodes[k] != nodes[k]}
            )
        )
        revision = PlanRevision(
            next_version,
            self.version or None,
            str(actor_agent_id),
            reason,
            evidence,
            digest,
            changed,
            source_revision,
        )
        self._nodes, self._milestones, self._risks = nodes, milestones, risks
        self._revisions.append(revision)
        self._snapshots[next_version] = payload
        return revision

    def revisions(self) -> tuple[PlanRevision, ...]:
        return tuple(self._revisions)

    def snapshot_nodes(self, version: int) -> dict[str, PlanNode]:
        if version == 0:
            return {}
        payload = self._snapshots.get(int(version))
        if payload is None:
            raise KeyError(f"unknown plan revision: {version}")
        return {x.node_id: x for x in (PlanNode.from_state(v) for v in payload["nodes"])}

    def topological_order(self) -> tuple[str, ...]:
        indegree = {k: 0 for k in self._nodes}
        forward = {k: [] for k in self._nodes}
        for key, node in self._nodes.items():
            for dep in node.dependencies:
                indegree[key] += 1
                forward[dep].append(key)
        ready = sorted(k for k, degree in indegree.items() if degree == 0)
        order: list[str] = []
        while ready:
            key = ready.pop(0)
            order.append(key)
            for nxt in sorted(forward[key]):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)
                    ready.sort()
        return tuple(order)

    def ready_nodes(self) -> tuple[str, ...]:
        done = {x.node_id for x in self._nodes.values() if x.status is PlanNodeStatus.DONE}
        return tuple(
            sorted(
                x.node_id
                for x in self._nodes.values()
                if x.status in {PlanNodeStatus.PLANNED, PlanNodeStatus.READY}
                and all(dep in done for dep in x.dependencies)
            )
        )

    def longest_dependency_depth(self) -> int:
        depth: dict[str, int] = {}
        for key in self.topological_order():
            deps = self._nodes[key].dependencies
            depth[key] = 1 if not deps else 1 + max(depth[d] for d in deps)
        return max(depth.values(), default=0)

    def to_state(self) -> dict[str, Any]:
        return {
            **self._current_payload(),
            "revisions": [x.to_state() for x in self._revisions],
            "snapshots": {str(k): v for k, v in sorted(self._snapshots.items())},
        }

    @classmethod
    def from_state(cls, requirements: RequirementsControlPlane, state: Mapping[str, Any]) -> "MasterPlanGraph":
        graph = cls(requirements)
        graph._nodes = {x.node_id: x for x in (PlanNode.from_state(v) for v in state.get("nodes", ())) }
        graph._milestones = {x.milestone_id: x for x in (Milestone.from_state(v) for v in state.get("milestones", ())) }
        graph._risks = {x.risk_id: x for x in (PlanRisk.from_state(v) for v in state.get("risks", ())) }
        graph._validate(graph._nodes, graph._milestones, graph._risks)
        graph._revisions = [PlanRevision.from_state(v) for v in state.get("revisions", ())]
        graph._snapshots = {int(k): dict(v) for k, v in state.get("snapshots", {}).items()}
        for index, rev in enumerate(graph._revisions, 1):
            if rev.version != index or index not in graph._snapshots:
                raise ValueError("non-canonical plan revision sequence")
        if graph._revisions and graph._revisions[-1].graph_digest != graph.digest:
            raise ValueError("plan graph digest mismatch")
        return graph


class PlanningControlPlane:
    def __init__(
        self,
        *,
        registry: Any,
        authority: Any,
        ledger: Any,
        tasks: Any,
        requirements: RequirementsControlPlane,
        graph: MasterPlanGraph | None = None,
        task_links: Mapping[str, str] | None = None,
        deltas: tuple[PlanDelta, ...] = (),
    ) -> None:
        self.registry, self.authority, self.ledger, self.tasks = registry, authority, ledger, tasks
        self.requirements = requirements
        self.graph = graph or MasterPlanGraph(requirements)
        self._task_links = dict(task_links or {})
        self._deltas = list(deltas)
        binder = getattr(self.tasks, "_bind_planning_authority", None)
        if binder is not None:
            binder(
                self._apply_legacy_task_amendment,
                canonical_version=self.graph.version,
                canonical_nodes=tuple(node.node_id for node in self.graph.nodes()),
            )

    def _project_tasks(self) -> None:
        projector = getattr(self.tasks, "_project_plan_revision", None)
        if projector is not None:
            projector(self.graph.version, tuple(node.node_id for node in self.graph.nodes()))

    def _delta(self, old_version: int, new_version: int, affected_tasks: tuple[str, ...]) -> PlanDelta:
        before = self.graph.snapshot_nodes(old_version)
        after = self.graph.snapshot_nodes(new_version)
        added = tuple(sorted(set(after) - set(before)))
        removed = tuple(sorted(set(before) - set(after)))
        changed = tuple(sorted(k for k in set(before) & set(after) if before[k] != after[k]))
        row = PlanDelta(old_version, new_version, added, removed, changed, tuple(sorted(set(affected_tasks))))
        self._deltas.append(row)
        return row

    def apply_revision(
        self,
        *,
        actor_agent_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
        upsert_nodes: tuple[PlanNode, ...],
        milestones: tuple[Milestone, ...] = (),
        risks: tuple[PlanRisk, ...] = (),
    ) -> PlanRevision:
        self.registry.get(actor_agent_id)
        self.authority.require_write(actor_agent_id, "master-plan")
        old = self.graph.version
        rev = self.graph.apply(
            actor_agent_id=actor_agent_id,
            reason=reason,
            evidence_refs=evidence_refs,
            upsert_nodes=upsert_nodes,
            milestones=milestones,
            risks=risks,
        )
        self._delta(old, rev.version, ())
        self._project_tasks()
        self.ledger.append(
            EventKind.PLAN_AMENDED,
            source_agent_id=actor_agent_id,
            target_agent_id="planning.chief",
            region="planning-program",
            evidence_refs=rev.evidence_refs,
            object_refs=rev.changed_node_ids,
            payload={"plan_action": "revision", "old_version": old, "new_version": rev.version, "affected_tasks": []},
        )
        return rev

    def rollback(self, *, actor_agent_id: str, source_revision: int, reason: str, evidence_refs: tuple[str, ...]) -> PlanRevision:
        self.registry.get(actor_agent_id)
        self.authority.require_write(actor_agent_id, "master-plan")
        old = self.graph.version
        rev = self.graph.rollback(
            actor_agent_id=actor_agent_id,
            source_revision=source_revision,
            reason=reason,
            evidence_refs=evidence_refs,
        )
        self._delta(old, rev.version, ())
        self._project_tasks()
        self.ledger.append(
            EventKind.PLAN_ROLLED_BACK,
            source_agent_id=actor_agent_id,
            target_agent_id="planning.chief",
            region="planning-program",
            evidence_refs=rev.evidence_refs,
            payload={
                "plan_action": "rollback",
                "old_version": old,
                "new_version": rev.version,
                "source_revision": source_revision,
                "affected_tasks": [],
            },
        )
        return rev

    def link_task(self, task_id: str, plan_node_id: str) -> None:
        self.tasks.get(task_id)
        self.graph.get(plan_node_id)
        self._task_links[str(task_id)] = str(plan_node_id)

    def plan_node_for_task(self, task_id: str) -> str:
        task = self.tasks.get(task_id)
        linked = self._task_links.get(str(task_id), task.plan_node_id)
        self.graph.get(linked)
        return linked

    def apply_gap(
        self,
        *,
        proposal_event_id: str,
        actor_agent_id: str,
        added_nodes: tuple[PlanNode, ...],
        evidence_refs: tuple[str, ...],
        affected_tasks: tuple[str, ...],
    ) -> GapApplication:
        proposal = self.ledger.get(proposal_event_id)
        if proposal.kind is not EventKind.PLAN_GAP_DETECTED:
            raise ValueError("gap application requires PLAN_GAP_DETECTED")
        self.registry.get(actor_agent_id)
        self.authority.require_write(actor_agent_id, "master-plan")
        for task_id in affected_tasks:
            self.tasks.get(task_id)
        old = self.graph.version
        rev = self.graph.apply(
            actor_agent_id=actor_agent_id,
            reason=str(proposal.payload.get("reason", "plan gap")),
            evidence_refs=evidence_refs,
            upsert_nodes=added_nodes,
        )
        self._delta(old, rev.version, affected_tasks)
        for task_id in affected_tasks:
            task = self.tasks.get(task_id)
            if task.plan_node_id in {x.node_id for x in self.graph.nodes()}:
                self._task_links[task_id] = task.plan_node_id
        self._project_tasks()
        event = self.ledger.append(
            EventKind.PLAN_AMENDED,
            source_agent_id=actor_agent_id,
            target_agent_id=proposal.source_agent_id,
            region="planning-program",
            causal_parent_ids=(proposal.event_id,),
            evidence_refs=tuple(str(x) for x in evidence_refs),
            object_refs=tuple(x.node_id for x in added_nodes),
            payload={
                "plan_action": "gap_applied",
                "proposal_event_id": proposal.event_id,
                "old_version": old,
                "new_version": rev.version,
                "affected_tasks": list(affected_tasks),
            },
        )
        return GapApplication(rev, event)

    def _apply_legacy_task_amendment(
        self,
        *,
        actor_agent_id: str,
        proposal_event_id: str,
        added_nodes: tuple[str, ...],
    ) -> Any:
        proposal = self.ledger.get(proposal_event_id)
        if proposal.kind is not EventKind.PLAN_GAP_DETECTED:
            raise ValueError("plan amendment must reference a plan-gap event")
        self.registry.get(actor_agent_id)
        self.authority.require_write(actor_agent_id, "master-plan")
        nodes = tuple(str(node).strip() for node in added_nodes if str(node).strip())
        if not nodes:
            raise ValueError("plan amendment must add at least one node")
        payload = proposal.payload
        evidence = tuple(str(x) for x in payload.get("evidence_ids", ()) if str(x).strip()) or (proposal.event_id,)
        task_id = payload.get("task_id")
        affected_tasks = (str(task_id),) if task_id else ()
        for affected_task in affected_tasks:
            self.tasks.get(affected_task)
        old = self.graph.version
        rev = self.graph.apply(
            actor_agent_id=actor_agent_id,
            reason=str(payload.get("reason", "plan gap")),
            evidence_refs=evidence,
            upsert_nodes=tuple(PlanNode(node, node) for node in nodes),
        )
        self._delta(old, rev.version, affected_tasks)
        for affected_task in affected_tasks:
            task = self.tasks.get(affected_task)
            if task.plan_node_id in {x.node_id for x in self.graph.nodes()}:
                self._task_links[affected_task] = task.plan_node_id
        self._project_tasks()
        return self.ledger.append(
            EventKind.PLAN_AMENDED,
            source_agent_id=str(actor_agent_id),
            target_agent_id=proposal.source_agent_id,
            region="planning-program",
            payload={
                "proposal_event_id": proposal.event_id,
                "task_id": task_id,
                "added_nodes": list(nodes),
                "affected_tasks": list(affected_tasks),
                "plan_version": rev.version,
            },
        )

    def plan_delta(self, from_version: int) -> PlanDelta:
        current = self.graph.version
        before = self.graph.snapshot_nodes(from_version)
        after = self.graph.snapshot_nodes(current)
        added = tuple(sorted(set(after) - set(before)))
        removed = tuple(sorted(set(before) - set(after)))
        changed = tuple(sorted(k for k in set(before) & set(after) if before[k] != after[k]))
        affected = tuple(
            sorted({task for delta in self._deltas if delta.to_version > from_version for task in delta.affected_tasks})
        )
        return PlanDelta(int(from_version), current, added, removed, changed, affected)

    def revisions(self) -> tuple[PlanRevision, ...]:
        return self.graph.revisions()

    def to_state(self) -> dict[str, Any]:
        return {
            "graph": self.graph.to_state(),
            "task_links": dict(sorted(self._task_links.items())),
            "deltas": [x.to_state() for x in self._deltas],
        }

    @classmethod
    def from_state(
        cls,
        *,
        registry: Any,
        authority: Any,
        ledger: Any,
        tasks: Any,
        requirements: RequirementsControlPlane,
        state: Mapping[str, Any],
    ) -> "PlanningControlPlane":
        graph = MasterPlanGraph.from_state(requirements, state.get("graph", {}))
        return cls(
            registry=registry,
            authority=authority,
            ledger=ledger,
            tasks=tasks,
            requirements=requirements,
            graph=graph,
            task_links=state.get("task_links", {}),
            deltas=tuple(PlanDelta.from_state(v) for v in state.get("deltas", ())),
        )


__all__ = (
    "PlanNodeStatus",
    "PlanNode",
    "Milestone",
    "PlanRisk",
    "PlanRevision",
    "PlanDelta",
    "GapApplication",
    "MasterPlanGraph",
    "PlanningControlPlane",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
)