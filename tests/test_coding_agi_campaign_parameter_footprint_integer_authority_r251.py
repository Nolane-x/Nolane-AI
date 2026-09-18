from __future__ import annotations

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest
from nolane.evaluation.evidence import EvaluationEvidenceLedger
from nolane.evaluation.parameters import ParameterFootprintReport, ParameterScalingAuthority
from nolane.evaluation.regimes import BenchmarkRegimeRegistry


_INTEGER_FIELDS = (
    "active_ephemeral_count",
    "shared_physical_parameters",
    "local_physical_parameters",
    "unique_stored_physical_parameters",
    "active_inference_physical_parameters",
    "logical_deployed_parameter_footprint",
    "compute_units",
    "latency_ms",
)
_CONSTRUCTOR_ALIASES = (True, 1.0)
_INGRESS_ALIASES = (True, 1.0, "1")
_INGRESS_FIELDS = ("active_ephemeral_count", "compute_units", "latency_ms")


def _values_for(field: str | None = None) -> dict[str, object]:
    values: dict[str, object] = {
        "active_ephemeral_count": 1,
        "shared_physical_parameters": 1,
        "local_physical_parameters": 0,
        "unique_stored_physical_parameters": 1,
        "active_inference_physical_parameters": 1,
        "logical_deployed_parameter_footprint": 1,
        "compute_units": 1,
        "latency_ms": 1,
    }
    if field == "local_physical_parameters":
        values.update(
            shared_physical_parameters=0,
            local_physical_parameters=1,
            unique_stored_physical_parameters=1,
            active_inference_physical_parameters=1,
            logical_deployed_parameter_footprint=1,
        )
    return values


def _report(*, field: str | None = None, alias: object | None = None) -> ParameterFootprintReport:
    values = _values_for(field)
    if field is not None:
        values[field] = alias
    payload = {
        "report_id": "parameter-footprint-r251",
        "active_agent_ids": ["agent-r251"],
        **values,
        "energy_joules": 1.0,
    }
    return ParameterFootprintReport(
        report_id=payload["report_id"],
        active_agent_ids=tuple(payload["active_agent_ids"]),
        active_ephemeral_count=payload["active_ephemeral_count"],
        shared_physical_parameters=payload["shared_physical_parameters"],
        local_physical_parameters=payload["local_physical_parameters"],
        unique_stored_physical_parameters=payload["unique_stored_physical_parameters"],
        active_inference_physical_parameters=payload["active_inference_physical_parameters"],
        logical_deployed_parameter_footprint=payload["logical_deployed_parameter_footprint"],
        compute_units=payload["compute_units"],
        latency_ms=payload["latency_ms"],
        energy_joules=payload["energy_joules"],
        digest=canonical_digest(payload),
    )


def _canonical_state(field: str) -> dict[str, object]:
    values = _values_for(field)
    payload = {
        "report_id": "parameter-footprint-r251",
        "active_agent_ids": ["agent-r251"],
        **values,
        "energy_joules": 1.0,
    }
    return {**payload, "digest": canonical_digest(payload)}


@pytest.mark.parametrize("field", _INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _CONSTRUCTOR_ALIASES)
def test_parameter_footprint_constructor_rejects_non_exact_integer_authority(
    field: str,
    alias: object,
) -> None:
    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        _report(field=field, alias=alias)


@pytest.mark.parametrize("field", _INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _INGRESS_ALIASES)
def test_parameter_footprint_restore_rejects_integer_alias_laundering(
    field: str,
    alias: object,
) -> None:
    state = _canonical_state(field)
    state[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        ParameterFootprintReport.from_state(state)


def _authority() -> ParameterScalingAuthority:
    runtime = OrganizationRuntime.first_generation()
    evidence = EvaluationEvidenceLedger(
        registry=runtime.registry,
        regimes=BenchmarkRegimeRegistry(),
    )
    return ParameterScalingAuthority(registry=runtime.registry, evidence=evidence)


@pytest.mark.parametrize("field", _INGRESS_FIELDS)
@pytest.mark.parametrize("alias", _INGRESS_ALIASES)
def test_parameter_footprint_api_rejects_integer_alias_laundering(
    field: str,
    alias: object,
) -> None:
    kwargs: dict[str, object] = {
        "active_agent_ids": ("nolane.central",),
        "active_ephemeral_count": 1,
        "compute_units": 1,
        "latency_ms": 1,
        "energy_joules": 1.0,
    }
    kwargs[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        _authority().parameter_footprint(**kwargs)


def test_parameter_footprint_preserves_canonical_integer_round_trip() -> None:
    state = _canonical_state("compute_units")
    restored = ParameterFootprintReport.from_state(state)

    assert restored.to_state() == state
    for field in _INTEGER_FIELDS:
        assert type(getattr(restored, field)) is int
