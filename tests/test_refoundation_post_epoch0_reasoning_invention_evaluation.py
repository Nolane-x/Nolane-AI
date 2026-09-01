from __future__ import annotations

import importlib
import math
from copy import deepcopy

import pytest


def _native():
    return importlib.import_module("nolane.external_core.reasoning_evaluation")


def _budget(native):
    return native.ClosedLoopBudget(
        regime_id="regime:c7:heldout",
        regime_digest="regime-digest:c7:heldout",
        budget_digest="budget-digest:c7:heldout",
        max_discovery_evidence=4,
        max_candidates=3,
        max_experiments=2,
        max_oracle_calls=6,
        max_verification_cost=10.0,
    )


def _case(
    native,
    *,
    benchmark_case_id: str,
    expected,
    observed,
    challenge_id: str | None = "challenge:c7",
    independent_support_ids=("experiment:c7",),
    discovery_evidence_count: int = 2,
    candidate_count: int = 2,
    experiment_count: int = 1,
    oracle_calls: int = 3,
    verification_cost: float = 2.0,
    information_gain: float = 2.0,
    transfer_trial_count: int = 0,
    transfer_trial_passes: int = 0,
    robustness_trial_count: int = 1,
    robustness_trial_passes: int = 1,
    regression_count: int = 0,
):
    return native.ClosedLoopCase(
        benchmark_case_id=benchmark_case_id,
        reasoning_receipt_id=f"reasoning-receipt:{benchmark_case_id}",
        hypothesis_ids=(f"hypothesis:{benchmark_case_id}",),
        challenge_id=challenge_id,
        independent_support_ids=independent_support_ids,
        capability_gap_ids=(f"capability-gap:{benchmark_case_id}",),
        transfer_intent_ids=(f"transfer-intent:{benchmark_case_id}",),
        expected_decision=expected,
        observed_decision=observed,
        discovery_evidence_count=discovery_evidence_count,
        candidate_count=candidate_count,
        experiment_count=experiment_count,
        oracle_calls=oracle_calls,
        verification_cost=verification_cost,
        information_gain=information_gain,
        transfer_trial_count=transfer_trial_count,
        transfer_trial_passes=transfer_trial_passes,
        robustness_trial_count=robustness_trial_count,
        robustness_trial_passes=robustness_trial_passes,
        regression_count=regression_count,
        reproduced_evidence_ids=(f"evidence:reproduced:{benchmark_case_id}",),
    )


def test_c7_declares_stateless_reasoning_evaluation_revision() -> None:
    native = _native()
    assert native.COMPONENT_ID == "external.reasoning_invention"
    assert native.COMPONENT_VERSION == "0.0.4"
    assert native.SCHEMA_VERSION == "reasoning-invention-evaluation-v1"


def test_c7_budget_and_case_identity_are_canonical_and_tamper_evident() -> None:
    native = _native()
    budget = _budget(native)
    restored_budget = native.ClosedLoopBudget.from_state(budget.to_state())
    assert restored_budget == budget
    assert budget.budget_id.startswith("closed-loop-budget:")

    case = _case(
        native,
        benchmark_case_id="case-a",
        expected=native.EvaluationDecision.ACCEPTED,
        observed=native.EvaluationDecision.ACCEPTED,
        independent_support_ids=("causal:c7", "experiment:c7"),
    )
    reordered = _case(
        native,
        benchmark_case_id="case-a",
        expected=native.EvaluationDecision.ACCEPTED,
        observed=native.EvaluationDecision.ACCEPTED,
        independent_support_ids=("experiment:c7", "causal:c7"),
    )
    assert reordered.case_id == case.case_id
    assert reordered.to_state() == case.to_state()
    assert native.ClosedLoopCase.from_state(case.to_state()) == case

    tampered = deepcopy(case.to_state())
    tampered["case_id"] = "closed-loop-case:tampered"
    with pytest.raises(ValueError, match="identity|canonical"):
        native.ClosedLoopCase.from_state(tampered)


def test_c7_accepted_outcome_requires_independent_challenge_support() -> None:
    native = _native()
    with pytest.raises(ValueError, match="challenge|independent"):
        _case(
            native,
            benchmark_case_id="unsupported-accept",
            expected=native.EvaluationDecision.ACCEPTED,
            observed=native.EvaluationDecision.ACCEPTED,
            challenge_id=None,
            independent_support_ids=(),
        )


def test_c7_budget_enforcement_and_numeric_validation_fail_closed() -> None:
    native = _native()
    budget = _budget(native)
    over_budget = _case(
        native,
        benchmark_case_id="over-budget",
        expected=native.EvaluationDecision.REJECTED,
        observed=native.EvaluationDecision.REJECTED,
        oracle_calls=7,
    )
    with pytest.raises(ValueError, match="budget"):
        native.evaluate_closed_loop(budget, (over_budget,))

    for bad in (float("nan"), float("inf"), -1.0, True):
        with pytest.raises((TypeError, ValueError)):
            _case(
                native,
                benchmark_case_id=f"bad-cost-{bad!r}",
                expected=native.EvaluationDecision.REJECTED,
                observed=native.EvaluationDecision.REJECTED,
                verification_cost=bad,
            )

    with pytest.raises(ValueError, match="passes|trials"):
        _case(
            native,
            benchmark_case_id="impossible-transfer",
            expected=native.EvaluationDecision.REJECTED,
            observed=native.EvaluationDecision.REJECTED,
            transfer_trial_count=1,
            transfer_trial_passes=2,
        )


