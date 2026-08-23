from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .artifacts import ArtifactStore
from .campaign import CampaignStatus, EvaluationCampaignControlPlane
from .campaign_contamination import CampaignContaminationLedger
from .campaign_repository import RepositorySnapshotRegistry
from .campaign_runner import CampaignRunLedger
from .campaign_tasks import CampaignPartition, CampaignTaskRegistry
from .evaluation import EvaluationScalingControlPlane
from .evaluation_regimes import BenchmarkDomain, EvidenceProvenanceClass, EvaluationMode
from .registry import AgentRegistry
from .types import EvidenceRecord, canonical_digest


@dataclass(frozen=True, slots=True)
class CampaignIngestReceipt:
    receipt_id: str
    campaign_id: str
    mode: EvaluationMode
    regime_id: str
    observation_id: str
    run_ids: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'receipt_id': self.receipt_id, 'campaign_id': self.campaign_id,
            'mode': self.mode.value, 'regime_id': self.regime_id,
            'observation_id': self.observation_id, 'run_ids': list(self.run_ids),
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CampaignIngestReceipt':
        row = cls(
            receipt_id=str(state['receipt_id']), campaign_id=str(state['campaign_id']),
            mode=EvaluationMode(str(state['mode'])), regime_id=str(state['regime_id']),
            observation_id=str(state['observation_id']), run_ids=tuple(str(x) for x in state.get('run_ids', ())),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('campaign ingest receipt digest mismatch')
        return row


class CampaignIngestor:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        artifacts: ArtifactStore,
        evaluation: EvaluationScalingControlPlane,
        repositories: RepositorySnapshotRegistry,
        tasks: CampaignTaskRegistry,
        campaigns: EvaluationCampaignControlPlane,
        runs: CampaignRunLedger,
        contamination: CampaignContaminationLedger,
        receipts: tuple[CampaignIngestReceipt, ...] = (),
    ) -> None:
        self.registry = registry
        self.artifacts = artifacts
        self.evaluation = evaluation
        self.repositories = repositories
        self.tasks = tasks
        self.campaigns = campaigns
        self.runs = runs
        self.contamination = contamination
        self._receipts: dict[str, CampaignIngestReceipt] = {}
        for row in receipts:
            self.campaigns.get(row.campaign_id)
            self.evaluation.regimes.get(row.regime_id)
            self.evaluation.evidence.get_observation(row.observation_id)
            if row.receipt_id in self._receipts:
                raise ValueError('duplicate campaign ingest receipt')
            self._receipts[row.receipt_id] = row

    def get_receipt(self, receipt_id: str) -> CampaignIngestReceipt:
        try:
            return self._receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f'unknown campaign ingest receipt: {receipt_id}') from exc

    def receipts(self) -> tuple[CampaignIngestReceipt, ...]:
        return tuple(self._receipts[key] for key in sorted(self._receipts))

    def _complete_rows(self, campaign_id: str, mode: EvaluationMode):
        campaign = self.campaigns.get(campaign_id)
        rows = self.runs.receipts_for(campaign_id, mode)
        by_task = {spec.task_id: (spec, receipt) for spec, receipt in rows}
        if set(by_task) != set(campaign.task_ids) or len(rows) != len(campaign.task_ids):
            raise PermissionError('campaign mode is incomplete for frozen task set')
        return tuple(by_task[task_id] for task_id in campaign.task_ids)

    def _all_modes_complete(self, campaign_id: str) -> bool:
        campaign = self.campaigns.get(campaign_id)
        for mode in campaign.modes:
            rows = self.runs.receipts_for(campaign_id, mode)
            if {spec.task_id for spec, _ in rows} != set(campaign.task_ids):
                return False
        return True

    def ingest_mode(
        self,
        *,
        campaign_id: str,
        mode: EvaluationMode,
        provenance_class: EvidenceProvenanceClass,
        evidence: EvidenceRecord,
        external_evaluator_id: str | None,
    ) -> CampaignIngestReceipt:
        campaign = self.campaigns.get(campaign_id)
        mode = EvaluationMode(mode)
        provenance = EvidenceProvenanceClass(provenance_class)
        if campaign.status not in (CampaignStatus.RUNNING, CampaignStatus.EVIDENCE_READY):
            raise PermissionError('campaign must be RUNNING or EVIDENCE_READY for ingestion')
        if mode not in campaign.modes:
            raise PermissionError('ingested mode was not declared by campaign')
        finding = self.contamination.latest_for(campaign.campaign_id)
        if finding.quarantined:
            if campaign.status not in (CampaignStatus.QUARANTINED, CampaignStatus.COMPLETE):
                self.campaigns.quarantine(campaign.campaign_id, reason='heldout_contamination')
            raise PermissionError('contaminated campaign evidence cannot be ingested')
        if provenance is EvidenceProvenanceClass.EXTERNAL_INDEPENDENT:
            permanent_ids = {row.agent_id for row in self.registry.identities()}
            if not external_evaluator_id or str(external_evaluator_id) in permanent_ids:
                raise PermissionError('external-independent evaluator must be outside permanent organization identities')
        self.registry.get(evidence.verifier_agent_id)
        rows = self._complete_rows(campaign.campaign_id, mode)
        producer_revisions = {spec.producer_revision for spec, _ in rows}
        if len(producer_revisions) != 1:
            raise ValueError('campaign mode requires one exact producer revision')

        task_rows = [self.tasks.get(task_id) for task_id in campaign.task_ids]
        repo_rows = [self.repositories.get(task.repository_snapshot_id) for task in task_rows]
        for spec, receipt in rows:
            repo = self.repositories.get(self.tasks.get(spec.task_id).repository_snapshot_id)
            if spec.toolchain_digest != repo.toolchain_digest:
                raise ValueError('campaign run toolchain does not match frozen repository snapshot')
            for artifact_id in receipt.output_artifact_ids:
                self.artifacts.get(artifact_id)

        domains = {task.domain for task in task_rows}
        domain = next(iter(domains)) if len(domains) == 1 else BenchmarkDomain.CROSS_DOMAIN
        task_set_digest = canonical_digest([{'task_id': task.task_id, 'digest': task.digest} for task in task_rows])
        repository_revision_digest = canonical_digest([
            {'snapshot_id': repo.snapshot_id, 'revision': repo.revision, 'digest': repo.digest} for repo in repo_rows
        ])
        tool_envelope_digest = canonical_digest([
            {'task_id': task.task_id, 'tools': list(task.allowed_tools), 'cores': list(task.allowed_cores)} for task in task_rows
        ])
        budget_payload = {
            'compute_budget_units': sum(task.compute_budget_units for task in task_rows),
            'tool_call_budget': sum(task.tool_call_budget for task in task_rows),
            'external_core_budget': sum(task.external_core_budget for task in task_rows),
            'wall_clock_budget_ms': sum(task.wall_clock_budget_ms for task in task_rows),
            'active_agent_budget': max(task.active_agent_budget for task in task_rows),
        }
        regime_seed = {
            'campaign_freeze_digest': campaign.freeze_digest, 'provenance_class': provenance.value,
            'task_set_digest': task_set_digest, 'repository_revision_digest': repository_revision_digest,
            'tool_envelope_digest': tool_envelope_digest,
        }
        regime_id = 'campaign-regime-' + canonical_digest(regime_seed)[:24]
        heldout = all(self.tasks.partition_of(task.task_id) is CampaignPartition.HELDOUT for task in task_rows)
        regime = self.evaluation.regimes.register(
            regime_id=regime_id, benchmark_id=campaign.benchmark_id, domain=domain,
            task_set_digest=task_set_digest, repository_revision_digest=repository_revision_digest,
            tool_envelope_digest=tool_envelope_digest, freshness_epoch=campaign.freshness_epoch,
            evaluator_protocol_version=campaign.runner_protocol_version, provenance_class=provenance,
            fresh=True, heldout=heldout, **budget_payload,
        )

        receipts = [receipt for _, receipt in rows]
        pass_count = sum(1 for receipt in receipts if receipt.passed)
        task_count = len(receipts)
        artifact_ids = tuple(sorted({artifact_id for receipt in receipts for artifact_id in receipt.output_artifact_ids}))
        energies = [receipt.energy_joules for receipt in receipts]
        energy = None if any(value is None for value in energies) else sum(float(value) for value in energies if value is not None)
        observation_seed = {
            'campaign_id': campaign.campaign_id, 'mode': mode.value,
            'producer_revision': next(iter(producer_revisions)),
            'run_digests': [receipt.digest for receipt in receipts], 'regime_digest': regime.regime_digest,
        }
        observation_id = 'campaign-observation-' + canonical_digest(observation_seed)[:24]
        observation = self.evaluation.evidence.record_observation(
            observation_id=observation_id, regime_id=regime.regime_id, mode=mode,
            producer_revision=next(iter(producer_revisions)), score=pass_count / task_count,
            task_count=task_count, pass_count=pass_count,
            false_accepts=sum(receipt.false_accepts for receipt in receipts),
            regressions=sum(receipt.regressions for receipt in receipts),
            compute_units=sum(receipt.compute_units for receipt in receipts),
            tool_calls=sum(receipt.tool_calls for receipt in receipts),
            external_core_calls=sum(receipt.external_core_calls for receipt in receipts),
            wall_clock_ms=sum(receipt.wall_clock_ms for receipt in receipts), energy_joules=energy,
            active_agents=max(receipt.active_agents for receipt in receipts),
            evidence_artifact_ids=artifact_ids, evidence=evidence,
            external_evaluator_id=external_evaluator_id,
        )
        if campaign.status is CampaignStatus.RUNNING and self._all_modes_complete(campaign.campaign_id):
            self.campaigns.mark_evidence_ready(campaign.campaign_id)
        payload0 = {
            'campaign_id': campaign.campaign_id, 'mode': mode.value, 'regime_id': regime.regime_id,
            'observation_id': observation.observation_id, 'run_ids': [spec.run_id for spec, _ in rows],
        }
        receipt_id = 'campaign-ingest-' + canonical_digest(payload0)[:24]
        payload = {'receipt_id': receipt_id, **payload0}
        row = CampaignIngestReceipt(
            receipt_id=receipt_id, campaign_id=campaign.campaign_id, mode=mode,
            regime_id=regime.regime_id, observation_id=observation.observation_id,
            run_ids=tuple(payload0['run_ids']), digest=canonical_digest(payload),
        )
        existing = self._receipts.get(row.receipt_id)
        if existing is not None:
            if existing == row: return existing
            raise ValueError('campaign ingest receipt cannot be rebound')
        self._receipts[row.receipt_id] = row
        return row

    def to_state(self) -> dict[str, Any]:
        return {'receipts': [row.to_state() for row in self.receipts()]}

    @classmethod
    def from_state(cls, *, state: Mapping[str, Any], **kwargs: Any) -> 'CampaignIngestor':
        return cls(receipts=tuple(CampaignIngestReceipt.from_state(x) for x in state.get('receipts', ())), **kwargs)
