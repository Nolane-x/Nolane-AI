from __future__ import annotations

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.evaluation.regimes import (
    BenchmarkDomain,
    BenchmarkRegime,
    BenchmarkRegimeRegistry,
    EvidenceProvenanceClass,
)


_INTEGER_FIELDS = (
    "compute_budget_units",
    "tool_call_budget",
    "external_core_budget",
    "wall_clock_budget_ms",
    "active_agent_budget",
    "freshness_epoch",
)
_REGISTER_ALIASES = (True, 1.0, "1")
_CONSTRUCTOR_ALIASES = (True, 1.0)


def _registration_kwargs() -> dict[str, object]:
    return {
        "regime_id": "regime-r250",
        "benchmark_id": "benchmark-r250",
        "domain": BenchmarkDomain.CODING,
        "task_set_digest": "tasks-r250",
        "repository_revision_digest": "repo-r250",
        "tool_envelope_digest": "tools-r250",
        "compute_budget_units": 1,
        "tool_call_budget": 1,
        "external_core_budget": 1,
        "wall_clock_budget_ms": 1,
        "active_agent_budget": 1,
        "freshness_epoch": 1,
        "evaluator_protocol_version": "protocol-r250",
        "provenance_class": EvidenceProvenanceClass.INTERNAL_REAL_REPOSITORY,
        "fresh": True,
        "heldout": True,
    }


def _canonical_row() -> BenchmarkRegime:
    return BenchmarkRegimeRegistry().register(**_registration_kwargs())


def _direct_row(field: str, alias: object) -> BenchmarkRegime:
    kwargs = _registration_kwargs()
    kwargs[field] = alias
    budget_payload = {
        "compute_budget_units": kwargs["compute_budget_units"],
        "tool_call_budget": kwargs["tool_call_budget"],
        "external_core_budget": kwargs["external_core_budget"],
        "wall_clock_budget_ms": kwargs["wall_clock_budget_ms"],
        "active_agent_budget": kwargs["active_agent_budget"],
    }
    budget_digest = canonical_digest(budget_payload)
    regime_payload = {
        "regime_id": kwargs["regime_id"],
        "benchmark_id": kwargs["benchmark_id"],
        "domain": BenchmarkDomain(kwargs["domain"]).value,
        "task_set_digest": kwargs["task_set_digest"],
        "repository_revision_digest": kwargs["repository_revision_digest"],
        "tool_envelope_digest": kwargs["tool_envelope_digest"],
        "budget_digest": budget_digest,
        "freshness_epoch": kwargs["freshness_epoch"],
        "evaluator_protocol_version": kwargs["evaluator_protocol_version"],
        "provenance_class": EvidenceProvenanceClass(kwargs["provenance_class"]).value,
        "fresh": kwargs["fresh"],
        "heldout": kwargs["heldout"],
    }
    return BenchmarkRegime(
        regime_id=str(kwargs["regime_id"]),
        benchmark_id=str(kwargs["benchmark_id"]),
        domain=BenchmarkDomain(kwargs["domain"]),
        task_set_digest=str(kwargs["task_set_digest"]),
        repository_revision_digest=str(kwargs["repository_revision_digest"]),
        tool_envelope_digest=str(kwargs["tool_envelope_digest"]),
        compute_budget_units=kwargs["compute_budget_units"],
        tool_call_budget=kwargs["tool_call_budget"],
        external_core_budget=kwargs["external_core_budget"],
        wall_clock_budget_ms=kwargs["wall_clock_budget_ms"],
        active_agent_budget=kwargs["active_agent_budget"],
        freshness_epoch=kwargs["freshness_epoch"],
        evaluator_protocol_version=str(kwargs["evaluator_protocol_version"]),
        provenance_class=EvidenceProvenanceClass(kwargs["provenance_class"]),
        fresh=True,
        heldout=True,
        budget_digest=budget_digest,
        regime_digest=canonical_digest(regime_payload),
    )


@pytest.mark.parametrize("field", _INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _CONSTRUCTOR_ALIASES)
def test_regime_constructor_rejects_non_exact_integer_authority_aliases(
    field: str,
    alias: object,
) -> None:
    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        _direct_row(field, alias)


@pytest.mark.parametrize("field", _INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _REGISTER_ALIASES)
def test_regime_register_rejects_integer_authority_aliases(field: str, alias: object) -> None:
    kwargs = _registration_kwargs()
    kwargs[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        BenchmarkRegimeRegistry().register(**kwargs)


@pytest.mark.parametrize("field", _INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _REGISTER_ALIASES)
def test_regime_restore_rejects_digest_preserving_integer_aliases(field: str, alias: object) -> None:
    state = _canonical_row().to_state()
    state[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        BenchmarkRegime.from_state(state)


def test_regime_preserves_canonical_integer_round_trip() -> None:
    row = _canonical_row()
    restored = BenchmarkRegime.from_state(row.to_state())

    assert restored == row
    for field in _INTEGER_FIELDS:
        assert type(getattr(restored, field)) is int
