from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping

from cogcoder.organization.types import EventKind

from .authority import AuthorityGraph
from .events import EventLedger
from .identity import AgentRegistry

COMPONENT_ID = "organization.tasks"
COMPONENT_VERSION = "0.0.2"
MIGRATED_FROM = "cogcoder.organization.tasks"
PLAN_REVISION_AUTHORITY = "external.planning"


@dataclass(frozen=True, slots=True)
class TaskRecord:
    task_id: str
    title: str
    plan_node_id: str
    dependencies: tuple[str, ...] = ()
    leased_to: str | None = None
    completed_by: str | None = None
    output_artifact_ids: tuple[str, ...] = ()
    aborted_by: str | None = None
    abort_reason: str | None = None

    def to_state(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "plan_node_id": self.plan_node_id,
            "dependencies": list(self.dependencies),
            "leased_to": self.leased_to,
            "completed_by": self.completed_by,
            "output_artifact_ids": list(self.output_artifact_ids),
            "aborted_by": self.aborted_by,
            "abort_reason": self.abort_reason,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TaskRecord":
        return cls(
            task_id=str(state["task_id"]),
            title=str(state["title"]),
            plan_node_id=str(state["plan_node_id"]),
            dependencies=tuple(str(row) for row in state.get("dependencies", ())),
            leased_to=None if state.get("leased_to") is None else str(state["leased_to"]),
            completed_by=None if state.get("completed_by") is None else str(state["completed_by"]),
            output_artifact_ids=tuple(str(row) for row in state.get("output_artifact_ids", ())),
            aborted_by=None if state.get("aborted_by") is None else str(state["aborted_by"]),
            abort_reason=None if state.get("abort_reason") is None else str(state["abort_reason"]),
        )


class TaskGraph:
    """Canonical task DAG with a read-only projection of Planning revision authority."""

    def __init__(
        self,
        *,
        ledger: EventLedger,
        registry: AgentRegistry | None = None,
        authority: AuthorityGraph | None = None,
    ) -> None:
        self.ledger = ledger
        self.registry = registry
        self.authority = authority
        self._tasks: dict[str, TaskRecord] = {}
        self._plan_nodes: list[str] = []
        self._plan_version = 0
        self._plan_revision_authority: str | None = PLAN_REVISION_AUTHORITY
        self._loaded_legacy_plan_revision = False
        self._planning_amendment_handler: Callable[..., Any] | None = None

    @property
    def plan_version(self) -> int:
        return self._plan_version

    def _bind_planning_authority(
        self,
        handler: Callable[..., Any],
        *,
        canonical_version: int,
        canonical_nodes: tuple[str, ...],
    ) -> None:
        canonical_version = int(canonical_version)
        if canonical_version < 0:
            raise ValueError("plan revision cannot be negative")
        if self._loaded_legacy_plan_revision:
            if self._plan_version == canonical_version:
                pass
            elif self._plan_version == 1 and canonical_version == 0:
                self._plan_version = 0
            else:
                raise ValueError(
                    f"legacy plan revision mismatch: task projection={self._plan_version}, planning={canonical_version}"
                )
            self._loaded_legacy_plan_revision = False
            self._plan_revision_authority = PLAN_REVISION_AUTHORITY
        elif self._plan_version != canonical_version:
            raise ValueError(
                f"plan revision authority mismatch: task projection={self._plan_version}, planning={canonical_version}"
            )
        self._planning_amendment_handler = handler
        self._plan_nodes = list(dict.fromkeys(str(node) for node in canonical_nodes if str(node).strip()))

    def _project_plan_revision(self, version: int, plan_nodes: tuple[str, ...]) -> None:
        version = int(version)
        if version < self._plan_version:
            raise ValueError(
                f"plan revision projection cannot move backwards: {self._plan_version} -> {version}"
            )
        self._plan_version = version
        self._plan_revision_authority = PLAN_REVISION_AUTHORITY
        self._loaded_legacy_plan_revision = False
        self._plan_nodes = list(dict.fromkeys(str(node) for node in plan_nodes if str(node).strip()))

    def add_task(self, task_id: str, *, title: str, plan_node_id: str) -> TaskRecord:
        task_id = str(task_id)
        if task_id in self._tasks:
            raise ValueError(f"duplicate task id: {task_id}")
        if not str(title).strip() or not str(plan_node_id).strip():
            raise ValueError("task title and plan node must be non-empty")
        row = TaskRecord(task_id=task_id, title=str(title), plan_node_id=str(plan_node_id))
        self._tasks[task_id] = row
        if row.plan_node_id not in self._plan_nodes:
            self._plan_nodes.append(row.plan_node_id)
        return row

    def get(self, task_id: str) -> TaskRecord:
        try:
            return self._tasks[str(task_id)]
        except KeyError as exc:
            raise KeyError(f"unknown task id: {task_id}") from exc

    def tasks(self) -> tuple[TaskRecord, ...]:
        return tuple(self._tasks.values())

    def lease(self, task_id: str, agent_id: str) -> TaskRecord:
        old = self.get(task_id)
        if old.completed_by is not None:
            raise ValueError(f"task {task_id} is already completed")
        if old.aborted_by is not None:
            raise ValueError(f"task {task_id} is aborted")
        if old.leased_to is not None and old.leased_to != str(agent_id):
            raise ValueError(f"task {task_id} is already leased to {old.leased_to}")
        if self.registry is not None:
            self.registry.get(agent_id)
        row = replace(old, leased_to=str(agent_id))
        self._tasks[row.task_id] = row
        if self.registry is not None:
            self.registry.bind_task(str(agent_id), row.task_id)
        return row

    def release_lease(self, task_id: str, agent_id: str) -> TaskRecord:
        old = self.get(task_id)
        if old.completed_by is not None:
            raise ValueError(f"task {task_id} is already completed")
        if old.aborted_by is not None:
            raise ValueError(f"task {task_id} is aborted")
        if old.leased_to != str(agent_id):
            raise PermissionError(f"agent {agent_id} does not own task lease {task_id}")
        row = replace(old, leased_to=None)
        self._tasks[row.task_id] = row
        if self.registry is not None:
            self.registry.bind_task(str(agent_id), None)
        return row

    def complete(
        self,
        task_id: str,
        agent_id: str,
        *,
        output_artifact_ids: tuple[str, ...] = (),
    ) -> TaskRecord:
        old = self.get(task_id)
        if old.aborted_by is not None:
            raise ValueError(f"task {task_id} is aborted")
        if old.leased_to != str(agent_id):
            raise PermissionError(f"agent {agent_id} does not own task lease {task_id}")
        row = replace(
            old,
            completed_by=str(agent_id),
            output_artifact_ids=tuple(str(x) for x in output_artifact_ids),
        )
        self._tasks[row.task_id] = row
        if self.registry is not None:
            self.registry.bind_task(str(agent_id), None)
        self.ledger.append(
            EventKind.TASK_COMPLETED,
            source_agent_id=str(agent_id),
            target_agent_id=str(agent_id),
            region=self.registry.get(agent_id).region if self.registry is not None else None,
            payload={"task_id": row.task_id, "output_artifact_ids": list(row.output_artifact_ids)},
        )
        return row

    def abort(self, task_id: str, actor_agent_id: str, *, reason: str) -> TaskRecord:
        old = self.get(task_id)
        actor = str(actor_agent_id)
        if actor != "nolane.central":
            raise PermissionError("Part-II task abort authority belongs to Nolane Central")
        if old.completed_by is not None:
            raise ValueError(f"task {task_id} is already completed")
        if old.aborted_by is not None:
            raise ValueError(f"task {task_id} is already aborted")
        reason = str(reason).strip()
        if not reason:
            raise ValueError("task abort reason must be explicit")
        prior_lessee = old.leased_to
        row = replace(old, leased_to=None, aborted_by=actor, abort_reason=reason)
        self._tasks[row.task_id] = row
        if self.registry is not None and prior_lessee is not None:
            self.registry.bind_task(prior_lessee, None)
        self.ledger.append(
            EventKind.TASK_BLOCKED,
            source_agent_id=actor,
            target_agent_id=prior_lessee,
            region=(
                self.registry.get(prior_lessee).region
                if self.registry is not None and prior_lessee is not None
                else None
            ),
            payload={"task_id": row.task_id, "reason": reason, "status": "aborted"},
        )
        return row

    def add_dependency(self, task_id: str, dependency_id: str) -> TaskRecord:
        task = self.get(task_id)
        self.get(dependency_id)
        if task_id == dependency_id:
            raise ValueError("task cannot depend on itself")
        dependencies = tuple(dict.fromkeys(task.dependencies + (str(dependency_id),)))
        candidate = replace(task, dependencies=dependencies)
        self._tasks[candidate.task_id] = candidate
        if self._has_cycle():
            self._tasks[task.task_id] = task
            raise ValueError("task dependency would create a cycle")
        return candidate

    def _has_cycle(self) -> bool:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> bool:
            if task_id in visiting:
                return True
            if task_id in visited:
                return False
            visiting.add(task_id)
            for dependency in self._tasks[task_id].dependencies:
                if visit(dependency):
                    return True
            visiting.remove(task_id)
            visited.add(task_id)
            return False

        return any(visit(task_id) for task_id in self._tasks)

    def propose_plan_gap(
        self,
        *,
        source_agent_id: str,
        task_id: str,
        reason: str,
        suggested_nodes: tuple[str, ...],
        evidence_ids: tuple[str, ...],
    ):
        self.get(task_id)
        if not str(reason).strip():
            raise ValueError("plan-gap reason must be explicit")
        region = self.registry.get(source_agent_id).region if self.registry is not None else None
        return self.ledger.append(
            EventKind.PLAN_GAP_DETECTED,
            source_agent_id=str(source_agent_id),
            target_agent_id="planning.chief",
            region=region,
            payload={
                "task_id": str(task_id),
                "reason": str(reason),
                "suggested_nodes": list(suggested_nodes),
                "evidence_ids": list(evidence_ids),
                "plan_version": self.plan_version,
            },
        )

    def apply_plan_amendment(
        self,
        actor_agent_id: str,
        proposal_event_id: str,
        *,
        added_nodes: tuple[str, ...],
    ):
        if self._planning_amendment_handler is None:
            raise RuntimeError("Planning authority is not bound")
        return self._planning_amendment_handler(
            actor_agent_id=str(actor_agent_id),
            proposal_event_id=str(proposal_event_id),
            added_nodes=tuple(str(node) for node in added_nodes),
        )

    def plan_nodes(self) -> tuple[str, ...]:
        return tuple(self._plan_nodes)

    def to_state(self) -> dict[str, Any]:
        return {
            "tasks": [row.to_state() for row in self.tasks()],
            "plan_nodes": list(self._plan_nodes),
            "plan_version": self.plan_version,
            "plan_revision_authority": PLAN_REVISION_AUTHORITY,
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        ledger: EventLedger,
        registry: AgentRegistry | None = None,
        authority: AuthorityGraph | None = None,
    ) -> "TaskGraph":
        graph = cls(ledger=ledger, registry=registry, authority=authority)
        graph._tasks = {
            row.task_id: row
            for row in (TaskRecord.from_state(value) for value in state.get("tasks", ()))
        }
        graph._plan_nodes = [str(value) for value in state.get("plan_nodes", ())]
        marker = state.get("plan_revision_authority")
        if marker is not None and str(marker) != PLAN_REVISION_AUTHORITY:
            raise ValueError(f"unknown plan revision authority: {marker}")
        graph._plan_revision_authority = None if marker is None else PLAN_REVISION_AUTHORITY
        graph._loaded_legacy_plan_revision = marker is None
        graph._plan_version = int(state.get("plan_version", 1 if marker is None else 0))
        if graph._plan_version < 0:
            raise ValueError("plan revision cannot be negative")
        return graph


__all__ = (
    "TaskGraph",
    "TaskRecord",
    "COMPONENT_ID",
    "COMPONENT_VERSION",
    "MIGRATED_FROM",
    "PLAN_REVISION_AUTHORITY",
)