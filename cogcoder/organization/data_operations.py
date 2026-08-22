from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .artifacts import ArtifactStore
from .registry import AgentRegistry
from .types import canonical_digest


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    migration_id: str
    producer_agent_id: str
    from_schema_version: str
    to_schema_version: str
    forward_artifact_id: str
    rollback_artifact_id: str
    compatibility_evidence_refs: tuple[str, ...]
    validation_evidence_refs: tuple[str, ...]
    online: bool
    idempotent: bool
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'migration_id': self.migration_id, 'producer_agent_id': self.producer_agent_id,
            'from_schema_version': self.from_schema_version, 'to_schema_version': self.to_schema_version,
            'forward_artifact_id': self.forward_artifact_id, 'rollback_artifact_id': self.rollback_artifact_id,
            'compatibility_evidence_refs': list(self.compatibility_evidence_refs),
            'validation_evidence_refs': list(self.validation_evidence_refs),
            'online': self.online, 'idempotent': self.idempotent,
        }

    def to_state(self) -> dict[str, Any]: return {**self.payload(), 'digest': self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'MigrationPlan':
        payload = {
            'migration_id': str(state['migration_id']), 'producer_agent_id': str(state['producer_agent_id']),
            'from_schema_version': str(state['from_schema_version']), 'to_schema_version': str(state['to_schema_version']),
            'forward_artifact_id': str(state['forward_artifact_id']), 'rollback_artifact_id': str(state.get('rollback_artifact_id', '')),
            'compatibility_evidence_refs': [str(x) for x in state.get('compatibility_evidence_refs', ())],
            'validation_evidence_refs': [str(x) for x in state.get('validation_evidence_refs', ())],
            'online': bool(state.get('online', False)), 'idempotent': bool(state.get('idempotent', False)),
        }
        row = cls(
            payload['migration_id'], payload['producer_agent_id'], payload['from_schema_version'], payload['to_schema_version'],
            payload['forward_artifact_id'], payload['rollback_artifact_id'], tuple(payload['compatibility_evidence_refs']),
            tuple(payload['validation_evidence_refs']), payload['online'], payload['idempotent'], str(state['digest']),
        )
        if canonical_digest(payload) != row.digest: raise ValueError('migration digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class MigrationReadinessReceipt:
    receipt_id: str
    migration_id: str
    ready: bool
    reasons: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {'receipt_id': self.receipt_id, 'migration_id': self.migration_id, 'ready': self.ready, 'reasons': list(self.reasons)}
    def to_state(self) -> dict[str, Any]: return {**self.payload(), 'digest': self.digest}
    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'MigrationReadinessReceipt':
        row = cls(str(state['receipt_id']), str(state['migration_id']), bool(state['ready']), tuple(str(x) for x in state.get('reasons', ())), str(state['digest']))
        if canonical_digest(row.payload()) != row.digest: raise ValueError('migration readiness digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class PersistenceInvariant:
    invariant_id: str
    producer_agent_id: str
    name: str
    statement: str
    evidence_refs: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {'invariant_id': self.invariant_id, 'producer_agent_id': self.producer_agent_id, 'name': self.name, 'statement': self.statement, 'evidence_refs': list(self.evidence_refs)}
    def to_state(self) -> dict[str, Any]: return {**self.payload(), 'digest': self.digest}
    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'PersistenceInvariant':
        row = cls(str(state['invariant_id']), str(state['producer_agent_id']), str(state['name']), str(state['statement']), tuple(str(x) for x in state.get('evidence_refs', ())), str(state['digest']))
        if canonical_digest(row.payload()) != row.digest: raise ValueError('persistence invariant digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ConsistencyExercise:
    exercise_id: str
    producer_agent_id: str
    source_version: str
    cache_version: str
    operation_sequence: tuple[str, ...]
    observed_result: str
    expected_result: str
    evidence_refs: tuple[str, ...]
    consistent: bool
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            'exercise_id': self.exercise_id, 'producer_agent_id': self.producer_agent_id,
            'source_version': self.source_version, 'cache_version': self.cache_version,
            'operation_sequence': list(self.operation_sequence), 'observed_result': self.observed_result,
            'expected_result': self.expected_result, 'evidence_refs': list(self.evidence_refs), 'consistent': self.consistent,
        }
    def to_state(self) -> dict[str, Any]: return {**self.payload(), 'digest': self.digest}
    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> 'ConsistencyExercise':
        row = cls(
            str(state['exercise_id']), str(state['producer_agent_id']), str(state['source_version']), str(state['cache_version']),
            tuple(str(x) for x in state.get('operation_sequence', ())), str(state['observed_result']), str(state['expected_result']),
            tuple(str(x) for x in state.get('evidence_refs', ())), bool(state['consistent']), str(state['digest']),
        )
        if canonical_digest(row.payload()) != row.digest: raise ValueError('consistency exercise digest mismatch')
        return row


class DataOperationsLedger:
    def __init__(self, *, registry: AgentRegistry, artifacts: ArtifactStore) -> None:
        self.registry = registry
        self.artifacts = artifacts
        self._migrations: dict[str, MigrationPlan] = {}
        self._migration_receipts: dict[str, MigrationReadinessReceipt] = {}
        self._invariants: dict[str, PersistenceInvariant] = {}
        self._consistency: dict[str, ConsistencyExercise] = {}
        self._migration_counter = 0

    @property
    def digest(self) -> str: return canonical_digest(self.to_state())

    def _require_data(self, agent_id: str) -> None:
        identity = self.registry.get(agent_id)
        if identity.region != 'data-storage-migration': raise PermissionError('data operations require Data-region authority')

    def register_migration(self, *, migration_id: str, producer_agent_id: str, from_schema_version: str, to_schema_version: str,
                           forward_artifact_id: str, rollback_artifact_id: str, compatibility_evidence_refs: tuple[str, ...],
                           validation_evidence_refs: tuple[str, ...], online: bool, idempotent: bool) -> MigrationPlan:
        self._require_data(producer_agent_id)
        if not all(str(x).strip() for x in (migration_id, from_schema_version, to_schema_version, forward_artifact_id)):
            raise ValueError('migration identity, schema versions and forward artifact must be explicit')
        forward = self.artifacts.get(forward_artifact_id)
        if forward.producer_agent_id != str(producer_agent_id): raise ValueError('forward migration artifact producer mismatch')
        if str(rollback_artifact_id).strip():
            rollback = self.artifacts.get(rollback_artifact_id)
            if rollback.producer_agent_id != str(producer_agent_id): raise ValueError('rollback migration artifact producer mismatch')
        payload = {
            'migration_id': str(migration_id), 'producer_agent_id': str(producer_agent_id),
            'from_schema_version': str(from_schema_version), 'to_schema_version': str(to_schema_version),
            'forward_artifact_id': str(forward_artifact_id), 'rollback_artifact_id': str(rollback_artifact_id),
            'compatibility_evidence_refs': [str(x) for x in compatibility_evidence_refs],
            'validation_evidence_refs': [str(x) for x in validation_evidence_refs],
            'online': bool(online), 'idempotent': bool(idempotent),
        }
        row = MigrationPlan(
            payload['migration_id'], payload['producer_agent_id'], payload['from_schema_version'], payload['to_schema_version'],
            payload['forward_artifact_id'], payload['rollback_artifact_id'], tuple(payload['compatibility_evidence_refs']),
            tuple(payload['validation_evidence_refs']), payload['online'], payload['idempotent'], canonical_digest(payload),
        )
        existing = self._migrations.get(row.migration_id)
        if existing is not None:
            if existing == row: return existing
            raise ValueError('migration id cannot be rebound')
        self._migrations[row.migration_id] = row
        return row

    def get_migration(self, migration_id: str) -> MigrationPlan:
        try: return self._migrations[str(migration_id)]
        except KeyError as exc: raise KeyError(f'unknown migration: {migration_id}') from exc

    def assess_migration(self, migration_id: str) -> MigrationReadinessReceipt:
        plan = self.get_migration(migration_id)
        reasons: list[str] = []
        if not plan.rollback_artifact_id.strip(): reasons.append('missing_rollback_artifact')
        elif plan.rollback_artifact_id == plan.forward_artifact_id: reasons.append('rollback_matches_forward')
        if not plan.compatibility_evidence_refs: reasons.append('missing_compatibility_evidence')
        if not plan.validation_evidence_refs: reasons.append('missing_validation_evidence')
        self._migration_counter += 1
        receipt_id = f'migration-ready-{self._migration_counter:08d}'
        payload = {'receipt_id': receipt_id, 'migration_id': plan.migration_id, 'ready': not reasons, 'reasons': reasons}
        row = MigrationReadinessReceipt(receipt_id, plan.migration_id, not reasons, tuple(reasons), canonical_digest(payload))
        self._migration_receipts[row.receipt_id] = row
        return row

    def migration_receipt(self, receipt_id: str) -> MigrationReadinessReceipt:
        try: return self._migration_receipts[str(receipt_id)]
        except KeyError as exc: raise KeyError(f'unknown migration readiness receipt: {receipt_id}') from exc

    def record_persistence_invariant(self, *, invariant_id: str, producer_agent_id: str, name: str, statement: str,
                                     evidence_refs: tuple[str, ...]) -> PersistenceInvariant:
        self._require_data(producer_agent_id)
        if not all(str(x).strip() for x in (invariant_id, name, statement)) or not evidence_refs:
            raise ValueError('persistence invariant requires identity/name/statement/evidence')
        payload = {'invariant_id': str(invariant_id), 'producer_agent_id': str(producer_agent_id), 'name': str(name), 'statement': str(statement), 'evidence_refs': [str(x) for x in evidence_refs]}
        row = PersistenceInvariant(payload['invariant_id'], payload['producer_agent_id'], payload['name'], payload['statement'], tuple(payload['evidence_refs']), canonical_digest(payload))
        existing = self._invariants.get(row.invariant_id)
        if existing is not None and existing != row: raise ValueError('persistence invariant id cannot be rebound')
        self._invariants[row.invariant_id] = row
        return row

    def record_consistency_exercise(self, *, exercise_id: str, producer_agent_id: str, source_version: str, cache_version: str,
                                    operation_sequence: tuple[str, ...], observed_result: str, expected_result: str,
                                    evidence_refs: tuple[str, ...]) -> ConsistencyExercise:
        self._require_data(producer_agent_id)
        if not all(str(x).strip() for x in (exercise_id, source_version, cache_version)) or not operation_sequence or not evidence_refs:
            raise ValueError('consistency exercise requires identity/versions/operations/evidence')
        payload = {
            'exercise_id': str(exercise_id), 'producer_agent_id': str(producer_agent_id), 'source_version': str(source_version),
            'cache_version': str(cache_version), 'operation_sequence': [str(x) for x in operation_sequence],
            'observed_result': str(observed_result), 'expected_result': str(expected_result),
            'evidence_refs': [str(x) for x in evidence_refs], 'consistent': str(observed_result) == str(expected_result),
        }
        row = ConsistencyExercise(
            payload['exercise_id'], payload['producer_agent_id'], payload['source_version'], payload['cache_version'],
            tuple(payload['operation_sequence']), payload['observed_result'], payload['expected_result'], tuple(payload['evidence_refs']),
            payload['consistent'], canonical_digest(payload),
        )
        existing = self._consistency.get(row.exercise_id)
        if existing is not None and existing != row: raise ValueError('consistency exercise id cannot be rebound')
        self._consistency[row.exercise_id] = row
        return row

    def to_state(self) -> dict[str, Any]:
        return {
            'migrations': [self._migrations[k].to_state() for k in sorted(self._migrations)],
            'migration_receipts': [self._migration_receipts[k].to_state() for k in sorted(self._migration_receipts)],
            'invariants': [self._invariants[k].to_state() for k in sorted(self._invariants)],
            'consistency': [self._consistency[k].to_state() for k in sorted(self._consistency)],
            'migration_counter': self._migration_counter,
        }

    @classmethod
    def from_state(cls, *, registry: AgentRegistry, artifacts: ArtifactStore, state: Mapping[str, Any]) -> 'DataOperationsLedger':
        result = cls(registry=registry, artifacts=artifacts)
        for value in state.get('migrations', ()):
            row = MigrationPlan.from_state(value); result._migrations[row.migration_id] = row
        for value in state.get('migration_receipts', ()):
            row = MigrationReadinessReceipt.from_state(value); result._migration_receipts[row.receipt_id] = row
        for value in state.get('invariants', ()):
            row = PersistenceInvariant.from_state(value); result._invariants[row.invariant_id] = row
        for value in state.get('consistency', ()):
            row = ConsistencyExercise.from_state(value); result._consistency[row.exercise_id] = row
        result._migration_counter = int(state.get('migration_counter', len(result._migration_receipts)))
        return result
