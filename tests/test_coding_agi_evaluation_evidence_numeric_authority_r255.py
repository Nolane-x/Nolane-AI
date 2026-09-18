from __future__ import annotations

from dataclasses import replace
import math

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.evaluation.evidence import (
    AblationAssessment,
    EvaluationEvidenceLedger,
    MatchedBudgetComparison,
)
from nolane.evaluation.regimes import (
    BenchmarkDomain,
    BenchmarkRegimeRegistry,
    EvidenceProvenanceClass,
    EvaluationMode,
)
from nolane.external_core.evidence import EvidenceRecord
from nolane.organization.identity import AgentRegistry
from nolane.schemas.identity import AgentIdentity, AgentRank, ParameterAccounting


_OBSERVATION_NUMERIC_FIELDS = ("score", "energy_joules")
_INVALID_NUMERIC_ALIASES = (True, "1.0", float("nan"), float("inf"), float("-inf"))


def _ledger() -> tuple[EvaluationEvidenceLedger, EvidenceRecord]:
    verifier = AgentIdentity(
        agent_id="r255-verifier",
        name="R2.55 Verifier",
        region="evaluation",
        role="evaluation verifier",
        rank=AgentRank.SPECIALIST,
        neural_version="neural-r255",
        parameter_accounting=ParameterAccounting(1, 1),
        region_chief_id="evaluation-chief",
        direct_work_capable=True,
        learning_capable=True,
        cognitive_capabilities=("verification",),
        memory_namespace="memory.r255-verifier",
        skill_namespace="skills.r255-verifier",
    )
    registry = AgentRegistry((verifier,))
    regimes = BenchmarkRegimeRegistry()
    regimes.register(
        regime_id="r255-regime",
        benchmark_id="r255-benchmark",
        domain=BenchmarkDomain.CODING,
        task_set_digest="r255-tasks",
        repository_revision_digest="r255-repository",
        tool_envelope_digest="r255-tools",
        compute_budget_units=100,
        tool_call_budget=10,
        external_core_budget=5,
        wall_clock_budget_ms=1_000,
        active_agent_budget=4,
        freshness_epoch=1,
        evaluator_protocol_version="r255-protocol",
        provenance_class=EvidenceProvenanceClass.INTERNAL_REAL_REPOSITORY,
        fresh=True,
        heldout=True,
    )
    evidence = EvidenceRecord(
        evidence_id="r255-evidence",
        verifier_agent_id=verifier.agent_id,
        passed=True,
        false_accepts=0,
        regressions=0,
        notes="R2.55 finite numeric evaluation evidence authority",
    )
    return EvaluationEvidenceLedger(registry=registry, regimes=regimes), evidence


def _record(
    ledger: EvaluationEvidenceLedger,
    evidence: EvidenceRecord,
    *,
    observation_id: str = "r255-observation",
    mode: EvaluationMode = EvaluationMode.ORGANIZATION,
    score: object = 1.0,
    energy_joules: object | None = 1.0,
    **overrides: object,
):
    kwargs: dict[str, object] = {
        "observation_id": observation_id,
        "regime_id": "r255-regime",
        "mode": mode,
        "producer_revision": f"{observation_id}-revision",
        "score": score,
        "task_count": 10,
        "pass_count": 10,
        "false_accepts": 0,
        "regressions": 0,
        "compute_units": 80,
        "tool_calls": 8,
        "external_core_calls": 4,
        "wall_clock_ms": 800,
        "energy_joules": energy_joules,
        "active_agents": 4,
        "evidence_artifact_ids": (f"artifact-{observation_id}",),
        "evidence": evidence,
    }
    kwargs.update(overrides)
    return ledger.record_observation(**kwargs)


def _observation():
    ledger, evidence = _ledger()
    return _record(ledger, evidence)


def _comparison(*, score_delta: object = 1.0) -> MatchedBudgetComparison:
    return MatchedBudgetComparison(
        comparison_id="comparison-r255",
        organization_observation_id="org-r255",
        baseline_observation_id="baseline-r255",
        baseline_mode=EvaluationMode.SINGLE_AGENT,
        comparable=True,
        improved=True,
        score_delta=score_delta,
        reason="r255",
        digest="digest-r255",
    )


def _comparison_state() -> dict[str, object]:
    row = _comparison(score_delta=1.0)
    payload = row.payload()
    return {**payload, "digest": canonical_digest(payload)}


def _ablation(*, score_delta: object = 1.0) -> AblationAssessment:
    return AblationAssessment(
        assessment_id="ablation-r255",
        full_observation_id="org-r255",
        ablation_observation_id="ablation-observation-r255",
        ablation_mode=EvaluationMode.ORGANIZATION_NO_MEMORY,
        comparable=True,
        score_delta=score_delta,
        false_accept_delta=0,
        regression_delta=0,
        compute_delta=1,
        reason="r255",
        digest="digest-r255",
    )


def _ablation_state() -> dict[str, object]:
    row = _ablation(score_delta=1.0)
    payload = row.payload()
    return {**payload, "digest": canonical_digest(payload)}


