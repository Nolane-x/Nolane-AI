from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .campaign_repository import RepositorySnapshotRegistry
from .evaluation_regimes import BenchmarkDomain
from .types import canonical_digest


class CampaignPartition(str, Enum):
    TRAIN = 'train'
    DEV = 'dev'
    HELDOUT = 'heldout'


@dataclass(frozen=True, slots=True)
class CampaignTaskManifest:
    task_id: str
    domain: BenchmarkDomain
    repository_snapshot_id: str
    objective: str
    objective_digest: str
    acceptance_command_digest: str
    difficulty: str
    allowed_tools: tuple[str, ...]
    allowed_cores: tuple[str, ...]
    compute_budget_units: int
    tool_call_budget: int
    external_core_budget: int
    wall_clock_budget_ms: int
    active_agent_budget: int
    evaluator_protocol_version: str
    contamination_tags: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'task_id': self.task_id, 'domain': self.domain.value,
            'repository_snapshot_id': self.repository_snapshot_id,
            'objective': self.objective, 'objective_digest': self.objective_digest,
            'acceptance_command_digest': self.acceptance_command_digest,
            'difficulty': self.difficulty, 'allowed_tools': list(self.allowed_tools),
            'allowed_cores': list(self.allowed_cores),
            'compute_budget_units': self.compute_budget_units,
            'tool_call_budget': self.tool_call_budget,
            'external_core_budget': self.external_core_budget,
            'wall_clock_budget_ms': self.wall_clock_budget_ms,
            'active_agent_budget': self.active_agent_budget,
            'evaluator_protocol_version': self.evaluator_protocol_version,
            'contamination_tags': list(self.contamination_tags),
        }

    def registration_kwargs(self) -> dict[str, Any]:
        return {
            'task_id': self.task_id, 'domain': self.domain,
            'repository_snapshot_id': self.repository_snapshot_id, 'objective': self.objective,
            'acceptance_command_digest': self.acceptance_command_digest, 'difficulty': self.difficulty,
            'allowed_tools': self.allowed_tools, 'allowed_cores': self.allowed_cores,
            'compute_budget_units': self.compute_budget_units, 'tool_call_budget': self.tool_call_budget,
            'external_core_budget': self.external_core_budget, 'wall_clock_budget_ms': self.wall_clock_budget_ms,
            'active_agent_budget': self.active_agent_budget,
            'evaluator_protocol_version': self.evaluator_protocol_version,
            'contamination_tags': self.contamination_tags,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CampaignTaskManifest':
        row = cls(
            task_id=str(state['task_id']), domain=BenchmarkDomain(str(state['domain'])),
            repository_snapshot_id=str(state['repository_snapshot_id']), objective=str(state['objective']),
            objective_digest=str(state['objective_digest']), acceptance_command_digest=str(state['acceptance_command_digest']),
            difficulty=str(state['difficulty']), allowed_tools=tuple(str(x) for x in state.get('allowed_tools', ())),
            allowed_cores=tuple(str(x) for x in state.get('allowed_cores', ())),
            compute_budget_units=int(state['compute_budget_units']), tool_call_budget=int(state['tool_call_budget']),
            external_core_budget=int(state['external_core_budget']), wall_clock_budget_ms=int(state['wall_clock_budget_ms']),
            active_agent_budget=int(state['active_agent_budget']), evaluator_protocol_version=str(state['evaluator_protocol_version']),
            contamination_tags=tuple(str(x) for x in state.get('contamination_tags', ())), digest=str(state['digest']),
        )
        _validate_task(row)
        if canonical_digest(row.objective) != row.objective_digest:
            raise ValueError('campaign task objective digest mismatch')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('campaign task digest mismatch')
        return row


def _validate_task(row: CampaignTaskManifest) -> None:
    for value, label in (
        (row.task_id, 'task id'), (row.repository_snapshot_id, 'repository snapshot id'),
        (row.objective, 'objective'), (row.acceptance_command_digest, 'acceptance command digest'),
        (row.difficulty, 'difficulty'), (row.evaluator_protocol_version, 'evaluator protocol version'),
    ):
        if not str(value).strip():
            raise ValueError(f'{label} must be explicit')
    if not row.allowed_tools or not row.allowed_cores:
        raise ValueError('campaign task requires explicit tool and external-core envelope')
    for value in (
        row.compute_budget_units, row.tool_call_budget, row.external_core_budget,
        row.wall_clock_budget_ms, row.active_agent_budget,
    ):
        if int(value) <= 0:
            raise ValueError('campaign task budgets must be positive')


class CampaignTaskRegistry:
    def __init__(
        self,
        *,
        repositories: RepositorySnapshotRegistry,
        tasks: tuple[CampaignTaskManifest, ...] = (),
        partitions: Mapping[str, str] | None = None,
        partition_digest: str | None = None,
    ) -> None:
        self.repositories = repositories
        self._tasks: dict[str, CampaignTaskManifest] = {}
        for row in tasks:
            self.repositories.get(row.repository_snapshot_id)
            if row.task_id in self._tasks:
                raise ValueError('duplicate campaign task id')
            self._tasks[row.task_id] = row
        self._partitions: dict[str, CampaignPartition] = {}
        for task_id, partition in dict(partitions or {}).items():
            if str(task_id) not in self._tasks:
                raise ValueError('partition references unknown task')
            self._partitions[str(task_id)] = CampaignPartition(str(partition))
        self.partition_digest = None if partition_digest is None else str(partition_digest)
        if self.partition_digest is not None:
            if set(self._partitions) != set(self._tasks):
                raise ValueError('frozen partition state must assign every campaign task')
            if canonical_digest(self._partition_payload()) != self.partition_digest:
                raise ValueError('campaign partition digest mismatch')

    def register(self, **kwargs: Any) -> CampaignTaskManifest:
        if self.partition_digest is not None:
            raise PermissionError('frozen campaign task registry cannot accept new tasks')
        self.repositories.get(str(kwargs['repository_snapshot_id']))
        objective = str(kwargs['objective'])
        row0 = CampaignTaskManifest(
            task_id=str(kwargs['task_id']), domain=BenchmarkDomain(kwargs['domain']),
            repository_snapshot_id=str(kwargs['repository_snapshot_id']), objective=objective,
            objective_digest=canonical_digest(objective), acceptance_command_digest=str(kwargs['acceptance_command_digest']),
            difficulty=str(kwargs['difficulty']), allowed_tools=tuple(str(x) for x in kwargs['allowed_tools']),
            allowed_cores=tuple(str(x) for x in kwargs['allowed_cores']),
            compute_budget_units=int(kwargs['compute_budget_units']), tool_call_budget=int(kwargs['tool_call_budget']),
            external_core_budget=int(kwargs['external_core_budget']), wall_clock_budget_ms=int(kwargs['wall_clock_budget_ms']),
            active_agent_budget=int(kwargs['active_agent_budget']), evaluator_protocol_version=str(kwargs['evaluator_protocol_version']),
            contamination_tags=tuple(str(x) for x in kwargs.get('contamination_tags', ())), digest='',
        )
        _validate_task(row0)
        row = CampaignTaskManifest(
            task_id=row0.task_id, domain=row0.domain, repository_snapshot_id=row0.repository_snapshot_id,
            objective=row0.objective, objective_digest=row0.objective_digest,
            acceptance_command_digest=row0.acceptance_command_digest, difficulty=row0.difficulty,
            allowed_tools=row0.allowed_tools, allowed_cores=row0.allowed_cores,
            compute_budget_units=row0.compute_budget_units, tool_call_budget=row0.tool_call_budget,
            external_core_budget=row0.external_core_budget, wall_clock_budget_ms=row0.wall_clock_budget_ms,
            active_agent_budget=row0.active_agent_budget, evaluator_protocol_version=row0.evaluator_protocol_version,
            contamination_tags=row0.contamination_tags, digest=canonical_digest(row0.payload()),
        )
        existing = self._tasks.get(row.task_id)
        if existing is not None:
            if existing == row:
                return existing
            raise ValueError('campaign task id cannot be rebound')
        self._tasks[row.task_id] = row
        return row

    def get(self, task_id: str) -> CampaignTaskManifest:
        try:
            return self._tasks[str(task_id)]
        except KeyError as exc:
            raise KeyError(f'unknown campaign task: {task_id}') from exc

    def tasks(self) -> tuple[CampaignTaskManifest, ...]:
        return tuple(self._tasks[key] for key in sorted(self._tasks))

    def assign_partition(self, task_id: str, partition: CampaignPartition) -> None:
        if self.partition_digest is not None:
            raise PermissionError('campaign partition assignments are frozen')
        task_id = str(task_id); self.get(task_id); partition = CampaignPartition(partition)
        current = self._partitions.get(task_id)
        if current is not None and current is not partition:
            raise ValueError('campaign task partition cannot be rebound')
        self._partitions[task_id] = partition

    def partition_of(self, task_id: str) -> CampaignPartition:
        self.get(task_id)
        try:
            return self._partitions[str(task_id)]
        except KeyError as exc:
            raise KeyError(f'campaign task has no partition: {task_id}') from exc

    def _partition_payload(self) -> dict[str, Any]:
        return {
            'tasks': [{'task_id': row.task_id, 'task_digest': row.digest, 'partition': self._partitions[row.task_id].value}
                      for row in self.tasks()]
        }

    def freeze_partitions(self) -> str:
        if self.partition_digest is not None:
            return self.partition_digest
        if not self._tasks or set(self._partitions) != set(self._tasks):
            raise ValueError('every campaign task must be assigned before partition freeze')
        self.partition_digest = canonical_digest(self._partition_payload())
        return self.partition_digest

    def to_state(self) -> dict[str, Any]:
        return {
            'tasks': [row.to_state() for row in self.tasks()],
            'partitions': {key: self._partitions[key].value for key in sorted(self._partitions)},
            'partition_digest': self.partition_digest,
        }

    @classmethod
    def from_state(
        cls, *, repositories: RepositorySnapshotRegistry, state: Mapping[str, Any],
    ) -> 'CampaignTaskRegistry':
        return cls(
            repositories=repositories,
            tasks=tuple(CampaignTaskManifest.from_state(x) for x in state.get('tasks', ())),
            partitions={str(k): str(v) for k, v in state.get('partitions', {}).items()},
            partition_digest=None if state.get('partition_digest') is None else str(state['partition_digest']),
        )
