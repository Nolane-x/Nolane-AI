from __future__ import annotations

from dataclasses import replace

import pytest

from nolane.evaluation.evidence import EvaluationEvidenceLedger
from nolane.evaluation.regimes import (
    BenchmarkDomain,
    BenchmarkRegimeRegistry,
    EvidenceProvenanceClass,
    EvaluationMode,
)
from nolane.external_core.evidence import EvidenceRecord
from nolane.organization.identity import AgentRegistry
from nolane.schemas.identity import AgentIdentity, AgentRank, ParameterAccounting


_OBSERVATION_INTEGER_FIELDS = (
    "task_count",
    "pass_count",
    "false_accepts",
    "regressions",
    "compute_units",
    "tool_calls",
    "external_core_calls",
    "wall_clock_ms",
    "active_agents",
)
_ABLATION_INTEGER_FIELDS = (
    "false_accept_delta",
    "regression_delta",
    "compute_delta",
)
_CONSTRUCTOR_ALIASES = (True, 1.0)
_INGRESS_ALIASES = (True, 1.0, "1")


def _ledger() -> tuple[EvaluationEvidenceLedger, EvidenceRecord]:
    verifier = AgentIdentity(
        agent_id="r253-verifier",
        name="R2.53 Verifier",
        region="evaluation",
        role="evaluation verifier",
        rank=AgentRank.SPECIALIST,
        neural_version="neural-r253",
        parameter_accounting=ParameterAccounting(1, 1),
        region_chief_id="evaluation-chief",
        direct_work_capable=True,
        learning_capable=True,
        cognitive_capabilities=("verification",),
        memory_namespace="memory.r253-verifier",
        skill_namespace="skills.r253-verifier",
    )
    registry = AgentRegistry((verifier,))
    regimes = BenchmarkRegimeRegistry()
    regimes.register(
        regime_id="r253-regime",
        benchmark_id="r253-benchmark",
        domain=BenchmarkDomain.CODING,
        task_set_digest="r253-tasks",
        repository_revision_digest="r253-repository",
        tool_envelope_digest="r253-tools",
        compute_budget_units=100,
        tool_call_budget=10,
        external_core_budget=5,
        wall_clock_budget_ms=1_000,
        active_agent_budget=4,
        freshness_epoch=1,
        evaluator_protocol_version="r253-protocol",
        provenance_class=EvidenceProvenanceClass.INTERNAL_REAL_REPOSITORY,
        fresh=True,
        heldout=True,
    )
    evidence = EvidenceRecord(
        evidence_id="r253-evidence",
        verifier_agent_id=verifier.agent_id,
        passed=True,
        false_accepts=0,
        regressions=0,
        notes="R2.53 exact integer evaluation evidence authority",
    )
    return EvaluationEvidenceLedger(registry=registry, regimes=regimes), evidence


def _record(
    ledger: EvaluationEvidenceLedger,
    evidence: EvidenceRecord,
    *,
    observation_id: str = "r253-observation",
    mode: EvaluationMode = EvaluationMode.ORGANIZATION,
    score: float = 0.8,
    **overrides: object,
):
    kwargs: dict[str, object] = {
        "observation_id": observation_id,
        "regime_id": "r253-regime",
        "mode": mode,
        "producer_revision": f"{observation_id}-revision",
        "score": score,
        "task_count": 10,
        "pass_count": 8,
        "false_accepts": 0,
        "regressions": 0,
        "compute_units": 80,
        "tool_calls": 8,
        "external_core_calls": 4,
        "wall_clock_ms": 800,
        "energy_joules": 2.5,
        "active_agents": 4,
        "evidence_artifact_ids": (f"artifact-{observation_id}",),
        "evidence": evidence,
    }
    kwargs.update(overrides)
    return ledger.record_observation(**kwargs)


def _observation():
    ledger, evidence = _ledger()
    return _record(ledger, evidence)


def _ablation():
    ledger, evidence = _ledger()
    full = _record(
        ledger,
        evidence,
        observation_id="r253-full",
        mode=EvaluationMode.ORGANIZATION,
        score=0.80,
    )
    ablated = _record(
        ledger,
        evidence,
        observation_id="r253-ablation",
        mode=EvaluationMode.ORGANIZATION_NO_MEMORY,
        score=0.70,
        pass_count=7,
        false_accepts=1,
        regressions=1,
        compute_units=70,
    )
    return ledger.assess_ablation(full.observation_id, ablated.observation_id)


@pytest.mark.parametrize("field", _OBSERVATION_INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _CONSTRUCTOR_ALIASES)
def test_evaluation_observation_constructor_rejects_non_exact_integer_authority(
    field: str,
    alias: object,
) -> None:
    row = _observation()
    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        replace(row, **{field: alias})


@pytest.mark.parametrize("field", _OBSERVATION_INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _INGRESS_ALIASES)
def test_evaluation_observation_restore_rejects_integer_alias_laundering(
    field: str,
    alias: object,
) -> None:
    row = _observation()
    state = row.to_state()
    state[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        type(row).from_state(state)


@pytest.mark.parametrize("field", _OBSERVATION_INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _INGRESS_ALIASES)
def test_record_observation_rejects_integer_alias_laundering(
    field: str,
    alias: object,
) -> None:
    ledger, evidence = _ledger()

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        _record(ledger, evidence, **{field: alias})


@pytest.mark.parametrize("field", _ABLATION_INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _CONSTRUCTOR_ALIASES)
def test_ablation_constructor_rejects_non_exact_integer_authority(
    field: str,
    alias: object,
) -> None:
    row = _ablation()
    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        replace(row, **{field: alias})


@pytest.mark.parametrize("field", _ABLATION_INTEGER_FIELDS)
@pytest.mark.parametrize("alias", _INGRESS_ALIASES)
def test_ablation_restore_rejects_integer_alias_laundering(
    field: str,
    alias: object,
) -> None:
    row = _ablation()
    state = row.to_state()
    state[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*exact int"):
        type(row).from_state(state)


def test_evaluation_evidence_preserves_canonical_integer_roundtrip() -> None:
    ledger, evidence = _ledger()
    _record(ledger, evidence)
    state = ledger.to_state()
    restored = EvaluationEvidenceLedger.from_state(
        registry=ledger.registry,
        regimes=ledger.regimes,
        state=state,
    )

    assert restored.to_state() == state
    observation = restored.get_observation("r253-observation")
    for field in _OBSERVATION_INTEGER_FIELDS:
        assert type(getattr(observation, field)) is int

    ablation = _ablation()
    restored_ablation = type(ablation).from_state(ablation.to_state())
    assert restored_ablation == ablation
    for field in _ABLATION_INTEGER_FIELDS:
        assert type(getattr(restored_ablation, field)) is int
