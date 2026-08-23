import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord
from cogcoder.organization.evaluation_stress import LongHorizonStressLedger, StressScenarioKind


REQUIRED = (
    StressScenarioKind.SLEEP_WAKE_CONTINUITY,
    StressScenarioKind.PLAN_DRIFT,
    StressScenarioKind.MEMORY_CONTAMINATION,
    StressScenarioKind.STALE_LEASE,
    StressScenarioKind.CONFLICT_BACKPRESSURE,
    StressScenarioKind.EPHEMERAL_RETIREMENT,
)


def _ledger():
    runtime = OrganizationRuntime.first_generation()
    return LongHorizonStressLedger(registry=runtime.registry)


def _record(ledger, scenario, *, oid=None, contamination=0, stale=0, false_accepts=0, regressions=0, recovered=True):
    oid = oid or f'stress-{scenario.value}'
    return ledger.record_stress(
        observation_id=oid,
        scenario=scenario,
        regime_digest='long-horizon-regime-1',
        initial_state_digest='state-before',
        final_state_digest='state-after',
        checkpoint_anchor='checkpoint-10',
        event_anchor='event-1000',
        plan_revision_before='plan-r1',
        plan_revision_after='plan-r2',
        contamination_count=contamination,
        stale_context_count=stale,
        false_accepts=false_accepts,
        regressions=regressions,
        recovered=recovered,
        elapsed_logical_epochs=5000,
        evidence=EvidenceRecord(f'ev-{oid}', 'verification.chief', True),
    )


def test_complete_long_horizon_suite_requires_all_six_required_scenarios():
    ledger = _ledger()
    rows = [_record(ledger, scenario) for scenario in REQUIRED]
    assessment = ledger.assess_suite(tuple(row.observation_id for row in rows))
    assert assessment.passed
    assert set(assessment.covered_scenarios) == set(REQUIRED)


def test_missing_one_required_scenario_blocks_reliability():
    ledger = _ledger()
    rows = [_record(ledger, scenario) for scenario in REQUIRED[:-1]]
    assessment = ledger.assess_suite(tuple(row.observation_id for row in rows))
    assert not assessment.passed
    assert StressScenarioKind.EPHEMERAL_RETIREMENT in assessment.missing_scenarios


@pytest.mark.parametrize('kwargs, reason', [
    ({'contamination': 1}, 'memory_contamination_detected'),
    ({'stale': 1}, 'stale_context_detected'),
    ({'false_accepts': 1}, 'false_accept_detected'),
    ({'regressions': 1}, 'regression_detected'),
    ({'recovered': False}, 'recovery_failed'),
])
def test_dirty_long_horizon_observation_blocks_suite(kwargs, reason):
    ledger = _ledger()
    rows = []
    for scenario in REQUIRED:
        rows.append(_record(ledger, scenario, **(kwargs if scenario is StressScenarioKind.MEMORY_CONTAMINATION else {})))
    assessment = ledger.assess_suite(tuple(row.observation_id for row in rows))
    assert not assessment.passed
    assert reason in assessment.reasons


def test_stress_evidence_must_be_clean_and_external_to_subject_agent():
    runtime = OrganizationRuntime.first_generation()
    ledger = LongHorizonStressLedger(registry=runtime.registry)
    with pytest.raises(PermissionError):
        ledger.record_stress(
            observation_id='self-stress', scenario=StressScenarioKind.SLEEP_WAKE_CONTINUITY,
            regime_digest='r', initial_state_digest='a', final_state_digest='b',
            checkpoint_anchor='c', event_anchor='e', plan_revision_before='p1', plan_revision_after='p1',
            contamination_count=0, stale_context_count=0, false_accepts=0, regressions=0,
            recovered=True, elapsed_logical_epochs=100,
            evidence=EvidenceRecord('self-ev', 'coding.backend.01', False, false_accepts=0, regressions=0),
            subject_agent_id='coding.backend.01',
        )
