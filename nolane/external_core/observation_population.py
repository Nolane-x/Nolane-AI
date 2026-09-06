from __future__ import annotations

from typing import Sequence

from nolane.external_core.observation import ObservationFinding


def _component_ids(values: Sequence[str], label: str) -> tuple[str, ...]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        if type(value) is not str or not value.strip():
            raise ValueError(f"{label} must contain exact non-empty strings")
        if value in seen:
            raise ValueError(f"duplicate {label}: {value}")
        seen.add(value)
        rows.append(value)
    return tuple(sorted(rows))


def validate_observed_component_population(
    *,
    expected_component_ids: Sequence[str],
    contract_component_ids: Sequence[str],
    observed_component_ids: Sequence[str],
) -> tuple[ObservationFinding, ...]:
    """Classify negative-space drift in the actually observed registry population.

    The surface contract states what should be observed, but it is not evidence
    that the registry actually contained those components. This validator keeps
    the contract population and the detached observed population separate so a
    missing component cannot be laundered by copying the expected IDs into the
    observation contract.
    """

    expected = set(_component_ids(expected_component_ids, "expected component identity"))
    contract = set(_component_ids(contract_component_ids, "contract component identity"))
    observed = set(_component_ids(observed_component_ids, "observed component identity"))

    findings: list[ObservationFinding] = []
    for component_id in sorted((expected | contract) - observed):
        findings.append(
            ObservationFinding(
                code="OBSERVATION_REQUIRED_COMPONENT_UNOBSERVED",
                detail="required canonical component is absent from the detached observed registry population",
                subject_id=component_id,
            )
        )
    for component_id in sorted(observed - (expected | contract)):
        findings.append(
            ObservationFinding(
                code="OBSERVATION_UNEXPECTED_COMPONENT_OBSERVED",
                detail="detached observed registry population contains an undeclared canonical component",
                subject_id=component_id,
            )
        )

    return tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))


__all__ = ("validate_observed_component_population",)
