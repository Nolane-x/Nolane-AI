from __future__ import annotations

import pytest

from research.r267_external_dot_transfer import run_external_transfer


np = pytest.importorskip('numpy')


def test_r267_pinned_numpy_dot_io_only_transfer() -> None:
    result = run_external_transfer(
        np.dot,
        source_id='numpy.dot',
        source_version=str(np.__version__),
    )
    assert result['milestone'] == 'R2.67'
    assert result['capability'] == 'verified-three-probe-causal-composition'
    assert result['source_id'] == 'numpy.dot'
    assert result['source_exposure'] == 'io_only'
    assert result['host_selected_intervention'] is False
    assert result['passed'] is True
    assert result['semantic_profile_count'] == 3
    assert result['all_three_probes_used'] is True
    assert result['all_singleton_ablations_fail'] is True
    assert result['all_pair_ablations_fail'] is True
    assert result['probe_validation_exact'] == result['probe_validation_cases'] * 3
    assert result['terminal_probe_validation_exact'] == result['terminal_probe_validation_cases']
    assert result['final_validation_exact'] == result['final_validation_cases']
    assert result['challenge_exact'] == result['challenge_cases'] == 6
    assert result['heldout_exact'] == result['heldout_cases'] == 6
    assert result['false_accepts'] == 0
    assert result['trainable_parameter_count'] == 0
