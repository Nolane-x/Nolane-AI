from benchmarks.kfigg.r256_autonomous_operator_invention import run_benchmark


def test_r256_autonomous_operator_invention_benchmark():
    result = run_benchmark()
    assert result['episodes'] >= 8
    assert result['exact'] == result['episodes']
    assert result['false_accepts'] == 0
    assert result['r255_no_invention_baseline_exact'] == 0
    assert result['episodes_with_cegis_refinement'] >= 1
    assert result['episodes_with_promotion'] == result['episodes']
    assert result['episodes_with_live_exact'] == result['episodes']
    assert result['episodes_with_transactional_rollback'] >= 1
    assert result['max_search_evaluations'] > 0
    assert result['trainable_parameter_count'] == 0
