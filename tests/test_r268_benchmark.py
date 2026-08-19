from benchmarks.kfigg.r268_adaptive_causal_basis import run_benchmark

def test_r268_mixed_cardinality_benchmark_is_deterministic_and_exact() -> None:
    first=run_benchmark();second=run_benchmark()
    assert first==second
    assert first['all_gates_pass'] is True
    assert first['selected_basis_sizes']==[1,2,3,4]
    assert first['false_accepts']==0
    assert first['trainable_parameter_count']==0
    assert first['cases'][0]['globally_minimal'] is False
    assert all(case['globally_minimal'] for case in first['cases'][1:])
