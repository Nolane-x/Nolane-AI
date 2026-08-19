from benchmarks.kfigg.r268_cross_task_causal_transfer import run_benchmark


def test_r268_transfer_advantage_requires_source_prior():
    result = run_benchmark()

    assert result['positive_transfer_exact'] == result['positive_transfer_cases'] == 3
    assert result['source_prior_ablation_cases'] == 3
    assert result['source_prior_ablation_exact'] == 0
    assert result['source_prior_ablation_same_candidate_budget'] is True
    assert result['all_gates_pass'] is True
