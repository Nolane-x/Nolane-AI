from __future__ import annotations

import pytest

from benchmarks.kfigg.r267_1_genuine_three_probe import run_benchmark
from research.r267_1_external_cyclic_dot_transfer import run_external_transfer


def _assert_case(case: dict[str, object]) -> None:
    assert case['passed'] is True
    assert case['selected_roles'] == ['a', 'b', 'c']
    assert case['semantic_profile_count'] == 3
    assert case['all_three_probes_used'] is True
    assert case['no_smuggling'] is True
    assert case['all_singleton_ablations_fail'] is True
    assert case['all_pair_ablations_fail'] is True
    assert case['singleton_collision_certificates'] == 3
    assert case['pair_collision_certificates'] == 3
    assert case['probe_validation_cases'] == 18
    assert case['probe_validation_exact'] == 18
    assert case['terminal_probe_validation_cases'] == 18
    assert case['terminal_probe_validation_exact'] == 18
    assert case['final_validation_cases'] == 6
    assert case['final_validation_exact'] == 6
    assert case['heldout_cases'] == 6
    assert case['heldout_exact'] == 6
    assert case['oracle_accounting_exact'] is True
    assert case['oracle_calls_learning_terminal'] > 0
    assert case['oracle_calls_collision_certificates'] == 72
    assert case['oracle_calls_heldout'] == 6
    assert case['oracle_calls_total'] == (
        case['oracle_calls_learning_terminal']
        + case['oracle_calls_collision_certificates']
        + case['oracle_calls_heldout']
    )
    assert case['false_accepts'] == 0
    assert case['trainable_parameter_count'] == 0


def test_authored_r267_1_replacement_evidence_is_exact_and_invariant() -> None:
    result = run_benchmark()
    assert result['milestone'] == 'R2.67.1'
    assert result['capability'] == 'genuine-three-probe-causal-necessity'
    assert result['all_gates_pass'] is True
    assert result['semantic_profile_invariant'] is True
    assert result['oracle_accounting_exact'] is True
    assert result['false_accepts'] == 0
    assert result['trainable_parameter_count'] == 0
    for key in ('base', 'renamed', 'permuted'):
        _assert_case(result[key])
    assert result['oracle_calls_total'] == sum(
        int(result[key]['oracle_calls_total'])
        for key in ('base', 'renamed', 'permuted')
    )


def test_pinned_numpy_cyclic_dot_transfer_is_io_only_and_exact() -> None:
    np = pytest.importorskip('numpy')
    assert np.__version__ == '2.4.6'
    result = run_external_transfer(
        np.dot,
        source_id='numpy:numpy.dot',
        source_version=np.__version__,
    )
    assert result['milestone'] == 'R2.67.1'
    assert result['capability'] == 'genuine-three-probe-causal-necessity'
    assert result['source_id'] == 'numpy:numpy.dot'
    assert result['source_version'] == '2.4.6'
    assert result['source_exposure'] == 'io_only'
    assert result['host_selected_intervention'] is False
    assert result['passed'] is True
    assert result['selected_roles'] == ['a', 'b', 'c']
    assert result['semantic_profile_count'] == 3
    assert result['all_three_probes_used'] is True
    assert result['all_singleton_ablations_fail'] is True
    assert result['all_pair_ablations_fail'] is True
    assert result['singleton_collision_certificates'] == 3
    assert result['pair_collision_certificates'] == 3
    assert result['probe_validation_cases'] == 18
    assert result['probe_validation_exact'] == 18
    assert result['terminal_probe_validation_cases'] == 18
    assert result['terminal_probe_validation_exact'] == 18
    assert result['final_validation_cases'] == 6
    assert result['final_validation_exact'] == 6
    assert result['challenge_cases'] == 6
    assert result['challenge_exact'] == 6
    assert result['heldout_cases'] == 6
    assert result['heldout_exact'] == 6
    assert result['oracle_accounting_exact'] is True
    assert result['oracle_calls_learning_terminal'] > 0
    assert result['oracle_calls_collision_certificates'] == 72
    assert result['oracle_calls_challenge'] == 6
    assert result['oracle_calls_heldout'] == 6
    assert result['oracle_calls_total'] == (
        result['oracle_calls_learning_terminal']
        + result['oracle_calls_collision_certificates']
        + result['oracle_calls_challenge']
        + result['oracle_calls_heldout']
    )
    assert result['false_accepts'] == 0
    assert result['trainable_parameter_count'] == 0
