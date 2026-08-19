from benchmarks.kfigg.r268_adaptive_causal_basis import run_benchmark

def test_r268_mixed_cardinality_benchmark_is_deterministic_and_exact() -> None:
    first=run_benchmark();second=run_benchmark()
    assert first==second
    assert first['all_gates_pass'] is True
    assert first['selected_basis_sizes']==[0,2,3,4]
    assert first['adaptive_selected_basis_sizes']==[2,3,4]
    assert first['one_probe_nuisance_rejected'] is True
    assert first['false_accepts']==0
    assert first['trainable_parameter_count']==0
    assert first['cases'][0]['passed'] is False
    assert first['cases'][0]['globally_minimal'] is False
    assert all(case['globally_minimal'] for case in first['cases'][1:])


def test_r268_benchmark_freezes_complete_lower_basis_ledger() -> None:
    result=run_benchmark()
    assert [case['lower_basis_count'] for case in result['cases']]==[0,2,6,14]
    assert [case['lower_basis_certified'] for case in result['cases']]==[0,2,6,14]
    assert [case['lower_basis_inconclusive'] for case in result['cases']]==[0,0,0,0]
    assert [case['lower_basis_certificate_count'] for case in result['cases']]==[0,2,6,14]
    assert [case['proof_ledger_complete'] for case in result['cases']]==[False,True,True,True]
    assert result['replayable_global_ledgers'] is True
    assert result['complete_minimality_ledgers'] is True


def test_r268_benchmark_freezes_complete_selected_basis_proper_subset_ledger() -> None:
    result=run_benchmark()
    assert [case['necessity_certificate_count'] for case in result['cases']]==[0,2,6,14]
    assert result['complete_local_ledgers'] is True
    for case in result['cases'][1:]:
        k=case['selected_basis_size']
        assert case['necessity_certificate_count']==(1<<k)-2
        assert all(cert['proof_kind']=='public_target_collision' for cert in case['necessity_certificates'])
        assert all(cert['subset_cardinality']<k for cert in case['necessity_certificates'])