def test_c7_metrics_are_explicit_reproducible_and_non_scalarized() -> None:
    native = _native()
    budget = _budget(native)
    cases = (
        _case(
            native,
            benchmark_case_id="accepted-correct",
            expected=native.EvaluationDecision.ACCEPTED,
            observed=native.EvaluationDecision.ACCEPTED,
            verification_cost=2.0,
            information_gain=4.0,
            transfer_trial_count=2,
            transfer_trial_passes=2,
            robustness_trial_count=3,
            robustness_trial_passes=3,
        ),
        _case(
            native,
            benchmark_case_id="false-accept",
            expected=native.EvaluationDecision.REJECTED,
            observed=native.EvaluationDecision.ACCEPTED,
            verification_cost=2.0,
            information_gain=1.0,
            robustness_trial_count=2,
            robustness_trial_passes=1,
            regression_count=1,
        ),
        _case(
            native,
            benchmark_case_id="correct-abstain",
            expected=native.EvaluationDecision.ABSTAINED,
            observed=native.EvaluationDecision.ABSTAINED,
            challenge_id=None,
            independent_support_ids=(),
            verification_cost=1.0,
            information_gain=1.0,
            robustness_trial_count=1,
            robustness_trial_passes=1,
        ),
    )
    receipt = native.evaluate_closed_loop(budget, cases)
    metrics = receipt.metrics

    assert metrics.case_count == 3
    assert metrics.accepted_count == 2
    assert metrics.rejected_count == 0
    assert metrics.abstained_count == 1
    assert metrics.false_acceptance_count == 1
    assert metrics.false_acceptance_rate == pytest.approx(0.5)
    assert metrics.correct_abstention_count == 1
    assert metrics.abstention_precision == pytest.approx(1.0)
    assert metrics.abstention_recall == pytest.approx(1.0)
    assert metrics.information_efficiency == pytest.approx(6.0 / 5.0)
    assert metrics.generalization_rate == pytest.approx(1.0)
    assert metrics.robustness_rate == pytest.approx(5.0 / 6.0)
    assert metrics.regression_count == 1
    assert not hasattr(metrics, "overall_score")
    assert not hasattr(receipt, "promoted")
    assert not hasattr(receipt, "accepted")
    assert not hasattr(receipt, "reused")


def test_c7_evaluation_is_order_invariant_and_receipt_roundtrips() -> None:
    native = _native()
    budget = _budget(native)
    first = _case(
        native,
        benchmark_case_id="order-a",
        expected=native.EvaluationDecision.REJECTED,
        observed=native.EvaluationDecision.REJECTED,
    )
    second = _case(
        native,
        benchmark_case_id="order-b",
        expected=native.EvaluationDecision.ABSTAINED,
        observed=native.EvaluationDecision.ABSTAINED,
        challenge_id=None,
        independent_support_ids=(),
    )

    left = native.evaluate_closed_loop(budget, (first, second))
    right = native.evaluate_closed_loop(budget, (second, first))
    assert left.receipt_id == right.receipt_id
    assert left.to_state() == right.to_state()
    assert native.ReasoningInventionEvaluationReceipt.from_state(left.to_state()) == left

    tampered = deepcopy(left.to_state())
    tampered["metrics"]["regression_count"] += 1
    with pytest.raises(ValueError, match="identity|canonical|metrics"):
        native.ReasoningInventionEvaluationReceipt.from_state(tampered)


def test_c7_requires_reproduced_evidence_and_rejects_duplicate_cases() -> None:
    native = _native()
    budget = _budget(native)
    case = _case(
        native,
        benchmark_case_id="duplicate",
        expected=native.EvaluationDecision.REJECTED,
        observed=native.EvaluationDecision.REJECTED,
    )
    with pytest.raises(ValueError, match="duplicate"):
        native.evaluate_closed_loop(budget, (case, case))

    with pytest.raises(ValueError, match="evidence"):
        native.ClosedLoopCase(
            benchmark_case_id="no-evidence",
            reasoning_receipt_id="reasoning-receipt:no-evidence",
            hypothesis_ids=("hypothesis:no-evidence",),
            challenge_id=None,
            independent_support_ids=(),
            capability_gap_ids=(),
            transfer_intent_ids=(),
            expected_decision=native.EvaluationDecision.ABSTAINED,
            observed_decision=native.EvaluationDecision.ABSTAINED,
            discovery_evidence_count=1,
            candidate_count=1,
            experiment_count=0,
            oracle_calls=1,
            verification_cost=1.0,
            information_gain=0.0,
            transfer_trial_count=0,
            transfer_trial_passes=0,
            robustness_trial_count=0,
            robustness_trial_passes=0,
            regression_count=0,
            reproduced_evidence_ids=(),
        )


def test_c7_module_has_no_mutable_authority_backdoor() -> None:
    native = _native()
    source = __import__("inspect").getsource(native)
    for forbidden in (
        "CapabilityAcquisitionGovernor",
        "TransferMetaGovernor",
        "AssuranceControlPlane",
        "register_abstraction(",
        ".promote(",
        ".accept(",
    ):
        assert forbidden not in source
