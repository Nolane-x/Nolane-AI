import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.reliability_operations import (
    FailureExercise,
    PerformanceClaimReceipt,
    PerformanceMeasurement,
    ReliabilityMatrixReceipt,
)


def _failure_exercise_state() -> dict[str, object]:
    payload = {
        "exercise_id": "EX-R233",
        "producer_agent_id": "reliability.recovery.01",
        "scenario": "restart",
        "workload_digest": "workload-r233",
        "environment_digest": "environment-r233",
        "injection_artifact_refs": ["artifact-r233"],
        "recovery_strategies": ["checkpoint"],
        "recovered": True,
        "data_loss_count": 0,
        "duplicate_side_effect_count": 0,
        "evidence_refs": ["EV-R233"],
    }
    return {**payload, "digest": canonical_digest(payload)}


def _reliability_matrix_state() -> dict[str, object]:
    payload = {
        "receipt_id": "reliability-matrix-r233",
        "exercise_ids": ["EX-R233"],
        "ready": True,
        "reasons": [],
    }
    return {**payload, "digest": canonical_digest(payload)}


def _performance_measurement_state() -> dict[str, object]:
    payload = {
        "measurement_id": "PERF-R233",
        "producer_agent_id": "reliability.performance.01",
        "baseline_workload_digest": "workload-r233",
        "candidate_workload_digest": "workload-r233",
        "baseline_environment_digest": "environment-r233",
        "candidate_environment_digest": "environment-r233",
        "metric_name": "p95_latency",
        "unit": "ms",
        "baseline_value": 120.0,
        "candidate_value": 90.0,
        "lower_is_better": True,
        "baseline_samples": 30,
        "candidate_samples": 30,
        "evidence_refs": ["EV-PERF-R233"],
    }
    return {**payload, "digest": canonical_digest(payload)}


def _performance_claim_state() -> dict[str, object]:
    payload = {
        "receipt_id": "performance-claim-r233",
        "measurement_id": "PERF-R233",
        "valid": True,
        "improved": True,
        "reasons": [],
    }
    return {**payload, "digest": canonical_digest(payload)}


@pytest.mark.parametrize(
    ("receipt_type", "field", "state_factory"),
    (
        (FailureExercise, "recovered", _failure_exercise_state),
        (ReliabilityMatrixReceipt, "ready", _reliability_matrix_state),
        (PerformanceMeasurement, "lower_is_better", _performance_measurement_state),
        (PerformanceClaimReceipt, "valid", _performance_claim_state),
        (PerformanceClaimReceipt, "improved", _performance_claim_state),
    ),
)
def test_reliability_state_restore_rejects_non_exact_boolean_alias(
    receipt_type: type,
    field: str,
    state_factory,
) -> None:
    state = state_factory()
    state[field] = "false"

    with pytest.raises(ValueError, match=field):
        receipt_type.from_state(state)
