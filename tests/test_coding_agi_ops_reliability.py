from cogcoder.organization.blueprint import build_first_generation_blueprint
from cogcoder.organization.registry import AgentRegistry
from cogcoder.organization.reliability_operations import (
    FailureScenarioKind,
    ReliabilityOperationsLedger,
)


def _ledger():
    return ReliabilityOperationsLedger(registry=AgentRegistry(build_first_generation_blueprint()))


def _exercise(ledger, scenario, *, eid, recovered=True, data_loss=0, duplicates=0, workload='workload-1', environment='env-1'):
    return ledger.record_failure_exercise(
        exercise_id=eid, producer_agent_id='reliability.recovery.01', scenario=scenario,
        workload_digest=workload, environment_digest=environment,
        injection_artifact_refs=(f'artifact-{eid}',),
        recovery_strategies=('retry', 'idempotency', 'checkpoint', 'deduplicate'),
        recovered=recovered, data_loss_count=data_loss, duplicate_side_effect_count=duplicates,
        evidence_refs=(f'EV-{eid}',),
    )


def test_reliability_matrix_requires_all_six_mandatory_adverse_scenarios():
    ledger = _ledger()
    mandatory = {
        FailureScenarioKind.DISK_FULL,
        FailureScenarioKind.NETWORK_TIMEOUT,
        FailureScenarioKind.PROCESS_KILL,
        FailureScenarioKind.RESTART,
        FailureScenarioKind.DUPLICATE_EVENT,
        FailureScenarioKind.OUT_OF_ORDER_EVENT,
    }
    assert set(FailureScenarioKind) == mandatory
    rows = [
        _exercise(ledger, scenario, eid=f'EX-{index}')
        for index, scenario in enumerate(sorted(mandatory, key=lambda item: item.value))
    ]
    complete = ledger.assess_matrix(tuple(row.exercise_id for row in rows))
    assert complete.ready is True
    assert complete.reasons == ()

    incomplete = ledger.assess_matrix(tuple(row.exercise_id for row in rows[:-1]))
    assert incomplete.ready is False
    assert any(reason.startswith('missing_scenario_') for reason in incomplete.reasons)


def test_recovered_flag_does_not_hide_data_loss_duplicate_side_effects_or_basis_mismatch():
    ledger = _ledger()
    scenarios = list(FailureScenarioKind)
    rows = []
    for index, scenario in enumerate(scenarios):
        rows.append(_exercise(
            ledger, scenario, eid=f'BAD-{index}',
            data_loss=1 if scenario is FailureScenarioKind.PROCESS_KILL else 0,
            duplicates=1 if scenario is FailureScenarioKind.DUPLICATE_EVENT else 0,
            environment='env-2' if scenario is FailureScenarioKind.RESTART else 'env-1',
        ))
    receipt = ledger.assess_matrix(tuple(row.exercise_id for row in rows))
    assert receipt.ready is False
    assert 'data_loss_detected' in receipt.reasons
    assert 'duplicate_side_effect_detected' in receipt.reasons
    assert 'environment_basis_mismatch' in receipt.reasons


def test_performance_claim_requires_matched_conditions_samples_and_measured_direction():
    ledger = _ledger()
    good = ledger.record_performance_measurement(
        measurement_id='PERF-GOOD', producer_agent_id='reliability.performance.01',
        baseline_workload_digest='w1', candidate_workload_digest='w1',
        baseline_environment_digest='e1', candidate_environment_digest='e1',
        metric_name='p95_latency', unit='ms', baseline_value=120.0, candidate_value=90.0,
        lower_is_better=True, baseline_samples=30, candidate_samples=30,
        evidence_refs=('EV-PERF-GOOD',),
    )
    good_claim = ledger.assess_performance(good.measurement_id)
    assert good_claim.valid is True and good_claim.improved is True

    mismatch = ledger.record_performance_measurement(
        measurement_id='PERF-MISMATCH', producer_agent_id='reliability.performance.01',
        baseline_workload_digest='w1', candidate_workload_digest='w2',
        baseline_environment_digest='e1', candidate_environment_digest='e2',
        metric_name='throughput', unit='rps', baseline_value=100.0, candidate_value=200.0,
        lower_is_better=False, baseline_samples=20, candidate_samples=20,
        evidence_refs=('EV-PERF-MISMATCH',),
    )
    mismatch_claim = ledger.assess_performance(mismatch.measurement_id)
    assert mismatch_claim.valid is False
    assert 'workload_basis_mismatch' in mismatch_claim.reasons
    assert 'environment_basis_mismatch' in mismatch_claim.reasons

    no_samples = ledger.record_performance_measurement(
        measurement_id='PERF-NO-SAMPLES', producer_agent_id='reliability.performance.01',
        baseline_workload_digest='w1', candidate_workload_digest='w1',
        baseline_environment_digest='e1', candidate_environment_digest='e1',
        metric_name='memory', unit='mb', baseline_value=100.0, candidate_value=80.0,
        lower_is_better=True, baseline_samples=0, candidate_samples=10,
        evidence_refs=('EV-PERF-NO-SAMPLES',),
    )
    assert 'missing_samples' in ledger.assess_performance(no_samples.measurement_id).reasons

    worse = ledger.record_performance_measurement(
        measurement_id='PERF-WORSE', producer_agent_id='reliability.performance.01',
        baseline_workload_digest='w1', candidate_workload_digest='w1',
        baseline_environment_digest='e1', candidate_environment_digest='e1',
        metric_name='p95_latency', unit='ms', baseline_value=90.0, candidate_value=120.0,
        lower_is_better=True, baseline_samples=20, candidate_samples=20,
        evidence_refs=('EV-PERF-WORSE',),
    )
    worse_claim = ledger.assess_performance(worse.measurement_id)
    assert worse_claim.valid is False
    assert 'no_measured_improvement' in worse_claim.reasons
