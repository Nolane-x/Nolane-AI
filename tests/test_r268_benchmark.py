from benchmarks.kfigg.r268_cross_task_causal_transfer import run_benchmark


def test_r268_authored_cross_task_transfer_gate():
    result = run_benchmark()

    assert result['milestone'] == 'R2.68'
    assert result['capability'] == 'cross-task-causal-program-transfer'
    assert result['candidate_budget_unit'] == 'proof_distinct_hypotheses'
    assert result['all_gates_pass'] is True
    assert result['positive_transfer_cases'] == 3
    assert result['positive_transfer_exact'] == 3
    assert result['negative_transfer_cases'] == 2
    assert result['negative_transfer_abstained'] == 2
    assert result['transfer_vs_tight_scratch_same_candidate_budget'] is True
    assert result['tight_scratch_exact'] == 1
    assert result['transfer_advantage_over_tight_scratch'] == 2
    assert result['roomy_scratch_exact'] == 3
    assert result['diagnostic_order_invariance'] is True
    assert result['false_accepts'] == 0
    assert result['trainable_parameter_count'] == 0
