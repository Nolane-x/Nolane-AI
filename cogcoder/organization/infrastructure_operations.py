from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .artifacts import ArtifactStore
from .registry import AgentRegistry
from .types import canonical_digest


@dataclass(frozen=True, slots=True)
class BuildManifest:
    build_id: str
    producer_agent_id: str
    source_digest: str
    dependency_lock_digest: str
    toolchain_digest: str
    environment_digest: str
    build_command_digest: str
    artifact_id: str
    artifact_digest: str
    evidence_refs: tuple[str, ...]
    digest: str
    def payload(self) -> dict[str, Any]:
        return {'build_id': self.build_id, 'producer_agent_id': self.producer_agent_id, 'source_digest': self.source_digest,
                'dependency_lock_digest': self.dependency_lock_digest, 'toolchain_digest': self.toolchain_digest,
                'environment_digest': self.environment_digest, 'build_command_digest': self.build_command_digest,
                'artifact_id': self.artifact_id, 'artifact_digest': self.artifact_digest, 'evidence_refs': list(self.evidence_refs)}
    def to_state(self): return {**self.payload(), 'digest': self.digest}
    @classmethod
    def from_state(cls, state: Mapping[str, Any]):
        row = cls(str(state['build_id']), str(state['producer_agent_id']), str(state['source_digest']), str(state['dependency_lock_digest']),
                  str(state['toolchain_digest']), str(state['environment_digest']), str(state['build_command_digest']), str(state['artifact_id']),
                  str(state['artifact_digest']), tuple(str(x) for x in state.get('evidence_refs', ())), str(state['digest']))
        if canonical_digest(row.payload()) != row.digest: raise ValueError('build manifest digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class BuildReproductionReceipt:
    receipt_id: str
    original_build_id: str
    replay_build_id: str
    reproducible: bool
    reasons: tuple[str, ...]
    digest: str
    def payload(self): return {'receipt_id': self.receipt_id, 'original_build_id': self.original_build_id, 'replay_build_id': self.replay_build_id, 'reproducible': self.reproducible, 'reasons': list(self.reasons)}
    def to_state(self): return {**self.payload(), 'digest': self.digest}
    @classmethod
    def from_state(cls, state):
        row = cls(str(state['receipt_id']), str(state['original_build_id']), str(state['replay_build_id']), bool(state['reproducible']), tuple(str(x) for x in state.get('reasons', ())), str(state['digest']))
        if canonical_digest(row.payload()) != row.digest: raise ValueError('build reproduction digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ObservabilityBundle:
    bundle_id: str
    producer_agent_id: str
    log_schema_digest: str
    metric_schema_digest: str
    trace_schema_digest: str
    slo_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    digest: str
    def payload(self):
        return {'bundle_id': self.bundle_id, 'producer_agent_id': self.producer_agent_id, 'log_schema_digest': self.log_schema_digest,
                'metric_schema_digest': self.metric_schema_digest, 'trace_schema_digest': self.trace_schema_digest,
                'slo_refs': list(self.slo_refs), 'evidence_refs': list(self.evidence_refs)}
    def to_state(self): return {**self.payload(), 'digest': self.digest}
    @classmethod
    def from_state(cls, state):
        row = cls(str(state['bundle_id']), str(state['producer_agent_id']), str(state['log_schema_digest']), str(state['metric_schema_digest']),
                  str(state['trace_schema_digest']), tuple(str(x) for x in state.get('slo_refs', ())), tuple(str(x) for x in state.get('evidence_refs', ())), str(state['digest']))
        if canonical_digest(row.payload()) != row.digest: raise ValueError('observability bundle digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ReleaseCandidate:
    release_id: str
    producer_agent_id: str
    build_reproduction_receipt_id: str
    package_artifact_id: str
    config_digest: str
    deployment_topology_digest: str
    rollback_artifact_id: str
    observability_bundle_id: str
    evidence_refs: tuple[str, ...]
    digest: str
    def payload(self):
        return {'release_id': self.release_id, 'producer_agent_id': self.producer_agent_id,
                'build_reproduction_receipt_id': self.build_reproduction_receipt_id, 'package_artifact_id': self.package_artifact_id,
                'config_digest': self.config_digest, 'deployment_topology_digest': self.deployment_topology_digest,
                'rollback_artifact_id': self.rollback_artifact_id, 'observability_bundle_id': self.observability_bundle_id,
                'evidence_refs': list(self.evidence_refs)}
    def to_state(self): return {**self.payload(), 'digest': self.digest}
    @classmethod
    def from_state(cls, state):
        row = cls(str(state['release_id']), str(state['producer_agent_id']), str(state['build_reproduction_receipt_id']), str(state['package_artifact_id']),
                  str(state['config_digest']), str(state['deployment_topology_digest']), str(state.get('rollback_artifact_id', '')),
                  str(state.get('observability_bundle_id', '')), tuple(str(x) for x in state.get('evidence_refs', ())), str(state['digest']))
        if canonical_digest(row.payload()) != row.digest: raise ValueError('release candidate digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ReleaseReadinessReceipt:
    receipt_id: str
    release_id: str
    ready: bool
    reasons: tuple[str, ...]
    digest: str
    def payload(self): return {'receipt_id': self.receipt_id, 'release_id': self.release_id, 'ready': self.ready, 'reasons': list(self.reasons)}
    def to_state(self): return {**self.payload(), 'digest': self.digest}
    @classmethod
    def from_state(cls, state):
        row = cls(str(state['receipt_id']), str(state['release_id']), bool(state['ready']), tuple(str(x) for x in state.get('reasons', ())), str(state['digest']))
        if canonical_digest(row.payload()) != row.digest: raise ValueError('release readiness digest mismatch')
        return row


class InfrastructureOperationsLedger:
    def __init__(self, *, registry: AgentRegistry, artifacts: ArtifactStore) -> None:
        self.registry = registry; self.artifacts = artifacts
        self._builds: dict[str, BuildManifest] = {}
        self._reproductions: dict[str, BuildReproductionReceipt] = {}
        self._observability: dict[str, ObservabilityBundle] = {}
        self._releases: dict[str, ReleaseCandidate] = {}
        self._release_receipts: dict[str, ReleaseReadinessReceipt] = {}
        self._repro_counter = 0; self._release_counter = 0

    @property
    def digest(self): return canonical_digest(self.to_state())
    def _require_infra(self, agent_id: str):
        if self.registry.get(agent_id).region != 'infrastructure-release': raise PermissionError('infrastructure operations require Infrastructure-region authority')

    def register_build(self, *, build_id: str, producer_agent_id: str, source_digest: str, dependency_lock_digest: str,
                       toolchain_digest: str, environment_digest: str, build_command_digest: str, artifact_id: str,
                       evidence_refs: tuple[str, ...]) -> BuildManifest:
        self._require_infra(producer_agent_id)
        if not all(str(x).strip() for x in (build_id, source_digest, dependency_lock_digest, toolchain_digest, environment_digest, build_command_digest, artifact_id)) or not evidence_refs:
            raise ValueError('build manifest requires explicit basis, artifact and evidence')
        artifact = self.artifacts.get(artifact_id)
        if artifact.producer_agent_id != str(producer_agent_id): raise ValueError('build artifact producer mismatch')
        payload = {'build_id': str(build_id), 'producer_agent_id': str(producer_agent_id), 'source_digest': str(source_digest),
                   'dependency_lock_digest': str(dependency_lock_digest), 'toolchain_digest': str(toolchain_digest),
                   'environment_digest': str(environment_digest), 'build_command_digest': str(build_command_digest),
                   'artifact_id': str(artifact_id), 'artifact_digest': artifact.digest, 'evidence_refs': [str(x) for x in evidence_refs]}
        row = BuildManifest(payload['build_id'], payload['producer_agent_id'], payload['source_digest'], payload['dependency_lock_digest'],
                            payload['toolchain_digest'], payload['environment_digest'], payload['build_command_digest'], payload['artifact_id'],
                            payload['artifact_digest'], tuple(payload['evidence_refs']), canonical_digest(payload))
        existing = self._builds.get(row.build_id)
        if existing is not None:
            if existing == row: return existing
            raise ValueError('build id cannot be rebound')
        self._builds[row.build_id] = row; return row

    def get_build(self, build_id):
        try: return self._builds[str(build_id)]
        except KeyError as exc: raise KeyError(f'unknown build: {build_id}') from exc

    def assess_reproducibility(self, original_build_id: str, replay_build_id: str) -> BuildReproductionReceipt:
        a, b = self.get_build(original_build_id), self.get_build(replay_build_id)
        reasons = []
        basis_a = (a.source_digest, a.dependency_lock_digest, a.toolchain_digest, a.environment_digest, a.build_command_digest)
        basis_b = (b.source_digest, b.dependency_lock_digest, b.toolchain_digest, b.environment_digest, b.build_command_digest)
        if basis_a != basis_b: reasons.append('build_basis_mismatch')
        if a.artifact_digest != b.artifact_digest: reasons.append('artifact_digest_mismatch')
        self._repro_counter += 1; rid = f'build-repro-{self._repro_counter:08d}'
        payload = {'receipt_id': rid, 'original_build_id': a.build_id, 'replay_build_id': b.build_id, 'reproducible': not reasons, 'reasons': reasons}
        row = BuildReproductionReceipt(rid, a.build_id, b.build_id, not reasons, tuple(reasons), canonical_digest(payload))
        self._reproductions[row.receipt_id] = row; return row

    def reproduction_receipt(self, receipt_id):
        try: return self._reproductions[str(receipt_id)]
        except KeyError as exc: raise KeyError(f'unknown build reproduction receipt: {receipt_id}') from exc

    def register_observability(self, *, bundle_id: str, producer_agent_id: str, log_schema_digest: str, metric_schema_digest: str,
                               trace_schema_digest: str, slo_refs: tuple[str, ...], evidence_refs: tuple[str, ...]) -> ObservabilityBundle:
        self._require_infra(producer_agent_id)
        if not all(str(x).strip() for x in (bundle_id, log_schema_digest, metric_schema_digest, trace_schema_digest)) or not slo_refs or not evidence_refs:
            raise ValueError('observability bundle requires schemas, SLO refs and evidence')
        payload = {'bundle_id': str(bundle_id), 'producer_agent_id': str(producer_agent_id), 'log_schema_digest': str(log_schema_digest),
                   'metric_schema_digest': str(metric_schema_digest), 'trace_schema_digest': str(trace_schema_digest),
                   'slo_refs': [str(x) for x in slo_refs], 'evidence_refs': [str(x) for x in evidence_refs]}
        row = ObservabilityBundle(payload['bundle_id'], payload['producer_agent_id'], payload['log_schema_digest'], payload['metric_schema_digest'],
                                  payload['trace_schema_digest'], tuple(payload['slo_refs']), tuple(payload['evidence_refs']), canonical_digest(payload))
        existing = self._observability.get(row.bundle_id)
        if existing is not None and existing != row: raise ValueError('observability bundle id cannot be rebound')
        self._observability[row.bundle_id] = row; return row

    def observability_bundle(self, bundle_id):
        try: return self._observability[str(bundle_id)]
        except KeyError as exc: raise KeyError(f'unknown observability bundle: {bundle_id}') from exc

    def register_release(self, *, release_id: str, producer_agent_id: str, build_reproduction_receipt_id: str,
                         package_artifact_id: str, config_digest: str, deployment_topology_digest: str,
                         rollback_artifact_id: str, observability_bundle_id: str, evidence_refs: tuple[str, ...]) -> ReleaseCandidate:
        self._require_infra(producer_agent_id)
        if not all(str(x).strip() for x in (release_id, build_reproduction_receipt_id, package_artifact_id, config_digest, deployment_topology_digest)) or not evidence_refs:
            raise ValueError('release candidate requires id/build/package/config/topology/evidence')
        self.reproduction_receipt(build_reproduction_receipt_id)
        package = self.artifacts.get(package_artifact_id)
        if package.producer_agent_id != str(producer_agent_id): raise ValueError('release package producer mismatch')
        if str(rollback_artifact_id).strip():
            rollback = self.artifacts.get(rollback_artifact_id)
            if rollback.producer_agent_id != str(producer_agent_id): raise ValueError('release rollback producer mismatch')
        if str(observability_bundle_id).strip(): self.observability_bundle(observability_bundle_id)
        payload = {'release_id': str(release_id), 'producer_agent_id': str(producer_agent_id), 'build_reproduction_receipt_id': str(build_reproduction_receipt_id),
                   'package_artifact_id': str(package_artifact_id), 'config_digest': str(config_digest), 'deployment_topology_digest': str(deployment_topology_digest),
                   'rollback_artifact_id': str(rollback_artifact_id), 'observability_bundle_id': str(observability_bundle_id), 'evidence_refs': [str(x) for x in evidence_refs]}
        row = ReleaseCandidate(payload['release_id'], payload['producer_agent_id'], payload['build_reproduction_receipt_id'], payload['package_artifact_id'],
                               payload['config_digest'], payload['deployment_topology_digest'], payload['rollback_artifact_id'], payload['observability_bundle_id'],
                               tuple(payload['evidence_refs']), canonical_digest(payload))
        existing = self._releases.get(row.release_id)
        if existing is not None and existing != row: raise ValueError('release id cannot be rebound')
        self._releases[row.release_id] = row; return row

    def get_release(self, release_id):
        try: return self._releases[str(release_id)]
        except KeyError as exc: raise KeyError(f'unknown release: {release_id}') from exc

    def assess_release(self, release_id: str) -> ReleaseReadinessReceipt:
        release = self.get_release(release_id); reasons = []
        repro = self.reproduction_receipt(release.build_reproduction_receipt_id)
        if not repro.reproducible: reasons.append('build_not_reproducible')
        if not release.rollback_artifact_id.strip(): reasons.append('missing_rollback_artifact')
        if not release.observability_bundle_id.strip(): reasons.append('missing_observability_bundle')
        if not release.evidence_refs: reasons.append('missing_release_evidence')
        self._release_counter += 1; rid = f'release-ready-{self._release_counter:08d}'
        payload = {'receipt_id': rid, 'release_id': release.release_id, 'ready': not reasons, 'reasons': reasons}
        row = ReleaseReadinessReceipt(rid, release.release_id, not reasons, tuple(reasons), canonical_digest(payload))
        self._release_receipts[row.receipt_id] = row; return row

    def release_receipt(self, receipt_id):
        try: return self._release_receipts[str(receipt_id)]
        except KeyError as exc: raise KeyError(f'unknown release readiness receipt: {receipt_id}') from exc

    def to_state(self):
        return {'builds': [self._builds[k].to_state() for k in sorted(self._builds)],
                'reproductions': [self._reproductions[k].to_state() for k in sorted(self._reproductions)],
                'observability': [self._observability[k].to_state() for k in sorted(self._observability)],
                'releases': [self._releases[k].to_state() for k in sorted(self._releases)],
                'release_receipts': [self._release_receipts[k].to_state() for k in sorted(self._release_receipts)],
                'repro_counter': self._repro_counter, 'release_counter': self._release_counter}

    @classmethod
    def from_state(cls, *, registry: AgentRegistry, artifacts: ArtifactStore, state: Mapping[str, Any]):
        result = cls(registry=registry, artifacts=artifacts)
        for v in state.get('builds', ()): row = BuildManifest.from_state(v); result._builds[row.build_id] = row
        for v in state.get('reproductions', ()): row = BuildReproductionReceipt.from_state(v); result._reproductions[row.receipt_id] = row
        for v in state.get('observability', ()): row = ObservabilityBundle.from_state(v); result._observability[row.bundle_id] = row
        for v in state.get('releases', ()): row = ReleaseCandidate.from_state(v); result._releases[row.release_id] = row
        for v in state.get('release_receipts', ()): row = ReleaseReadinessReceipt.from_state(v); result._release_receipts[row.receipt_id] = row
        result._repro_counter = int(state.get('repro_counter', len(result._reproductions)))
        result._release_counter = int(state.get('release_counter', len(result._release_receipts)))
        return result
