from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from .authority import AuthorityGraph
from .events import EventLedger
from .registry import AgentRegistry
from .types import EventKind


@dataclass(frozen=True, slots=True)
class TaskRecord:
    task_id: str
    title: str
    plan_node_id: str
    dependencies: tuple[str, ...] = ()
    leased_to: str | None = None
    completed_by: str | None = None
    output_artifact_ids: tuple[str, ...] = ()

    def to_state(self) -> dict[str, Any]:
        return {
            'task_id': self.task_id,
            'title': self.title,
            'plan_node_id': self.plan_node_id,
            'dependencies': list(self.dependencies),
            'leased_to': self.leased_to,
            'completed_by': self.completed_by,
            'output_artifact_ids': list(self.output_artifact_ids),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'TaskRecord':
        return cls(
            task_id=str(state['task_id']),
            title=str(state['title']),
            plan_node_id=str(state['plan_node_id']),
            dependencies=tuple(str(row) for row in state.get('dependencies', ())),
            leased_to=None if state.get('leased_to') is None else str(state['leased_to']),
            completed_by=None if state.get('completed_by') is None else str(state['completed_by']),
            output_artifact_ids=tuple(str(row) for row in state.get('output_artifact_ids', ())),
        )


class TaskGraph:
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
        self.plan_version = 1

    def add_task(self, task_id: str, *, title: str, plan_node_id: str) -> TaskRecord:
        task_id = str(task_id)
        if task_id in self._tasks:
            raise ValueError(f'duplicate task id: {task_id}')
        if not str(title).strip() or not str(plan_node_id).strip():
            raise ValueError('task title and plan node must be non-empty')
        row = TaskRecord(task_id=task_id, title=str(title), plan_node_id=str(plan_node_id))
        self._tasks[task_id] = row
        if row.plan_node_id not in self._plan_nodes:
            self._plan_nodes.append(row.plan_node_id)
        return row

    def get(self, task_id: str) -> TaskRecord:
        try:
            return self._tasks[str(task_id)]
        except KeyError as exc:
            raise KeyError(f'unknown task id: {task_id}') from exc

    def tasks(self) -> tuple[TaskRecord, ...]:
        return tuple(self._tasks.values())

    def lease(self, task_id: str, agent_id: str) -> TaskRecord:
        old = self.get(task_id)
        if old.completed_by is not None:
            raise ValueError(f'task {task_id} is already completed')
        if old.leased_to is not None and old.leased_to != str(agent_id):
            raise ValueError(f'task {task_id} is already leased to {old.leased_to}')
        if self.registry is not None:
            self.registry.get(agent_id)
        row = replace(old, leased_to=str(agent_id))
        self._tasks[row.task_id] = row
        if self.registry is not None:
            self.registry.bind_task(str(agent_id), row.task_id)
        return row

    def complete(self, task_id: str, agent_id: str, *, output_artifact_ids: tuple[str, ...] = ()) -> TaskRecord:
        old = self.get(task_id)
        if old.leased_to != str(agent_id):
            raise PermissionError(f'agent {agent_id} does not own task lease {task_id}')
        row = replace(old, completed_by=str(agent_id), output_artifact_ids=tuple(str(x) for x in output_artifact_ids))
        self._tasks[row.task_id] = row
        if self.registry is not None:
            self.registry.bind_task(str(agent_id), None)
        self.ledger.append(
            EventKind.TASK_COMPLETED,
            source_agent_id=str(agent_id),
            target_agent_id=str(agent_id),
            region=self.registry.get(agent_id).region if self.registry is not None else None,
            payload={'task_id': row.task_id, 'output_artifact_ids': list(row.output_artifact_ids)},
        )
        return row

    def add_dependency(self, task_id: str, dependency_id: str) -> TaskRecord:
        task = self.get(task_id)
        self.get(dependency_id)
        if task_id == dependency_id:
            raise ValueError('task cannot depend on itself')
        dependencies = tuple(dict.fromkeys(task.dependencies + (str(dependency_id),)))
        candidate = replace(task, dependencies=dependencies)
        self._tasks[candidate.task_id] = candidate
        if self._has_cycle():
            self._tasks[task.task_id] = task
            raise ValueError('task dependency would create a cycle')
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
            for dep in self._tasks[task_id].dependencies:
                if visit(dep):
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
            raise ValueError('plan-gap reason must be explicit')
        if self.registry is not None:
            source = self.registry.get(source_agent_id)
            region = source.region
        else:
            region = None
        return self.ledger.append(
            EventKind.PLAN_GAP_DETECTED,
            source_agent_id=str(source_agent_id),
            target_agent_id='planning.chief',
            region=region,
            payload={
                'task_id': str(task_id),
                'reason': str(reason),
                'suggested_nodes': list(suggested_nodes),
                'evidence_ids': list(evidence_ids),
                'plan_version': self.plan_version,
            },
        )

    def apply_plan_amendment(self, actor_agent_id: str, proposal_event_id: str, *, added_nodes: tuple[str, ...]):
        proposal = self.ledger.get(proposal_event_id)
        if proposal.kind is not EventKind.PLAN_GAP_DETECTED:
            raise ValueError('plan amendment must reference a plan-gap event')
        if self.authority is not None:
            self.authority.require_write(actor_agent_id, 'master-plan')
        elif str(actor_agent_id) != 'planning.chief':
            raise PermissionError('only Planning Chief may authoritatively amend the master plan')
        nodes = tuple(str(node) for node in added_nodes if str(node).strip())
        if not nodes:
            raise ValueError('plan amendment must add at least one node')
        for node in nodes:
            if node not in self._plan_nodes:
                self._plan_nodes.append(node)
        self.plan_version += 1
        payload = proposal.payload
        return self.ledger.append(
            EventKind.PLAN_AMENDED,
            source_agent_id=str(actor_agent_id),
            target_agent_id=proposal.source_agent_id,
            region='planning-program',
            payload={
                'proposal_event_id': proposal.event_id,
                'task_id': payload.get('task_id'),
                'added_nodes': list(nodes),
                'affected_tasks': [payload.get('task_id')] if payload.get('task_id') else [],
                'plan_version': self.plan_version,
            },
        )

    def plan_nodes(self) -> tuple[str, ...]:
        return tuple(self._plan_nodes)

    def to_state(self) -> dict[str, Any]:
        return {
            'tasks': [row.to_state() for row in self.tasks()],
            'plan_nodes': list(self._plan_nodes),
            'plan_version': self.plan_version,
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
        *,
        ledger: EventLedger,
        registry: AgentRegistry | None = None,
        authority: AuthorityGraph | None = None,
    ) -> 'TaskGraph':
        graph = cls(ledger=ledger, registry=registry, authority=authority)
        graph._tasks = {
            row.task_id: row
            for row in (TaskRecord.from_state(value) for value in state.get('tasks', ()))
        }
        graph._plan_nodes = [str(value) for value in state.get('plan_nodes', ())]
        graph.plan_version = int(state.get('plan_version', 1))
        return graph
