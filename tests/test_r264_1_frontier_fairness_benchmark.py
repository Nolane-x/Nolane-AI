from benchmarks.kfigg.r264_1_frontier_fairness import run_benchmark


def test_r264_1_frontier_fairness_family() -> None:
    result = run_benchmark()
    assert result["all_gates_pass"] is True
    summary = result["summary"]
    assert summary["episodes"] == 6
    assert summary["accepted_r264_tight_abstains"] == 6
    assert summary["hotfix_tight_exact"] == 6
    assert summary["hotfix_roomy_exact"] == 6
    assert summary["fallback_exact"] == 6
    assert summary["tight_one_generated_each"] == 6
    assert summary["tight_one_admitted_each"] == 6
    assert summary["fallback_one_generated_each"] == 6
    assert summary["fallback_one_admitted_each"] == 6
    assert summary["target_output_leakage"] is False
    assert summary["false_terminal_accepts"] == 0
    assert summary["verification_failures"] == 0
    assert summary["trainable_parameter_count"] == 0
