from __future__ import annotations

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.evaluation.claims import (
    ClaimAssessment,
    ClaimClass,
    ClaimDisposition,
    OrganizationReadinessReport,
)


_BOOL_ALIASES = (0, 0.0, 1, 1.0, "", "false", "true")


def _claim(*, override_effective: object) -> ClaimAssessment:
    return ClaimAssessment(
        claim_id="claim-r248",
        claim_class=ClaimClass.INTERNAL_ENGINEERING_PROGRESS,
        disposition=ClaimDisposition.LIMITED,
        observation_ids=(),
        comparison_ids=(),
        stress_assessment_id=None,
        reproduction_receipt_id=None,
        reasons=(),
        limitations=("internal_engineering_evidence_only",),
        override_effective=override_effective,
        digest="digest-r248",
    )


def _claim_state(*, override_effective: bool) -> dict[str, object]:
    row = _claim(override_effective=override_effective)
    payload = row.payload()
    return {**payload, "digest": canonical_digest(payload)}


@pytest.mark.parametrize("alias", _BOOL_ALIASES)
def test_claim_assessment_constructor_rejects_non_bool_override_aliases(alias: object) -> None:
    with pytest.raises(ValueError, match="override_effective.*exact bool"):
        _claim(override_effective=alias)


@pytest.mark.parametrize(("canonical", "alias"), ((False, 0), (False, 0.0), (True, 1), (True, 1.0)))
def test_claim_assessment_restore_rejects_digest_preserving_override_aliases(
    canonical: bool,
    alias: object,
) -> None:
    state = _claim_state(override_effective=canonical)
    state["override_effective"] = alias

    with pytest.raises(ValueError, match="override_effective.*exact bool"):
        ClaimAssessment.from_state(state)


@pytest.mark.parametrize("override_effective", (False, True))
def test_claim_assessment_preserves_canonical_bool_round_trip(override_effective: bool) -> None:
    state = _claim_state(override_effective=override_effective)
    restored = ClaimAssessment.from_state(state)

    assert restored.to_state() == state
    assert type(restored.override_effective) is bool


def _readiness(*, gate_value: object) -> OrganizationReadinessReport:
    return OrganizationReadinessReport(
        report_id="readiness-r248",
        claim_assessment_ids=("claim-r248",),
        gates={"benchmark_coverage": gate_value},
        digest="digest-r248",
    )


def _readiness_state(*, gate_value: bool) -> dict[str, object]:
    row = _readiness(gate_value=gate_value)
    payload = row.payload()
    return {**payload, "digest": canonical_digest(payload)}


@pytest.mark.parametrize("alias", _BOOL_ALIASES)
def test_readiness_constructor_rejects_non_bool_gate_aliases(alias: object) -> None:
    with pytest.raises(ValueError, match="readiness gate.*exact bool"):
        _readiness(gate_value=alias)


@pytest.mark.parametrize(("canonical", "alias"), ((False, 0), (False, 0.0), (True, 1), (True, 1.0)))
def test_readiness_restore_rejects_digest_preserving_gate_aliases(
    canonical: bool,
    alias: object,
) -> None:
    state = _readiness_state(gate_value=canonical)
    state["gates"]["benchmark_coverage"] = alias

    with pytest.raises(ValueError, match="readiness gate.*exact bool"):
        OrganizationReadinessReport.from_state(state)


@pytest.mark.parametrize("gate_value", (False, True))
def test_readiness_preserves_canonical_bool_round_trip(gate_value: bool) -> None:
    state = _readiness_state(gate_value=gate_value)
    restored = OrganizationReadinessReport.from_state(state)

    assert restored.to_state() == state
    assert type(restored.gates["benchmark_coverage"]) is bool
