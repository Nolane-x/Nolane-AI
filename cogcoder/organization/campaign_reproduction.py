from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .artifacts import ArtifactStore
from .campaign import EvaluationCampaignControlPlane
from .registry import AgentRegistry
from .types import canonical_digest


@dataclass(frozen=True, slots=True)
class CampaignReproductionPackage:
    package_id: str
    campaign_id: str
    campaign_freeze_digest: str
    observation_ids: tuple[str, ...]
    source_revision_digests: tuple[str, ...]
    task_set_digest: str
    runner_protocol_digest: str
    environment_digest: str
    command_manifest_digest: str
    artifact_ids: tuple[str, ...]
    artifact_bundle_digest: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'package_id': self.package_id, 'campaign_id': self.campaign_id,
            'campaign_freeze_digest': self.campaign_freeze_digest,
            'observation_ids': list(self.observation_ids),
            'source_revision_digests': list(self.source_revision_digests),
            'task_set_digest': self.task_set_digest, 'runner_protocol_digest': self.runner_protocol_digest,
            'environment_digest': self.environment_digest, 'command_manifest_digest': self.command_manifest_digest,
            'artifact_ids': list(self.artifact_ids), 'artifact_bundle_digest': self.artifact_bundle_digest,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CampaignReproductionPackage':
        row = cls(
            package_id=str(state['package_id']), campaign_id=str(state['campaign_id']),
            campaign_freeze_digest=str(state['campaign_freeze_digest']),
            observation_ids=tuple(str(x) for x in state.get('observation_ids', ())),
            source_revision_digests=tuple(str(x) for x in state.get('source_revision_digests', ())),
            task_set_digest=str(state['task_set_digest']), runner_protocol_digest=str(state['runner_protocol_digest']),
            environment_digest=str(state['environment_digest']), command_manifest_digest=str(state['command_manifest_digest']),
            artifact_ids=tuple(str(x) for x in state.get('artifact_ids', ())),
            artifact_bundle_digest=str(state['artifact_bundle_digest']), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('campaign reproduction package digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class CampaignReproductionReceipt:
    reproduction_id: str
    package_id: str
    evaluator_id: str
    reproduced: bool
    independent: bool
    artifact_bundle_digest: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'reproduction_id': self.reproduction_id, 'package_id': self.package_id,
            'evaluator_id': self.evaluator_id, 'reproduced': self.reproduced,
            'independent': self.independent, 'artifact_bundle_digest': self.artifact_bundle_digest,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'CampaignReproductionReceipt':
        row = cls(
            reproduction_id=str(state['reproduction_id']), package_id=str(state['package_id']),
            evaluator_id=str(state['evaluator_id']), reproduced=bool(state['reproduced']),
            independent=bool(state['independent']), artifact_bundle_digest=str(state['artifact_bundle_digest']),
            digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('campaign reproduction receipt digest mismatch')
        return row


class CampaignReproductionLedger:
    def __init__(
        self,
        *,
        registry: AgentRegistry,
        artifacts: ArtifactStore,
        campaigns: EvaluationCampaignControlPlane,
        packages: tuple[CampaignReproductionPackage, ...] = (),
        receipts: tuple[CampaignReproductionReceipt, ...] = (),
    ) -> None:
        self.registry = registry
        self.artifacts = artifacts
        self.campaigns = campaigns
        self._packages: dict[str, CampaignReproductionPackage] = {}
        self._receipts: dict[str, CampaignReproductionReceipt] = {}
        for row in packages:
            self._validate_package(row)
            if row.package_id in self._packages:
                raise ValueError('duplicate campaign reproduction package id')
            self._packages[row.package_id] = row
        for row in receipts:
            package = self.get_package(row.package_id)
            self._validate_receipt(row, package)
            if row.reproduction_id in self._receipts:
                raise ValueError('duplicate campaign reproduction receipt id')
            self._receipts[row.reproduction_id] = row

    def _artifact_bundle_digest(self, artifact_ids: tuple[str, ...]) -> str:
        rows = [self.artifacts.get(x) for x in artifact_ids]
        return canonical_digest([{'artifact_id': row.artifact_id, 'digest': row.digest} for row in rows])

    def _validate_package(self, row: CampaignReproductionPackage) -> None:
        campaign = self.campaigns.get(row.campaign_id)
        if not campaign.freeze_digest or row.campaign_freeze_digest != campaign.freeze_digest:
            raise ValueError('reproduction package campaign freeze mismatch')
        for value in (
            row.package_id, row.task_set_digest, row.runner_protocol_digest,
            row.environment_digest, row.command_manifest_digest,
        ):
            if not str(value).strip():
                raise ValueError('reproduction package identity/digests must be explicit')
        if not row.observation_ids or not row.source_revision_digests or not row.artifact_ids:
            raise ValueError('reproduction package requires observations, source revisions and artifacts')
        if self._artifact_bundle_digest(row.artifact_ids) != row.artifact_bundle_digest:
            raise ValueError('reproduction package artifact bundle digest mismatch')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('campaign reproduction package digest mismatch')

    def _validate_receipt(self, row: CampaignReproductionReceipt, package: CampaignReproductionPackage) -> None:
        permanent_ids = {identity.agent_id for identity in self.registry.identities()}
        expected_independent = bool(row.evaluator_id and row.evaluator_id not in permanent_ids)
        if row.independent != expected_independent:
            raise ValueError('reproduction independence disposition is non-canonical')
        if row.artifact_bundle_digest != package.artifact_bundle_digest:
            raise ValueError('reproduction receipt artifact bundle mismatch')
        if canonical_digest(row.payload()) != row.digest:
            raise ValueError('campaign reproduction receipt digest mismatch')

    def create_package(self, **kwargs: Any) -> CampaignReproductionPackage:
        campaign = self.campaigns.get(str(kwargs['campaign_id']))
        if not campaign.freeze_digest:
            raise PermissionError('campaign must be frozen before packaging reproduction evidence')
        artifact_ids = tuple(str(x) for x in kwargs['artifact_ids'])
        bundle_digest = self._artifact_bundle_digest(artifact_ids)
        row0 = CampaignReproductionPackage(
            package_id=str(kwargs['package_id']), campaign_id=campaign.campaign_id,
            campaign_freeze_digest=campaign.freeze_digest,
            observation_ids=tuple(str(x) for x in kwargs['observation_ids']),
            source_revision_digests=tuple(str(x) for x in kwargs['source_revision_digests']),
            task_set_digest=str(kwargs['task_set_digest']), runner_protocol_digest=str(kwargs['runner_protocol_digest']),
            environment_digest=str(kwargs['environment_digest']), command_manifest_digest=str(kwargs['command_manifest_digest']),
            artifact_ids=artifact_ids, artifact_bundle_digest=bundle_digest, digest='',
        )
        row = CampaignReproductionPackage(
            package_id=row0.package_id, campaign_id=row0.campaign_id,
            campaign_freeze_digest=row0.campaign_freeze_digest, observation_ids=row0.observation_ids,
            source_revision_digests=row0.source_revision_digests, task_set_digest=row0.task_set_digest,
            runner_protocol_digest=row0.runner_protocol_digest, environment_digest=row0.environment_digest,
            command_manifest_digest=row0.command_manifest_digest, artifact_ids=row0.artifact_ids,
            artifact_bundle_digest=row0.artifact_bundle_digest, digest=canonical_digest(row0.payload()),
        )
        self._validate_package(row)
        existing = self._packages.get(row.package_id)
        if existing is not None:
            if existing == row: return existing
            raise ValueError('campaign reproduction package id cannot be rebound')
        self._packages[row.package_id] = row
        return row

    def get_package(self, package_id: str) -> CampaignReproductionPackage:
        try:
            return self._packages[str(package_id)]
        except KeyError as exc:
            raise KeyError(f'unknown campaign reproduction package: {package_id}') from exc

    def record_reproduction(
        self,
        *,
        reproduction_id: str,
        package_id: str,
        evaluator_id: str,
        reproduced: bool,
        artifact_bundle_digest: str,
    ) -> CampaignReproductionReceipt:
        package = self.get_package(package_id)
        evaluator_id = str(evaluator_id).strip()
        permanent_ids = {identity.agent_id for identity in self.registry.identities()}
        if not evaluator_id or evaluator_id in permanent_ids:
            raise PermissionError('independent reproduction requires evaluator outside permanent organization identities')
        row0 = CampaignReproductionReceipt(
            reproduction_id=str(reproduction_id), package_id=package.package_id, evaluator_id=evaluator_id,
            reproduced=bool(reproduced), independent=True, artifact_bundle_digest=str(artifact_bundle_digest), digest='',
        )
        row = CampaignReproductionReceipt(
            reproduction_id=row0.reproduction_id, package_id=row0.package_id, evaluator_id=row0.evaluator_id,
            reproduced=row0.reproduced, independent=row0.independent,
            artifact_bundle_digest=row0.artifact_bundle_digest, digest=canonical_digest(row0.payload()),
        )
        self._validate_receipt(row, package)
        existing = self._receipts.get(row.reproduction_id)
        if existing is not None:
            if existing == row: return existing
            raise ValueError('campaign reproduction receipt id cannot be rebound')
        self._receipts[row.reproduction_id] = row
        return row

    def to_state(self) -> dict[str, Any]:
        return {
            'packages': [self._packages[k].to_state() for k in sorted(self._packages)],
            'receipts': [self._receipts[k].to_state() for k in sorted(self._receipts)],
        }

    @classmethod
    def from_state(
        cls, *, registry: AgentRegistry, artifacts: ArtifactStore, campaigns: EvaluationCampaignControlPlane,
        state: Mapping[str, Any],
    ) -> 'CampaignReproductionLedger':
        return cls(
            registry=registry, artifacts=artifacts, campaigns=campaigns,
            packages=tuple(CampaignReproductionPackage.from_state(x) for x in state.get('packages', ())),
            receipts=tuple(CampaignReproductionReceipt.from_state(x) for x in state.get('receipts', ())),
        )
