from __future__ import annotations

import copy

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.evaluation_regimes import (
    BenchmarkDomain,
    BenchmarkRegime,
    BenchmarkRegimeRegistry,
    EvidenceProvenanceClass,
)


def _register(
    registry: BenchmarkRegimeRegistry,
    *,
    fresh: object = True,
    heldout: object = True,
):
    return registry.register(
        regime_id="r243-regime",
        benchmark_id="r243-benchmark",
        domain=BenchmarkDomain.CODING,
        task_set_digest="r243-tasks",
        repository_revision_digest="r243-repo",
        tool_envelope_digest="r243-tools",
        compute_budget_units=100,
        tool_call_budget=10,
        external_core_budget=2,
        wall_clock_budget_ms=10_000,
        active_agent_budget=4,
        freshness_epoch=7,
        evaluator_protocol_version="r243-protocol",
        provenance_class=EvidenceProvenanceClass.EXTERNAL_INDEPENDENT,
        fresh=fresh,
        heldout=heldout,
    )


@pytest.mark.parametrize("field", ["fresh", "heldout"])
@pytest.mark.parametrize("alias", ["false", "true", 0, 1])
def test_regime_registration_rejects_non_boolean_authority(
    field: str,
    alias: object,
) -> None:
    kwargs = {"fresh": True, "heldout": True, field: alias}
    with pytest.raises(ValueError, match=f"benchmark regime {field}.*exact bool"):
        _register(BenchmarkRegimeRegistry(), **kwargs)


@pytest.mark.parametrize("field", ["fresh", "heldout"])
@pytest.mark.parametrize("alias", ["false", 1])
def test_benchmark_regime_constructor_rejects_non_boolean_authority(
    field: str,
    alias: object,
) -> None:
    row = _register(BenchmarkRegimeRegistry())
    values = row.registration_kwargs()
    values[field] = alias

    with pytest.raises(ValueError, match=f"benchmark regime {field}.*exact bool"):
        BenchmarkRegime(
            **values,
            budget_digest=row.budget_digest,
            regime_digest=row.regime_digest,
        )


@pytest.mark.parametrize("field", ["fresh", "heldout"])
@pytest.mark.parametrize("alias", ["false", "true", 0, 1])
def test_benchmark_regime_restore_rejects_non_boolean_authority(
    field: str,
    alias: object,
) -> None:
    row = _register(BenchmarkRegimeRegistry())
    state = row.to_state()
    state[field] = alias

    with pytest.raises(ValueError, match=f"benchmark regime {field}.*exact bool"):
        BenchmarkRegime.from_state(state)


@pytest.mark.parametrize("field", ["fresh", "heldout"])
@pytest.mark.parametrize("alias", ["false", 1])
def test_runtime_restore_rejects_truthy_benchmark_regime_alias(
    field: str,
    alias: object,
) -> None:
    runtime = OrganizationRuntime.first_generation()
    _register(runtime.evaluation_scaling.regimes)

    state = copy.deepcopy(runtime.to_state())
    state["evaluation_scaling"]["regimes"]["regimes"][0][field] = alias

    with pytest.raises(ValueError, match=f"benchmark regime {field}.*exact bool"):
        OrganizationRuntime.from_state(state)
