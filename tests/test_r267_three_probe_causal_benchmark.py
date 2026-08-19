from __future__ import annotations

from benchmarks.kfigg.r267_three_probe_causal_composition import run_benchmark


def test_r267_authored_three_probe_benchmark_passes_all_gates() -> None:
    result = run_benchmark()
    assert result['milestone'] == 'R2.67'
    assert result['capability'] == 'verified-three-probe-causal-composition'
    assert result['all_gates_pass'] is True
    assert result['semantic_profile_invariant'] is True
    assert result['false_accepts'] == 0
    assert result['trainable_parameter_count'] == 0
    for case_name in ('base', 'renamed', 'permuted'):
        case = result[case_name]
        assert case['passed'] is True
        assert case['semantic_profile_count'] == 3
        assert case['all_three_probes_used'] is True
        assert case['no_smuggling'] is True
        assert case['all_singleton_ablations_fail'] is True
        assert case['all_pair_ablations_fail'] is True
        assert case['probe_validation_exact'] == case['probe_validation_cases'] * 3
        assert case['terminal_probe_validation_exact'] == case['terminal_probe_validation_cases']
        assert case['final_validation_exact'] == case['final_validation_cases']
        assert case['heldout_exact'] == case['heldout_cases']
        assert case['oracle_calls_total'] > case['oracle_calls_learning']


def test_r267_authored_benchmark_is_deterministic() -> None:
    assert run_benchmark() == run_benchmark()
