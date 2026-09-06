from __future__ import annotations

from nolane.external_core.observation_population import validate_observed_component_population


def test_missing_actual_registry_component_is_reported() -> None:
    findings = validate_observed_component_population(
        expected_component_ids=("external.alpha", "external.beta"),
        contract_component_ids=("external.alpha", "external.beta"),
        observed_component_ids=("external.alpha",),
    )

    assert {row.code for row in findings} == {"OBSERVATION_REQUIRED_COMPONENT_UNOBSERVED"}
    assert {row.subject_id for row in findings} == {"external.beta"}


def test_unexpected_actual_registry_component_is_reported() -> None:
    findings = validate_observed_component_population(
        expected_component_ids=("external.alpha",),
        contract_component_ids=("external.alpha",),
        observed_component_ids=("external.alpha", "external.gamma"),
    )

    assert {row.code for row in findings} == {"OBSERVATION_UNEXPECTED_COMPONENT_OBSERVED"}
    assert {row.subject_id for row in findings} == {"external.gamma"}


def test_exact_actual_registry_population_is_clean() -> None:
    findings = validate_observed_component_population(
        expected_component_ids=("external.beta", "external.alpha"),
        contract_component_ids=("external.alpha", "external.beta"),
        observed_component_ids=("external.beta", "external.alpha"),
    )

    assert findings == ()
