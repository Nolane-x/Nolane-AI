from __future__ import annotations

from dataclasses import replace

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EvidenceRecord
from nolane.evaluation.stress import (
    LongHorizonStressLedger,
    LongHorizonStressObservation,
    StressScenarioKind,
)


_INTEGER_FIELDS = (
    "contamination_count",
    "stale_context_count",
    "false_accepts",
    "regressions",
    "elapsed_logical_epochs",
)

_INTEGER_ALIASES = (True, 1.0, "1")


def _ledger() -> LongHorizonStressLedger:
    runtime = OrganizationRuntime.first_generation()
    return LongHorizonStressLedger(registry=runtime.registry)


def _kwargs(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "observation_id": "r258-stress-observation",
        "scenario": StressScenarioKind.SLEEP_WAKE_CONTINUITY,
        "regime_digest": "r258-regime",
        "initial_state_digest": "r258-state-before",
        "final_state_digest": "r258-state-after",
        "checkpoint_anchor": "r258-checkpoint",
        "event_anchor": "r258-event",
        "plan_revision_before": "r258-plan-before",
        "plan_revision_after": "r258-plan-after",
        "contamination_count": 1,
        "stale_context_count": 1,
        "false_accepts": 1,
        "regressions": 1,
        "recovered": True,
        "elapsed_logical_epochs": 1,
        "evidence": EvidenceRecord(
            "r258-clean-evidence",
            "verification.chief",
            True,
            false_accepts=0,
            regressions=0,
        ),
    }
    values.update(overrides)
    return values


def _canonical_observation() -> LongHorizonStressObservation:
    ledger = _ledger()
    return ledger.record_stress(**_kwargs())


@pytest.mark.parametrize("field", _INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _INTEGER_ALIASES)
def test_stress_observation_constructor_rejects_non_exact_integer_authority(
    field: str,
    alias: object,
) -> None:
    canonical = _canonical_observation()
    mutated = replace(canonical, **{field: alias})

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        LongHorizonStressObservation(
            observation_id=mutated.observation_id,
            scenario=mutated.scenario,
            regime_digest=mutated.regime_digest,
            initial_state_digest=mutated.initial_state_digest,
            final_state_digest=mutated.final_state_digest,
            checkpoint_anchor=mutated.checkpoint_anchor,
            event_anchor=mutated.event_anchor,
            plan_revision_before=mutated.plan_revision_before,
            plan_revision_after=mutated.plan_revision_after,
            contamination_count=mutated.contamination_count,
            stale_context_count=mutated.stale_context_count,
            false_accepts=mutated.false_accepts,
            regressions=mutated.regressions,
            recovered=mutated.recovered,
            elapsed_logical_epochs=mutated.elapsed_logical_epochs,
            evidence=mutated.evidence,
            subject_agent_id=mutated.subject_agent_id,
            digest=mutated.digest,
        )


@pytest.mark.parametrize("field", _INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _INTEGER_ALIASES)
def test_stress_observation_restore_rejects_digest_preserving_integer_alias(
    field: str,
    alias: object,
) -> None:
    canonical = _canonical_observation()
    state = canonical.to_state()
    state[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        LongHorizonStressObservation.from_state(state)


@pytest.mark.parametrize("field", _INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _INTEGER_ALIASES)
def test_record_stress_rejects_non_exact_integer_authority(
    field: str,
    alias: object,
) -> None:
    ledger = _ledger()
    kwargs = _kwargs(**{field: alias})

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        ledger.record_stress(**kwargs)


def test_exact_integer_stress_authority_roundtrips_without_semantic_change() -> None:
    canonical = _canonical_observation()

    assert all(type(getattr(canonical, field)) is int for field in _INTEGER_FIELDS)
    assert LongHorizonStressObservation.from_state(canonical.to_state()) == canonical
