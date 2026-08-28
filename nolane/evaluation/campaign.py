from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping

from nolane.evaluation.campaign_repository import RepositorySnapshotRegistry
from nolane.evaluation.campaign_tasks import CampaignTaskRegistry
from nolane.evaluation.regimes import EvaluationMode
from nolane.core.canonical_digest import canonical_digest

COMPONENT_ID = "evaluation.campaign"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.campaign"


class CampaignStatus(str, Enum):
    DRAFT = 'draft'
    FROZEN = 'frozen'
    RUNNING = 'running'
    EVIDENCE_READY = 'evidence_ready'
    REPRODUCING = 'reproducing'
    COMPLETE = 'complete'
    INVALID = 'invalid'
    QUARANTINED = 'quarantined'
    ABORTED = 'aborted'


_TERMINAL = {CampaignStatus.COMPLETE, CampaignStatus.INVALID, CampaignStatus.QUARANTINED, CampaignStatus.ABORTED}


@dataclass(frozen=True, slots=True)
class EvaluationCampaign:
    campaign_id: str
    benchmark_id: str
    task_ids: tuple[str, ...]
    modes: tuple[EvaluationMode, ...]
    freshness_epoch: int
    runner_protocol_version: str
    status: CampaignStatus
    freeze_digest: str | None = None
    status_reason: str | None = None

    def base_payload(self) -> dict[str, Any]:
        return {
            'campaign_id': self.campaign_id, 'benchmark_id': self.benchmark_id,
            'task_ids': list(self.task_ids), 'modes': [x.value for x in self.modes],
            'freshness_epoch': self.freshness_epoch, 'runner_protocol_version': self.runner_protocol_version,
        }

    def to_state(self) -> dict[str, Any]:
        return {
            **self.base_payload(), 'status': self.status.value,
            'freeze_digest': self.freeze_digest, 'status_reason': self.status_reason,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'EvaluationCampaign':
        return cls(
            campaign_id=str(state['campaign_id']), benchmark_id=str(state['benchmark_id']),
            task_ids=tuple(str(x) for x in state.get('task_ids', ())),
            modes=tuple(EvaluationMode(str(x)) for x in state.get('modes', ())),
            freshness_epoch=int(state['freshness_epoch']), runner_protocol_version=str(state['runner_protocol_version']),
            status=CampaignStatus(str(state['status'])),
            freeze_digest=None if state.get('freeze_digest') is None else str(state['freeze_digest']),
            status_reason=None if state.get('status_reason') is None else str(state['status_reason']),
        )


class EvaluationCampaignControlPlane:
    def __init__(
        self,
        *,
        repositories: RepositorySnapshotRegistry | None = None,
        tasks: CampaignTaskRegistry | None = None,
        campaigns: tuple[EvaluationCampaign, ...] = (),
        registry=None,
        artifacts=None,
        evaluation=None,
        runs=None,
        contamination=None,
        reproduction=None,
    ) -> None:
        self.repositories = repositories or RepositorySnapshotRegistry()
        self.tasks = tasks or CampaignTaskRegistry(repositories=self.repositories)
        self._campaigns: dict[str, EvaluationCampaign] = {}
        for row in campaigns:
            self._validate_campaign(row)
            if row.campaign_id in self._campaigns:
                raise ValueError('duplicate campaign id')
            self._campaigns[row.campaign_id] = row
        self.registry = registry
        self.artifacts = artifacts
        self.evaluation = evaluation
        self.runs = runs
        self.contamination = contamination
        self.reproduction = reproduction
        self.ingestor = None
        if registry is not None and artifacts is not None and evaluation is not None:
            from nolane.evaluation.campaign_contamination import CampaignContaminationLedger
            from nolane.evaluation.campaign_ingest import CampaignIngestor
            from nolane.evaluation.campaign_reproduction import CampaignReproductionLedger
            from nolane.evaluation.campaign_runner import CampaignRunLedger
            self.runs = self.runs or CampaignRunLedger(campaigns=self, tasks=self.tasks)
            self.contamination = self.contamination or CampaignContaminationLedger(tasks=self.tasks)
            self.reproduction = self.reproduction or CampaignReproductionLedger(
                registry=registry, artifacts=artifacts, campaigns=self,
            )
            self.ingestor = CampaignIngestor(
                registry=registry, artifacts=artifacts, evaluation=evaluation,
                repositories=self.repositories, tasks=self.tasks, campaigns=self,
                runs=self.runs, contamination=self.contamination,
            )

    def _validate_campaign(self, row: EvaluationCampaign) -> None:
        if not row.campaign_id.strip() or not row.benchmark_id.strip() or not row.runner_protocol_version.strip():
            raise ValueError('campaign identity, benchmark and runner protocol must be explicit')
        if row.freshness_epoch < 0 or not row.task_ids or not row.modes:
            raise ValueError('campaign requires tasks, modes and non-negative freshness epoch')
        if len(set(row.task_ids)) != len(row.task_ids) or len(set(row.modes)) != len(row.modes):
            raise ValueError('campaign task/mode declarations must be unique')
        for task_id in row.task_ids:
            self.tasks.get(task_id)
        if row.status is not CampaignStatus.DRAFT:
            if not row.freeze_digest:
                raise ValueError('non-draft campaign requires freeze digest')
            if row.freeze_digest != self._expected_freeze_digest(row):
                raise ValueError('campaign freeze digest mismatch')

    def _expected_freeze_digest(self, row: EvaluationCampaign) -> str:
        if self.tasks.partition_digest is None:
            raise ValueError('campaign partitions must be frozen')
        return canonical_digest({
            **row.base_payload(),
            'task_digests': [self.tasks.get(x).digest for x in row.task_ids],
            'partition_digest': self.tasks.partition_digest,
            'repository_digests': [self.repositories.get(self.tasks.get(x).repository_snapshot_id).digest for x in row.task_ids],
        })

    def create_campaign(self, **kwargs: Any) -> EvaluationCampaign:
        task_ids = tuple(str(x) for x in kwargs['task_ids'])
        modes = tuple(EvaluationMode(x) for x in kwargs['modes'])
        row = EvaluationCampaign(
            campaign_id=str(kwargs['campaign_id']), benchmark_id=str(kwargs['benchmark_id']),
            task_ids=task_ids, modes=modes, freshness_epoch=int(kwargs['freshness_epoch']),
            runner_protocol_version=str(kwargs['runner_protocol_version']), status=CampaignStatus.DRAFT,
        )
        self._validate_campaign(row)
        existing = self._campaigns.get(row.campaign_id)
        if existing is not None:
            if existing == row:
                return existing
            raise ValueError('campaign id cannot be rebound')
        self._campaigns[row.campaign_id] = row
        return row

    def get(self, campaign_id: str) -> EvaluationCampaign:
        try:
            return self._campaigns[str(campaign_id)]
        except KeyError as exc:
            raise KeyError(f'unknown evaluation campaign: {campaign_id}') from exc

    def campaigns(self) -> tuple[EvaluationCampaign, ...]:
        return tuple(self._campaigns[k] for k in sorted(self._campaigns))

    def replace_modes(self, campaign_id: str, modes: tuple[EvaluationMode, ...]) -> EvaluationCampaign:
        row = self.get(campaign_id)
        if row.status is not CampaignStatus.DRAFT:
            raise PermissionError('frozen campaign modes are immutable')
        new_modes = tuple(EvaluationMode(x) for x in modes)
        if not new_modes or len(set(new_modes)) != len(new_modes):
            raise ValueError('campaign modes must be non-empty and unique')
        updated = replace(row, modes=new_modes)
        self._campaigns[row.campaign_id] = updated
        return updated

    def freeze(self, campaign_id: str) -> EvaluationCampaign:
        row = self.get(campaign_id)
        if row.status is CampaignStatus.FROZEN:
            return row
        if row.status is not CampaignStatus.DRAFT:
            raise PermissionError('only draft campaign can be frozen')
        digest = self._expected_freeze_digest(row)
        updated = replace(row, status=CampaignStatus.FROZEN, freeze_digest=digest)
        self._campaigns[row.campaign_id] = updated
        return updated

    def start(self, campaign_id: str) -> EvaluationCampaign:
        return self._transition(campaign_id, CampaignStatus.FROZEN, CampaignStatus.RUNNING)

    def mark_evidence_ready(self, campaign_id: str) -> EvaluationCampaign:
        row = self.get(campaign_id)
        if row.status is CampaignStatus.EVIDENCE_READY:
            return row
        return self._transition(campaign_id, CampaignStatus.RUNNING, CampaignStatus.EVIDENCE_READY)

    def mark_reproducing(self, campaign_id: str) -> EvaluationCampaign:
        return self._transition(campaign_id, CampaignStatus.EVIDENCE_READY, CampaignStatus.REPRODUCING)

    def complete(self, campaign_id: str) -> EvaluationCampaign:
        row = self.get(campaign_id)
        if row.status not in (CampaignStatus.EVIDENCE_READY, CampaignStatus.REPRODUCING):
            raise PermissionError('campaign is not ready to complete')
        updated = replace(row, status=CampaignStatus.COMPLETE)
        self._campaigns[row.campaign_id] = updated
        return updated

    def quarantine(self, campaign_id: str, *, reason: str) -> EvaluationCampaign:
        row = self.get(campaign_id)
        if row.status in _TERMINAL:
            if row.status is CampaignStatus.QUARANTINED and row.status_reason == str(reason):
                return row
            raise PermissionError('terminal campaign state cannot be reactivated or rebound')
        updated = replace(row, status=CampaignStatus.QUARANTINED, status_reason=str(reason))
        self._campaigns[row.campaign_id] = updated
        return updated

    def _transition(self, campaign_id: str, expected: CampaignStatus, target: CampaignStatus) -> EvaluationCampaign:
        row = self.get(campaign_id)
        if row.status in _TERMINAL:
            raise PermissionError('terminal campaign state cannot transition')
        if row.status is not expected:
            raise PermissionError(f'campaign transition requires {expected.value}')
        updated = replace(row, status=target)
        self._campaigns[row.campaign_id] = updated
        return updated

    def is_empty(self) -> bool:
        return not self.repositories.snapshots() and not self.tasks.tasks() and not self._campaigns

    def to_state(self) -> dict[str, Any]:
        state: dict[str, Any] = {
            'repositories': self.repositories.to_state(),
            'tasks': self.tasks.to_state(),
            'campaigns': [row.to_state() for row in self.campaigns()],
        }
        if self.runs is not None:
            state['runs'] = self.runs.to_state()
        if self.contamination is not None:
            state['contamination'] = self.contamination.to_state()
        if self.reproduction is not None:
            state['reproduction'] = self.reproduction.to_state()
        if self.ingestor is not None:
            state['ingestor'] = self.ingestor.to_state()
        return state

    @classmethod
    def from_state(
        cls,
        *,
        state: Mapping[str, Any],
        repositories: RepositorySnapshotRegistry | None = None,
        tasks: CampaignTaskRegistry | None = None,
        registry=None,
        artifacts=None,
        evaluation=None,
    ) -> 'EvaluationCampaignControlPlane':
        repos = repositories or RepositorySnapshotRegistry.from_state(state.get('repositories', {}))
        task_registry = tasks or CampaignTaskRegistry.from_state(repositories=repos, state=state.get('tasks', {}))
        campaigns = tuple(EvaluationCampaign.from_state(x) for x in state.get('campaigns', ()))
        result = cls(
            repositories=repos, tasks=task_registry, campaigns=campaigns,
            registry=registry, artifacts=artifacts, evaluation=evaluation,
        )
        if registry is not None and artifacts is not None and evaluation is not None:
            from nolane.evaluation.campaign_contamination import CampaignContaminationLedger
            from nolane.evaluation.campaign_ingest import CampaignIngestor
            from nolane.evaluation.campaign_reproduction import CampaignReproductionLedger
            from nolane.evaluation.campaign_runner import CampaignRunLedger
            result.runs = CampaignRunLedger.from_state(
                campaigns=result, tasks=result.tasks, state=state.get('runs', {}),
            )
            result.contamination = CampaignContaminationLedger.from_state(
                tasks=result.tasks, state=state.get('contamination', {}),
            )
            result.reproduction = CampaignReproductionLedger.from_state(
                registry=registry, artifacts=artifacts, campaigns=result, state=state.get('reproduction', {}),
            )
            result.ingestor = CampaignIngestor.from_state(
                registry=registry, artifacts=artifacts, evaluation=evaluation,
                repositories=result.repositories, tasks=result.tasks, campaigns=result,
                runs=result.runs, contamination=result.contamination,
                state=state.get('ingestor', {}),
            )
        return result
