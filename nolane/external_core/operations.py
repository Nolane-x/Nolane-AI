from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.external_core.artifacts import ArtifactStore
from nolane.external_core.assurance import AssuranceControlPlane, AssuranceDisposition
from nolane.external_core.data_operations import DataOperationsLedger
from nolane.memory.skills import SkillEvolutionEngine, SkillRecord
from nolane.external_core.infrastructure_operations import InfrastructureOperationsLedger
from nolane.external_core.operations_profiles import OperationsProfileRegistry
from nolane.organization.identity import AgentRegistry
from nolane.external_core.reliability_operations import ReliabilityOperationsLedger
from nolane.core.canonical_digest import canonical_digest


class OperationalReadinessDisposition(str, Enum):
    READY = 'ready'
    READY_WITH_ASSURANCE_OVERRIDE = 'ready_with_assurance_override'
    BLOCKED = 'blocked'


@dataclass(frozen=True, slots=True)
class OperationalReadinessReceipt:
    readiness_id: str
    migration_receipt_ids: tuple[str, ...]
    release_readiness_receipt_id: str
    reliability_matrix_receipt_id: str
    performance_claim_receipt_ids: tuple[str, ...]
    assurance_subject_id: str
    assurance_disposition: str
    disposition: OperationalReadinessDisposition
    reasons: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'readiness_id': self.readiness_id,
            'migration_receipt_ids': list(self.migration_receipt_ids),
            'release_readiness_receipt_id': self.release_readiness_receipt_id,
            'reliability_matrix_receipt_id': self.reliability_matrix_receipt_id,
            'performance_claim_receipt_ids': list(self.performance_claim_receipt_ids),
            'assurance_subject_id': self.assurance_subject_id,
            'assurance_disposition': self.assurance_disposition,
            'disposition': self.disposition.value,
            'reasons': list(self.reasons),
        }

    def to_state(self) -> dict[str, Any]: return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'OperationalReadinessReceipt':
        row = cls(
            readiness_id=str(state['readiness_id']),
            migration_receipt_ids=tuple(str(x) for x in state.get('migration_receipt_ids', ())),
            release_readiness_receipt_id=str(state['release_readiness_receipt_id']),
            reliability_matrix_receipt_id=str(state['reliability_matrix_receipt_id']),
            performance_claim_receipt_ids=tuple(str(x) for x in state.get('performance_claim_receipt_ids', ())),
            assurance_subject_id=str(state['assurance_subject_id']),
            assurance_disposition=str(state['assurance_disposition']),
            disposition=OperationalReadinessDisposition(str(state['disposition'])),
            reasons=tuple(str(x) for x in state.get('reasons', ())), digest=str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest: raise ValueError('operational readiness digest mismatch')
        return row


class OperationsControlPlane:
    def __init__(
        self, *, registry: AgentRegistry, artifacts: ArtifactStore, evolution: SkillEvolutionEngine,
        assurance: AssuranceControlPlane, profiles: OperationsProfileRegistry | None = None,
        data: DataOperationsLedger | None = None, infrastructure: InfrastructureOperationsLedger | None = None,
        reliability: ReliabilityOperationsLedger | None = None,
        readiness: tuple[OperationalReadinessReceipt, ...] = (),
    ) -> None:
        self.registry = registry; self.artifacts = artifacts; self.evolution = evolution; self.assurance = assurance
        self.profiles = profiles or OperationsProfileRegistry(registry)
        self.data = data or DataOperationsLedger(registry=registry, artifacts=artifacts)
        self.infrastructure = infrastructure or InfrastructureOperationsLedger(registry=registry, artifacts=artifacts)
        self.reliability = reliability or ReliabilityOperationsLedger(registry=registry)
        self._readiness: dict[str, OperationalReadinessReceipt] = {row.readiness_id: row for row in readiness}

    @property
    def digest(self): return canonical_digest(self.to_state())

    def assess_readiness(
        self, *, readiness_id: str, migration_receipt_ids: tuple[str, ...], release_readiness_receipt_id: str,
        reliability_matrix_receipt_id: str, performance_claim_receipt_ids: tuple[str, ...], assurance_subject_id: str,
    ) -> OperationalReadinessReceipt:
        if not all(str(x).strip() for x in (readiness_id, release_readiness_receipt_id, reliability_matrix_receipt_id, assurance_subject_id)):
            raise ValueError('operational readiness requires explicit identifiers')
        if str(readiness_id) in self._readiness: return self._readiness[str(readiness_id)]
        reasons: list[str] = []
        for receipt_id in migration_receipt_ids:
            if not self.data.migration_receipt(receipt_id).ready: reasons.append('migration_not_ready')
        if not self.infrastructure.release_receipt(release_readiness_receipt_id).ready: reasons.append('release_not_ready')
        if not self.reliability.matrix_receipt(reliability_matrix_receipt_id).ready: reasons.append('reliability_matrix_not_ready')
        for receipt_id in performance_claim_receipt_ids:
            if not self.reliability.performance_claim(receipt_id).valid: reasons.append('performance_claim_not_valid')
        assurance_disposition = self.assurance.effective_disposition(assurance_subject_id)
        if assurance_disposition not in {AssuranceDisposition.VERIFIED, AssuranceDisposition.OVERRIDDEN}:
            reasons.append('assurance_not_verified_or_overridden')
        reasons = list(dict.fromkeys(reasons))
        if reasons:
            disposition = OperationalReadinessDisposition.BLOCKED
        elif assurance_disposition is AssuranceDisposition.OVERRIDDEN:
            disposition = OperationalReadinessDisposition.READY_WITH_ASSURANCE_OVERRIDE
        else:
            disposition = OperationalReadinessDisposition.READY
        payload = {
            'readiness_id': str(readiness_id), 'migration_receipt_ids': [str(x) for x in migration_receipt_ids],
            'release_readiness_receipt_id': str(release_readiness_receipt_id),
            'reliability_matrix_receipt_id': str(reliability_matrix_receipt_id),
            'performance_claim_receipt_ids': [str(x) for x in performance_claim_receipt_ids],
            'assurance_subject_id': str(assurance_subject_id), 'assurance_disposition': assurance_disposition.value,
            'disposition': disposition.value, 'reasons': reasons,
        }
        row = OperationalReadinessReceipt(
            payload['readiness_id'], tuple(payload['migration_receipt_ids']), payload['release_readiness_receipt_id'],
            payload['reliability_matrix_receipt_id'], tuple(payload['performance_claim_receipt_ids']),
            payload['assurance_subject_id'], payload['assurance_disposition'], disposition, tuple(reasons), canonical_digest(payload),
        )
        self._readiness[row.readiness_id] = row; return row

    def readiness_receipt(self, readiness_id: str) -> OperationalReadinessReceipt:
        try: return self._readiness[str(readiness_id)]
        except KeyError as exc: raise KeyError(f'unknown operational readiness receipt: {readiness_id}') from exc

    def propose_personal_skill(self, *, agent_id: str, name: str, body: str,
                               object_refs: tuple[str, ...], evidence_refs: tuple[str, ...]) -> SkillRecord:
        profile = self.profiles.get(agent_id)
        if not object_refs or not evidence_refs: raise ValueError('operational skill requires object and evidence refs')
        return self.evolution.propose(owner_agent_id=profile.agent_id, region=profile.region, name=name, body=body)

    def to_state(self):
        return {'profiles': self.profiles.to_state(), 'data': self.data.to_state(),
                'infrastructure': self.infrastructure.to_state(), 'reliability': self.reliability.to_state(),
                'readiness': [self._readiness[k].to_state() for k in sorted(self._readiness)]}

    @classmethod
    def from_state(cls, *, registry: AgentRegistry, artifacts: ArtifactStore, evolution: SkillEvolutionEngine,
                   assurance: AssuranceControlPlane, state: Mapping[str, Any]):
        profiles = OperationsProfileRegistry.from_state(registry, state.get('profiles', {}))
        data = DataOperationsLedger.from_state(registry=registry, artifacts=artifacts, state=state.get('data', {}))
        infrastructure = InfrastructureOperationsLedger.from_state(registry=registry, artifacts=artifacts, state=state.get('infrastructure', {}))
        reliability = ReliabilityOperationsLedger.from_state(registry=registry, state=state.get('reliability', {}))
        readiness = tuple(OperationalReadinessReceipt.from_state(x) for x in state.get('readiness', ()))
        result = cls(registry=registry, artifacts=artifacts, evolution=evolution, assurance=assurance,
                     profiles=profiles, data=data, infrastructure=infrastructure, reliability=reliability, readiness=readiness)
        for row in readiness:
            for rid in row.migration_receipt_ids: data.migration_receipt(rid)
            infrastructure.release_receipt(row.release_readiness_receipt_id)
            reliability.matrix_receipt(row.reliability_matrix_receipt_id)
            for rid in row.performance_claim_receipt_ids: reliability.performance_claim(rid)
            assurance.evidence.get_subject(row.assurance_subject_id)
        return result


COMPONENT_ID = "external.operations"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.operations"
