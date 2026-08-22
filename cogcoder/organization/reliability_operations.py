from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .registry import AgentRegistry
from .types import canonical_digest


class FailureScenarioKind(str, Enum):
    DISK_FULL = 'disk_full'
    NETWORK_TIMEOUT = 'network_timeout'
    PROCESS_KILL = 'process_kill'
    RESTART = 'restart'
    DUPLICATE_EVENT = 'duplicate_event'
    OUT_OF_ORDER_EVENT = 'out_of_order_event'


@dataclass(frozen=True, slots=True)
class FailureExercise:
    exercise_id: str
    producer_agent_id: str
    scenario: FailureScenarioKind
    workload_digest: str
    environment_digest: str
    injection_artifact_refs: tuple[str, ...]
    recovery_strategies: tuple[str, ...]
    recovered: bool
    data_loss_count: int
    duplicate_side_effect_count: int
    evidence_refs: tuple[str, ...]
    digest: str
    def payload(self):
        return {'exercise_id': self.exercise_id, 'producer_agent_id': self.producer_agent_id, 'scenario': self.scenario.value,
                'workload_digest': self.workload_digest, 'environment_digest': self.environment_digest,
                'injection_artifact_refs': list(self.injection_artifact_refs), 'recovery_strategies': list(self.recovery_strategies),
                'recovered': self.recovered, 'data_loss_count': self.data_loss_count,
                'duplicate_side_effect_count': self.duplicate_side_effect_count, 'evidence_refs': list(self.evidence_refs)}
    def to_state(self): return {**self.payload(), 'digest': self.digest}
    @classmethod
    def from_state(cls, state):
        row = cls(str(state['exercise_id']), str(state['producer_agent_id']), FailureScenarioKind(str(state['scenario'])),
                  str(state['workload_digest']), str(state['environment_digest']), tuple(str(x) for x in state.get('injection_artifact_refs', ())),
                  tuple(str(x) for x in state.get('recovery_strategies', ())), bool(state['recovered']), int(state.get('data_loss_count', 0)),
                  int(state.get('duplicate_side_effect_count', 0)), tuple(str(x) for x in state.get('evidence_refs', ())), str(state['digest']))
        if canonical_digest(row.payload()) != row.digest: raise ValueError('failure exercise digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class ReliabilityMatrixReceipt:
    receipt_id: str
    exercise_ids: tuple[str, ...]
    ready: bool
    reasons: tuple[str, ...]
    digest: str
    def payload(self): return {'receipt_id': self.receipt_id, 'exercise_ids': list(self.exercise_ids), 'ready': self.ready, 'reasons': list(self.reasons)}
    def to_state(self): return {**self.payload(), 'digest': self.digest}
    @classmethod
    def from_state(cls, state):
        row = cls(str(state['receipt_id']), tuple(str(x) for x in state.get('exercise_ids', ())), bool(state['ready']), tuple(str(x) for x in state.get('reasons', ())), str(state['digest']))
        if canonical_digest(row.payload()) != row.digest: raise ValueError('reliability matrix digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class PerformanceMeasurement:
    measurement_id: str
    producer_agent_id: str
    baseline_workload_digest: str
    candidate_workload_digest: str
    baseline_environment_digest: str
    candidate_environment_digest: str
    metric_name: str
    unit: str
    baseline_value: float
    candidate_value: float
    lower_is_better: bool
    baseline_samples: int
    candidate_samples: int
    evidence_refs: tuple[str, ...]
    digest: str
    def payload(self):
        return {'measurement_id': self.measurement_id, 'producer_agent_id': self.producer_agent_id,
                'baseline_workload_digest': self.baseline_workload_digest, 'candidate_workload_digest': self.candidate_workload_digest,
                'baseline_environment_digest': self.baseline_environment_digest, 'candidate_environment_digest': self.candidate_environment_digest,
                'metric_name': self.metric_name, 'unit': self.unit, 'baseline_value': self.baseline_value,
                'candidate_value': self.candidate_value, 'lower_is_better': self.lower_is_better,
                'baseline_samples': self.baseline_samples, 'candidate_samples': self.candidate_samples, 'evidence_refs': list(self.evidence_refs)}
    def to_state(self): return {**self.payload(), 'digest': self.digest}
    @classmethod
    def from_state(cls, state):
        row = cls(str(state['measurement_id']), str(state['producer_agent_id']), str(state['baseline_workload_digest']),
                  str(state['candidate_workload_digest']), str(state['baseline_environment_digest']), str(state['candidate_environment_digest']),
                  str(state['metric_name']), str(state['unit']), float(state['baseline_value']), float(state['candidate_value']),
                  bool(state['lower_is_better']), int(state['baseline_samples']), int(state['candidate_samples']),
                  tuple(str(x) for x in state.get('evidence_refs', ())), str(state['digest']))
        if canonical_digest(row.payload()) != row.digest: raise ValueError('performance measurement digest mismatch')
        return row


@dataclass(frozen=True, slots=True)
class PerformanceClaimReceipt:
    receipt_id: str
    measurement_id: str
    valid: bool
    improved: bool
    reasons: tuple[str, ...]
    digest: str
    def payload(self): return {'receipt_id': self.receipt_id, 'measurement_id': self.measurement_id, 'valid': self.valid, 'improved': self.improved, 'reasons': list(self.reasons)}
    def to_state(self): return {**self.payload(), 'digest': self.digest}
    @classmethod
    def from_state(cls, state):
        row = cls(str(state['receipt_id']), str(state['measurement_id']), bool(state['valid']), bool(state['improved']), tuple(str(x) for x in state.get('reasons', ())), str(state['digest']))
        if canonical_digest(row.payload()) != row.digest: raise ValueError('performance claim digest mismatch')
        return row


class ReliabilityOperationsLedger:
    def __init__(self, *, registry: AgentRegistry) -> None:
        self.registry = registry
        self._exercises: dict[str, FailureExercise] = {}
        self._matrices: dict[str, ReliabilityMatrixReceipt] = {}
        self._measurements: dict[str, PerformanceMeasurement] = {}
        self._claims: dict[str, PerformanceClaimReceipt] = {}
        self._matrix_counter = 0; self._claim_counter = 0

    @property
    def digest(self): return canonical_digest(self.to_state())
    def _require_reliability(self, agent_id):
        if self.registry.get(agent_id).region != 'performance-reliability': raise PermissionError('reliability operations require Reliability-region authority')

    def record_failure_exercise(self, *, exercise_id: str, producer_agent_id: str, scenario: FailureScenarioKind,
                                workload_digest: str, environment_digest: str, injection_artifact_refs: tuple[str, ...],
                                recovery_strategies: tuple[str, ...], recovered: bool, data_loss_count: int,
                                duplicate_side_effect_count: int, evidence_refs: tuple[str, ...]) -> FailureExercise:
        self._require_reliability(producer_agent_id); scenario = FailureScenarioKind(scenario)
        if not all(str(x).strip() for x in (exercise_id, workload_digest, environment_digest)) or not injection_artifact_refs or not recovery_strategies or not evidence_refs:
            raise ValueError('failure exercise requires identity/basis/injection/recovery/evidence')
        if int(data_loss_count) < 0 or int(duplicate_side_effect_count) < 0: raise ValueError('failure counters must be non-negative')
        payload = {'exercise_id': str(exercise_id), 'producer_agent_id': str(producer_agent_id), 'scenario': scenario.value,
                   'workload_digest': str(workload_digest), 'environment_digest': str(environment_digest),
                   'injection_artifact_refs': [str(x) for x in injection_artifact_refs], 'recovery_strategies': [str(x) for x in recovery_strategies],
                   'recovered': bool(recovered), 'data_loss_count': int(data_loss_count), 'duplicate_side_effect_count': int(duplicate_side_effect_count),
                   'evidence_refs': [str(x) for x in evidence_refs]}
        row = FailureExercise(payload['exercise_id'], payload['producer_agent_id'], scenario, payload['workload_digest'], payload['environment_digest'],
                              tuple(payload['injection_artifact_refs']), tuple(payload['recovery_strategies']), payload['recovered'], payload['data_loss_count'],
                              payload['duplicate_side_effect_count'], tuple(payload['evidence_refs']), canonical_digest(payload))
        existing = self._exercises.get(row.exercise_id)
        if existing is not None:
            if existing == row: return existing
            raise ValueError('failure exercise id cannot be rebound')
        self._exercises[row.exercise_id] = row; return row

    def get_exercise(self, exercise_id):
        try: return self._exercises[str(exercise_id)]
        except KeyError as exc: raise KeyError(f'unknown failure exercise: {exercise_id}') from exc

    def assess_matrix(self, exercise_ids: tuple[str, ...]) -> ReliabilityMatrixReceipt:
        rows = tuple(self.get_exercise(x) for x in exercise_ids)
        reasons: list[str] = []
        present = {row.scenario for row in rows}
        for scenario in FailureScenarioKind:
            if scenario not in present: reasons.append(f'missing_scenario_{scenario.value}')
        if rows:
            if len({row.workload_digest for row in rows}) != 1: reasons.append('workload_basis_mismatch')
            if len({row.environment_digest for row in rows}) != 1: reasons.append('environment_basis_mismatch')
        if any(not row.recovered for row in rows): reasons.append('recovery_failed')
        if any(row.data_loss_count for row in rows): reasons.append('data_loss_detected')
        if any(row.duplicate_side_effect_count for row in rows): reasons.append('duplicate_side_effect_detected')
        self._matrix_counter += 1; rid = f'reliability-matrix-{self._matrix_counter:08d}'
        payload = {'receipt_id': rid, 'exercise_ids': [row.exercise_id for row in rows], 'ready': not reasons, 'reasons': reasons}
        receipt = ReliabilityMatrixReceipt(rid, tuple(row.exercise_id for row in rows), not reasons, tuple(reasons), canonical_digest(payload))
        self._matrices[receipt.receipt_id] = receipt; return receipt

    def matrix_receipt(self, receipt_id):
        try: return self._matrices[str(receipt_id)]
        except KeyError as exc: raise KeyError(f'unknown reliability matrix receipt: {receipt_id}') from exc

    def record_performance_measurement(self, *, measurement_id: str, producer_agent_id: str,
                                       baseline_workload_digest: str, candidate_workload_digest: str,
                                       baseline_environment_digest: str, candidate_environment_digest: str,
                                       metric_name: str, unit: str, baseline_value: float, candidate_value: float,
                                       lower_is_better: bool, baseline_samples: int, candidate_samples: int,
                                       evidence_refs: tuple[str, ...]) -> PerformanceMeasurement:
        self._require_reliability(producer_agent_id)
        if not all(str(x).strip() for x in (measurement_id, baseline_workload_digest, candidate_workload_digest, baseline_environment_digest, candidate_environment_digest, metric_name, unit)) or not evidence_refs:
            raise ValueError('performance measurement requires identity/basis/metric/evidence')
        if int(baseline_samples) < 0 or int(candidate_samples) < 0: raise ValueError('sample counts must be non-negative')
        payload = {'measurement_id': str(measurement_id), 'producer_agent_id': str(producer_agent_id),
                   'baseline_workload_digest': str(baseline_workload_digest), 'candidate_workload_digest': str(candidate_workload_digest),
                   'baseline_environment_digest': str(baseline_environment_digest), 'candidate_environment_digest': str(candidate_environment_digest),
                   'metric_name': str(metric_name), 'unit': str(unit), 'baseline_value': float(baseline_value), 'candidate_value': float(candidate_value),
                   'lower_is_better': bool(lower_is_better), 'baseline_samples': int(baseline_samples), 'candidate_samples': int(candidate_samples),
                   'evidence_refs': [str(x) for x in evidence_refs]}
        row = PerformanceMeasurement(payload['measurement_id'], payload['producer_agent_id'], payload['baseline_workload_digest'], payload['candidate_workload_digest'],
                                     payload['baseline_environment_digest'], payload['candidate_environment_digest'], payload['metric_name'], payload['unit'],
                                     payload['baseline_value'], payload['candidate_value'], payload['lower_is_better'], payload['baseline_samples'], payload['candidate_samples'],
                                     tuple(payload['evidence_refs']), canonical_digest(payload))
        existing = self._measurements.get(row.measurement_id)
        if existing is not None:
            if existing == row: return existing
            raise ValueError('performance measurement id cannot be rebound')
        self._measurements[row.measurement_id] = row; return row

    def get_measurement(self, measurement_id):
        try: return self._measurements[str(measurement_id)]
        except KeyError as exc: raise KeyError(f'unknown performance measurement: {measurement_id}') from exc

    def assess_performance(self, measurement_id: str) -> PerformanceClaimReceipt:
        row = self.get_measurement(measurement_id); reasons: list[str] = []
        if row.baseline_samples <= 0 or row.candidate_samples <= 0: reasons.append('missing_samples')
        if row.baseline_workload_digest != row.candidate_workload_digest: reasons.append('workload_basis_mismatch')
        if row.baseline_environment_digest != row.candidate_environment_digest: reasons.append('environment_basis_mismatch')
        improved = row.candidate_value < row.baseline_value if row.lower_is_better else row.candidate_value > row.baseline_value
        if not improved: reasons.append('no_measured_improvement')
        self._claim_counter += 1; rid = f'performance-claim-{self._claim_counter:08d}'
        payload = {'receipt_id': rid, 'measurement_id': row.measurement_id, 'valid': not reasons, 'improved': improved, 'reasons': reasons}
        receipt = PerformanceClaimReceipt(rid, row.measurement_id, not reasons, improved, tuple(reasons), canonical_digest(payload))
        self._claims[receipt.receipt_id] = receipt; return receipt

    def performance_claim(self, receipt_id):
        try: return self._claims[str(receipt_id)]
        except KeyError as exc: raise KeyError(f'unknown performance claim receipt: {receipt_id}') from exc

    def to_state(self):
        return {'exercises': [self._exercises[k].to_state() for k in sorted(self._exercises)],
                'matrices': [self._matrices[k].to_state() for k in sorted(self._matrices)],
                'measurements': [self._measurements[k].to_state() for k in sorted(self._measurements)],
                'claims': [self._claims[k].to_state() for k in sorted(self._claims)],
                'matrix_counter': self._matrix_counter, 'claim_counter': self._claim_counter}

    @classmethod
    def from_state(cls, *, registry: AgentRegistry, state: Mapping[str, Any]):
        result = cls(registry=registry)
        for v in state.get('exercises', ()): row = FailureExercise.from_state(v); result._exercises[row.exercise_id] = row
        for v in state.get('matrices', ()): row = ReliabilityMatrixReceipt.from_state(v); result._matrices[row.receipt_id] = row
        for v in state.get('measurements', ()): row = PerformanceMeasurement.from_state(v); result._measurements[row.measurement_id] = row
        for v in state.get('claims', ()): row = PerformanceClaimReceipt.from_state(v); result._claims[row.receipt_id] = row
        result._matrix_counter = int(state.get('matrix_counter', len(result._matrices)))
        result._claim_counter = int(state.get('claim_counter', len(result._claims)))
        return result
