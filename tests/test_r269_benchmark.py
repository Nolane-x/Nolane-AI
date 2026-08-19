from __future__ import annotations

from benchmarks.kfigg.r269_meta_learning import run_benchmark


def test_r269_benchmark_reports_verified_matched_meta_learning_evidence():
    result = run_benchmark()

    required = {
        "milestone",
        "capability",
        "accepted_parent_sha",
        "source_basis_sizes",
        "source_portable_digests",
        "hard_source_verified",
        "positive_targets",
        "positive_transfer_solved",
        "tight_cold_scratch_solved",
        "roomy_scratch_solved",
        "source_prior_ablation_solved",
        "shuffled_prior_solved",
        "source_prior_ablation_advantage_removed_fraction",
        "median_transfer_diagnostic_calls",
        "median_cold_solved_diagnostic_calls",
        "median_transfer_search_work",
        "median_tight_scratch_search_work",
        "negative_targets",
        "negative_transfer_false_accepts",
        "continued_scratch_correctness_preserved",
        "max_negative_transfer_diagnostic_regret",
        "false_accepts",
        "authored_gate_pass",
        "semantic_result_digest",
        "positive_cases",
        "negative_cases",
        "trainable_parameter_count",
    }
    assert required.issubset(result)
    assert result["milestone"] == "R2.69"
    assert result["accepted_parent_sha"] == "fda7f502185266fedb00886d5786c6d28cc0e0eb"
    assert result["source_basis_sizes"] == [2, 3, 4]
    assert len(result["source_portable_digests"]) == 3
    assert len(set(result["source_portable_digests"])) == 3
    assert result["hard_source_verified"] is True
    assert result["trainable_parameter_count"] == 0

    assert result["positive_targets"] >= 18
    assert len(result["positive_cases"]) == result["positive_targets"]
    assert result["positive_transfer_solved"] >= 17
    assert result["tight_cold_scratch_solved"] <= 12
    assert result["roomy_scratch_solved"] >= 17
    assert result["median_transfer_diagnostic_calls"] <= 0.70 * result["median_cold_solved_diagnostic_calls"]
    assert result["median_transfer_search_work"] <= 0.50 * result["median_tight_scratch_search_work"]
    assert result["source_prior_ablation_advantage_removed_fraction"] >= 0.80
    assert result["shuffled_prior_solved"] < result["positive_transfer_solved"]

    assert result["negative_targets"] == 12
    assert len(result["negative_cases"]) == result["negative_targets"]
    assert result["negative_transfer_false_accepts"] == 0
    assert result["continued_scratch_correctness_preserved"] is True
    assert result["max_negative_transfer_diagnostic_regret"] <= 1
    assert result["false_accepts"] == 0
    assert result["authored_gate_pass"] is True


def test_r269_benchmark_is_semantically_deterministic_within_process():
    first = run_benchmark()
    second = run_benchmark()
    assert first == second
    assert first["semantic_result_digest"] == second["semantic_result_digest"]
