from __future__ import annotations

from benchmarks.kfigg.r269_external_numpy_transfer import run_external_transfer


def test_r269_external_numpy_transfer_is_io_only_matched_and_fail_closed():
    result = run_external_transfer()

    assert result["milestone"] == "R2.69"
    assert result["dependency"] == "numpy==2.4.6"
    assert result["source_verified"] is True
    assert result["source_basis_size"] == 2
    assert result["trainable_parameter_count"] == 0

    assert result["positive_targets"] >= 3
    assert result["transfer_solved"] == result["positive_targets"]
    assert result["roomy_scratch_solved"] == result["positive_targets"]
    assert result["transfer_total_diagnostic_calls"] < result["roomy_scratch_total_diagnostic_calls"]
    assert result["transfer_total_search_work"] < result["roomy_scratch_total_search_work"]
    assert result["tight_scratch_solved"] < result["transfer_solved"]
    assert result["source_prior_ablation_solved"] == result["tight_scratch_solved"]

    assert result["negative_target"] == "numpy.bitwise_xor"
    assert result["negative_transfer_false_accepts"] == 0
    assert result["negative_receipt_passed"] is False
    assert result["false_accepts"] == 0
    assert result["all_gates_pass"] is True


def test_r269_external_numpy_transfer_replays_deterministically():
    first = run_external_transfer()
    second = run_external_transfer()
    assert first == second
    assert first["semantic_result_digest"] == second["semantic_result_digest"]