@pytest.mark.parametrize("field", _OBSERVATION_NUMERIC_FIELDS)
@pytest.mark.parametrize("alias", _INVALID_NUMERIC_ALIASES)
def test_evaluation_observation_constructor_rejects_noncanonical_or_nonfinite_numeric_authority(
    field: str,
    alias: object,
) -> None:
    row = _observation()

    with pytest.raises(ValueError, match=rf"{field}.*(exact numeric|finite)"):
        replace(row, **{field: alias})


@pytest.mark.parametrize("field", _OBSERVATION_NUMERIC_FIELDS)
@pytest.mark.parametrize("alias", _INVALID_NUMERIC_ALIASES)
def test_evaluation_observation_restore_rejects_numeric_alias_or_nonfinite_laundering(
    field: str,
    alias: object,
) -> None:
    row = _observation()
    state = row.to_state()
    state[field] = alias

    with pytest.raises(ValueError, match=rf"{field}.*(exact numeric|finite)"):
        type(row).from_state(state)


@pytest.mark.parametrize("field", _OBSERVATION_NUMERIC_FIELDS)
@pytest.mark.parametrize("alias", _INVALID_NUMERIC_ALIASES)
def test_record_observation_rejects_numeric_alias_or_nonfinite_laundering(
    field: str,
    alias: object,
) -> None:
    ledger, evidence = _ledger()
    kwargs = {field: alias}

    with pytest.raises(ValueError, match=rf"{field}.*(exact numeric|finite)"):
        _record(ledger, evidence, **kwargs)


@pytest.mark.parametrize("alias", _INVALID_NUMERIC_ALIASES)
def test_matched_budget_comparison_constructor_rejects_noncanonical_or_nonfinite_score_delta(
    alias: object,
) -> None:
    with pytest.raises(ValueError, match=r"score_delta.*(exact numeric|finite)"):
        _comparison(score_delta=alias)


@pytest.mark.parametrize("alias", _INVALID_NUMERIC_ALIASES)
def test_matched_budget_comparison_restore_rejects_score_delta_alias_or_nonfinite_laundering(
    alias: object,
) -> None:
    state = _comparison_state()
    state["score_delta"] = alias

    with pytest.raises(ValueError, match=r"score_delta.*(exact numeric|finite)"):
        MatchedBudgetComparison.from_state(state)


@pytest.mark.parametrize("alias", _INVALID_NUMERIC_ALIASES)
def test_ablation_constructor_rejects_noncanonical_or_nonfinite_score_delta(
    alias: object,
) -> None:
    with pytest.raises(ValueError, match=r"score_delta.*(exact numeric|finite)"):
        _ablation(score_delta=alias)


@pytest.mark.parametrize("alias", _INVALID_NUMERIC_ALIASES)
def test_ablation_restore_rejects_score_delta_alias_or_nonfinite_laundering(
    alias: object,
) -> None:
    state = _ablation_state()
    state["score_delta"] = alias

    with pytest.raises(ValueError, match=r"score_delta.*(exact numeric|finite)"):
        AblationAssessment.from_state(state)


def test_evaluation_numeric_authority_normalizes_exact_builtin_ints_to_float() -> None:
    observation = _observation()
    score_row = replace(observation, score=1)
    energy_row = replace(observation, energy_joules=1)
    comparison = _comparison(score_delta=1)
    ablation = _ablation(score_delta=1)

    assert type(score_row.score) is float
    assert score_row.score == 1.0
    assert type(energy_row.energy_joules) is float
    assert energy_row.energy_joules == 1.0
    assert type(comparison.score_delta) is float
    assert comparison.score_delta == 1.0
    assert type(ablation.score_delta) is float
    assert ablation.score_delta == 1.0


def test_evaluation_observation_preserves_optional_energy_none() -> None:
    ledger, evidence = _ledger()
    row = _record(ledger, evidence, energy_joules=None)

    assert row.energy_joules is None
    restored = type(row).from_state(row.to_state())
    assert restored.energy_joules is None


def test_evaluation_numeric_authority_preserves_canonical_finite_round_trip() -> None:
    observation = _observation()
    restored_observation = type(observation).from_state(observation.to_state())
    assert restored_observation == observation
    assert type(restored_observation.score) is float
    assert type(restored_observation.energy_joules) is float
    assert math.isfinite(restored_observation.score)
    assert math.isfinite(restored_observation.energy_joules)

    comparison_state = _comparison_state()
    restored_comparison = MatchedBudgetComparison.from_state(comparison_state)
    assert restored_comparison.to_state() == comparison_state
    assert type(restored_comparison.score_delta) is float
    assert math.isfinite(restored_comparison.score_delta)

    ablation_state = _ablation_state()
    restored_ablation = AblationAssessment.from_state(ablation_state)
    assert restored_ablation.to_state() == ablation_state
    assert type(restored_ablation.score_delta) is float
    assert math.isfinite(restored_ablation.score_delta)
