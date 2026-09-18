from __future__ import annotations

from copy import deepcopy

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord
from nolane.evaluation.stress import (
    LongHorizonStressLedger,
    LongHorizonStressObservation,
    StressScenarioKind,
    StressSuiteAssessment,
)


def _ledger() -> LongHorizonStressLedger:
    runtime = OrganizationRuntime.first_generation()
    return LongHorizonStressLedger(registry=runtime.registry)


def _record(
    ledger: LongHorizonStressLedger,
    scenario: StressScenarioKind,
    *,
    recovered: object = True,
    observation_id: str | None = None,
):
    oid = observation_id or f"r244-{scenario.value}"
    return ledger.record_stress(
        observation_id=oid,
        scenario=scenario,
        regime_digest="r244-regime",
        initial_state_digest="r244-state-before",
        final_state_digest="r244-state-after",
        checkpoint_anchor="r244-checkpoint",
        event_anchor="r244-event",
        plan_revision_before="r244-plan-before",
        plan_revision_after="r244-plan-after",
        contamination_count=0,
        stale_context_count=0,
        false_accepts=0,
        regressions=0,
        recovered=recovered,
        elapsed_logical_epochs=5000,
        evidence=EvidenceRecord(f"r244-evidence-{oid}", "verification.chief", True),
    )


def _clean_suite(ledger: LongHorizonStressLedger):
    rows = [
        _record(ledger, scenario, observation_id=f"r244-suite-{index}")
        for index, scenario in enumerate(LongHorizonStressLedger.REQUIRED_SCENARIOS, start=1)
    ]
    return ledger.assess_suite(tuple(row.observation_id for row in rows))


@pytest.mark.parametrize("alias", ["false", "true", 0, 1])
def test_record_stress_rejects_non_boolean_recovered_aliases(alias: object) -> None:
    ledger = _ledger()

    with pytest.raises(ValueError, match="recovered.*exact bool"):
        _record(ledger, StressScenarioKind.SLEEP_WAKE_CONTINUITY, recovered=alias)


@pytest.mark.parametrize("alias", ["false", "true", 0, 1])
def test_long_horizon_observation_constructor_rejects_non_boolean_recovered(alias: object) -> None:
    ledger = _ledger()
    canonical = _record(ledger, StressScenarioKind.SLEEP_WAKE_CONTINUITY)

    with pytest.raises(ValueError, match="recovered.*exact bool"):
        LongHorizonStressObservation(
            observation_id=canonical.observation_id,
            scenario=canonical.scenario,
            regime_digest=canonical.regime_digest,
            initial_state_digest=canonical.initial_state_digest,
            final_state_digest=canonical.final_state_digest,
            checkpoint_anchor=canonical.checkpoint_anchor,
            event_anchor=canonical.event_anchor,
            plan_revision_before=canonical.plan_revision_before,
            plan_revision_after=canonical.plan_revision_after,
            contamination_count=canonical.contamination_count,
            stale_context_count=canonical.stale_context_count,
            false_accepts=canonical.false_accepts,
            regressions=canonical.regressions,
            recovered=alias,
            elapsed_logical_epochs=canonical.elapsed_logical_epochs,
            evidence=canonical.evidence,
            subject_agent_id=canonical.subject_agent_id,
            digest=canonical.digest,
        )


def test_long_horizon_observation_restore_rejects_truthy_false_alias() -> None:
    ledger = _ledger()
    canonical = _record(ledger, StressScenarioKind.SLEEP_WAKE_CONTINUITY)
    state = canonical.to_state()
    state["recovered"] = "false"

    with pytest.raises(ValueError, match="recovered.*exact bool"):
        LongHorizonStressObservation.from_state(state)


def test_stress_ledger_restore_rejects_persisted_recovered_alias() -> None:
    ledger = _ledger()
    _record(ledger, StressScenarioKind.SLEEP_WAKE_CONTINUITY)
    state = ledger.to_state()
    state["observations"][0]["recovered"] = "false"

    with pytest.raises(ValueError, match="recovered.*exact bool"):
        LongHorizonStressLedger.from_state(registry=ledger.registry, state=state)


@pytest.mark.parametrize("alias", ["false", "true", 0, 1])
def test_stress_assessment_constructor_rejects_non_boolean_passed(alias: object) -> None:
    ledger = _ledger()
    canonical = _clean_suite(ledger)

    with pytest.raises(ValueError, match="passed.*exact bool"):
        StressSuiteAssessment(
            assessment_id=canonical.assessment_id,
            observation_ids=canonical.observation_ids,
            covered_scenarios=canonical.covered_scenarios,
            missing_scenarios=canonical.missing_scenarios,
            passed=alias,
            reasons=canonical.reasons,
            digest=canonical.digest,
        )


def test_stress_assessment_restore_rejects_truthy_false_alias() -> None:
    ledger = _ledger()
    canonical = _clean_suite(ledger)
    state = canonical.to_state()
    state["passed"] = "false"

    with pytest.raises(ValueError, match="passed.*exact bool"):
        StressSuiteAssessment.from_state(state)


def test_stress_ledger_restore_rejects_persisted_passed_alias() -> None:
    ledger = _ledger()
    _clean_suite(ledger)
    state = ledger.to_state()
    state["assessments"][0]["passed"] = "false"

    with pytest.raises(ValueError, match="passed.*exact bool"):
        LongHorizonStressLedger.from_state(registry=ledger.registry, state=state)


def test_runtime_restore_rejects_persisted_stress_boolean_aliases() -> None:
    runtime = OrganizationRuntime.first_generation()
    ledger = runtime.evaluation_scaling.stress
    _clean_suite(ledger)
    state = deepcopy(runtime.to_state())
    state["evaluation_scaling"]["stress"]["observations"][0]["recovered"] = "false"
    state["evaluation_scaling"]["stress"]["assessments"][0]["passed"] = "false"

    with pytest.raises(ValueError, match="recovered.*exact bool|passed.*exact bool"):
        OrganizationRuntime.from_state(state)
