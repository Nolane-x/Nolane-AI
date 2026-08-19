from __future__ import annotations

import numpy as np

from benchmarks.kfigg.r267_1_genuine_causal_necessity import run_benchmark
from research.r267_1_external_cyclic_dot_transfer import run_external_transfer


def test_fresh_authored_genuine_causal_necessity_evidence() -> None:
    result = run_benchmark()
    assert result['milestone'] == 'R2.67.1'
    assert result['all_gates_pass'] is True
    assert result['semantic_profile_invariant'] is True
    assert result['false_accepts'] == 0
    assert result['trainable_parameter_count'] == 0
    for key in ('base', 'renamed', 'permuted'):
        case = result[key]
        assert case['passed'] is True
        assert case['singleton_collision_certificates'] == [True, True, True]
        assert case['pair_collision_certificates'] == [True, True, True]
        assert case['probe_validation_cases'] == case['probe_validation_exact'] == 18
        assert case['terminal_probe_validation_cases'] == case['terminal_probe_validation_exact'] == 18
    assert result['triangle_min_representation_stress']['passed'] is True


def test_fresh_pinned_numpy_cyclic_dot_transfer() -> None:
    result = run_external_transfer(
        np.dot,
        source_id='numpy.dot',
        source_version=np.__version__,
    )
    assert np.__version__ == '2.4.6'
    assert result['passed'] is True
    assert result['source_exposure'] == 'io_only'
    assert result['adapter'] == 'dot([a,b,c],[b,c,a])'
    assert result['singleton_collision_certificates'] == [True, True, True]
    assert result['pair_collision_certificates'] == [True, True, True]
    assert result['probe_validation_cases'] == result['probe_validation_exact'] == 18
    assert result['terminal_probe_validation_cases'] == result['terminal_probe_validation_exact'] == 18
    assert result['challenge_exact'] == result['challenge_cases'] == 6
    assert result['heldout_exact'] == result['heldout_cases'] == 6
    assert result['false_accepts'] == 0
    assert result['trainable_parameter_count'] == 0
