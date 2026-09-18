from __future__ import annotations

import math

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest
from nolane.evaluation.evidence import EvaluationEvidenceLedger
from nolane.evaluation.parameters import ParameterScalingAuthority, ScalingProposal
from nolane.evaluation.regimes import (
    BenchmarkDomain,
    BenchmarkRegimeRegistry,
    EvidenceProvenanceClass,
    EvaluationMode,
)
from nolane.external_core.evidence import EvidenceRecord


_NUMERIC_FIELDS = ("compute_cost_ratio", "energy_delta_joules")
_INVALID_NUMERIC_ALIASES = (True, "1.5", float("nan"), float("inf"), float("-inf"))


def _proposal_values() -> dict[str, object]:
    return {
        "compute_cost_ratio": 1.25,
        "energy_delta_joules": 100.0,
    }


def _proposal(*, field: str | None = None, alias: object | None = None) -> ScalingProposal:
    values = _proposal_values()
    if field is not None:
        values[field] = alias
    payload = {
        "proposal_id": "scaling-proposal-r254",
        "agent_id": "agent-r254",
        "current_physical_parameters": 1,
        "candidate_physical_parameters": 2,
        "baseline_observation_id": "baseline-r254",
        "candidate_observation_id": "candidate-r254",
        **values,
        "storage_delta_bytes": 1,
        "latency_delta_ms": 1,
        "economic_capacity_digest": "capacity-r254",
        "verifier_ids": ["verification.chief", "architecture.chief"],
        "external_evaluator_id": "external-lab-r254",
        "evidence_ids": ["evidence-r254"],
    }
    return ScalingProposal(
        proposal_id=payload["proposal_id"],
        agent_id=payload["agent_id"],
        current_physical_parameters=payload["current_physical_parameters"],
        candidate_physical_parameters=payload["candidate_physical_parameters"],
        baseline_observation_id=payload["baseline_observation_id"],
        candidate_observation_id=payload["candidate_observation_id"],
        compute_cost_ratio=payload["compute_cost_ratio"],
        storage_delta_bytes=payload["storage_delta_bytes"],
        latency_delta_ms=payload["latency_delta_ms"],
        energy_delta_joules=payload["energy_delta_joules"],
        economic_capacity_digest=payload["economic_capacity_digest"],
        verifier_ids=tuple(payload["verifier_ids"]),
        external_evaluator_id=payload["external_evaluator_id"],
        evidence_ids=tuple(payload["evidence_ids"]),
        digest=canonical_digest(payload),
    )


def _canonical_state() -> dict[str, object]:
    return _proposal().to_state()


def _authority() -> tuple[ParameterScalingAuthority, str, str]:
    runtime = OrganizationRuntime.first_generation()
    regimes = BenchmarkRegimeRegistry()
    regime = regimes.register(
        regime_id="scale-r254",
        benchmark_id="scale-suite-r254",
        domain=BenchmarkDomain.CODING,
        task_set_digest="tasks-r254",
        repository_revision_digest="repo-r254",
        tool_envelope_digest="tools-r254",
        compute_budget_units=100,
        tool_call_budget=10,
        external_core_budget=3,
        wall_clock_budget_ms=20_000,
        active_agent_budget=2,
        freshness_epoch=10,
        evaluator_protocol_version="p-r254",
        provenance_class=EvidenceProvenanceClass.EXTERNAL_INDEPENDENT,
        fresh=True,
        heldout=True,
    )
    ledger = EvaluationEvidenceLedger(registry=runtime.registry, regimes=regimes)

    def observation(observation_id: str, score: float):
        return ledger.record_observation(
            observation_id=observation_id,
            regime_id=regime.regime_id,
            mode=EvaluationMode.SINGLE_AGENT,
            producer_revision=observation_id,
            score=score,
            task_count=100,
            pass_count=int(score * 100),
            false_accepts=0,
            regressions=0,
            compute_units=80,
            tool_calls=5,
            external_core_calls=1,
            wall_clock_ms=10_000,
            energy_joules=500.0,
            active_agents=1,
            evidence_artifact_ids=(f"artifact-{observation_id}",),
            evidence=EvidenceRecord(f"evidence-{observation_id}", "verification.chief", True),
            external_evaluator_id="external-lab-r254",
        )

    baseline = observation("baseline-r254", 0.70)
    candidate = observation("candidate-r254", 0.75)
    return (
        ParameterScalingAuthority(registry=runtime.registry, evidence=ledger),
        baseline.observation_id,
        candidate.observation_id,
    )


def _api_kwargs(baseline_id: str, candidate_id: str) -> dict[str, object]:
    return {
        "proposal_id": "proposal-api-r254",
        "agent_id": "coding.backend.01",
        "candidate_physical_parameters": 120_000_000,
        "baseline_observation_id": baseline_id,
        "candidate_observation_id": candidate_id,
        "compute_cost_ratio": 1.5,
        "storage_delta_bytes": 250_000_000,
        "latency_delta_ms": 80,
        "energy_delta_joules": 100.0,
        "economic_capacity_digest": "capacity-r254",
        "verifier_ids": ("verification.chief", "architecture.chief"),
        "external_evaluator_id": "external-lab-r254",
        "evidence_ids": ("budget-proof-r254",),
    }


@pytest.mark.parametrize("field", _NUMERIC_FIELDS)
@pytest.mark.parametrize("alias", _INVALID_NUMERIC_ALIASES)
def test_scaling_proposal_constructor_rejects_noncanonical_or_nonfinite_numeric_authority(
    field: str,
    alias: object,
) -> None:
    with pytest.raises(ValueError, match=rf"{field}.*(exact numeric|finite)"):
        _proposal(field=field, alias=alias)


@pytest.mark.parametrize("field", _NUMERIC_FIELDS)
@pytest.mark.parametrize("alias", _INVALID_NUMERIC_ALIASES)
def test_scaling_proposal_restore_rejects_numeric_alias_or_nonfinite_laundering(
    field: str,
    alias: object,
) -> None:
    state = _canonical_state()
    state[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*(exact numeric|finite)"):
        ScalingProposal.from_state(state)


@pytest.mark.parametrize("field", _NUMERIC_FIELDS)
@pytest.mark.parametrize("alias", _INVALID_NUMERIC_ALIASES)
def test_scaling_proposal_api_rejects_numeric_alias_or_nonfinite_laundering(
    field: str,
    alias: object,
) -> None:
    authority, baseline_id, candidate_id = _authority()
    kwargs = _api_kwargs(baseline_id, candidate_id)
    kwargs[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*(exact numeric|finite)"):
        authority.propose_scaling(**kwargs)


@pytest.mark.parametrize("field", _NUMERIC_FIELDS)
@pytest.mark.parametrize("value", (0, 1, 0.0, 1.25))
def test_scaling_proposal_accepts_exact_finite_builtin_numeric_authority(
    field: str,
    value: int | float,
) -> None:
    proposal = _proposal(field=field, alias=value)
    normalized = getattr(proposal, field)

    assert type(normalized) is float
    assert math.isfinite(normalized)
    assert normalized == float(value)


def test_scaling_proposal_preserves_canonical_finite_numeric_round_trip() -> None:
    state = _canonical_state()
    restored = ScalingProposal.from_state(state)

    assert restored.to_state() == state
    for field in _NUMERIC_FIELDS:
        value = getattr(restored, field)
        assert type(value) is float
        assert math.isfinite(value)
