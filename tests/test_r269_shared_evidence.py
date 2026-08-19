from __future__ import annotations

import math

import pytest

from cogcoder.r269_meta_learning_kernel import PublicTaskSignature, SharedObservationLedger


def _signature():
    return PublicTaskSignature(
        role_names=("x", "y"),
        numeric_domain="finite_numeric",
        allowed_binary_ops=("add", "sub", "mul"),
        query_space_digest="queries.v1",
        budget_contract="oracle<=8;candidate<=64",
    )


def test_shared_ledger_counts_one_physical_call_for_reused_diagnostic():
    calls = []
    ledger = SharedObservationLedger(_signature())

    def oracle(context):
        calls.append(dict(context))
        return context["x"] + context["y"]

    first, first_reused = ledger.observe(
        {"x": 2, "y": 3}, oracle, phase="diagnostic", provenance="transfer",
        transfer_info_score=2, scratch_info_score=2,
    )
    second, second_reused = ledger.observe(
        {"y": 3.0, "x": 2.0}, oracle, phase="diagnostic", provenance="scratch",
        transfer_info_score=0, scratch_info_score=2,
    )

    assert first == second
    assert first_reused is False
    assert second_reused is True
    assert ledger.physical_oracle_calls == 1
    assert len(calls) == 1


def test_terminal_cannot_reuse_diagnostic_semantic_query():
    calls = 0
    ledger = SharedObservationLedger(_signature())

    def oracle(context):
        nonlocal calls
        calls += 1
        return context["x"] + context["y"]

    ledger.observe(
        {"x": 1, "y": 4}, oracle, phase="diagnostic", provenance="shared",
        transfer_info_score=2, scratch_info_score=2,
    )
    with pytest.raises(ValueError, match="terminal"):
        ledger.observe(
            {"x": 1.0, "y": 4.0}, oracle, phase="terminal", provenance="shared",
            transfer_info_score=0, scratch_info_score=0,
        )
    assert calls == 1


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_oracle_output_fails_closed_and_is_counted_once(bad):
    ledger = SharedObservationLedger(_signature())
    row, reused = ledger.observe(
        {"x": 2, "y": 5}, lambda _: bad, phase="diagnostic", provenance="shared",
        transfer_info_score=1, scratch_info_score=1,
    )
    assert reused is False
    assert row.status == "invalid_oracle_output"
    assert row.observed is None
    assert ledger.physical_oracle_calls == 1


def test_oracle_exception_is_contained_as_invalid_evidence():
    ledger = SharedObservationLedger(_signature())

    def boom(_):
        raise RuntimeError("external failure")

    row, _ = ledger.observe(
        {"x": 2, "y": 5}, boom, phase="diagnostic", provenance="shared",
        transfer_info_score=1, scratch_info_score=1,
    )
    assert row.status == "oracle_error"
    assert ledger.physical_oracle_calls == 1
