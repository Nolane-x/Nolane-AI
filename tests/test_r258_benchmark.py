from benchmarks.kfigg.r258_active_probe_discovery import run_benchmark
from research.r258_external_active_probe_transfer import run_external_transfer


def test_r258_frozen_authored_benchmark_requires_active_probe_causal_gain():
    result = run_benchmark()
    assert result['milestone'] == 'R2.58'
    assert result['capability'] == 'active-probe-subgoal-discovery'
    assert result['episodes'] >= 6
    assert result['r257_harness_free_exact'] == 0
    assert result['r258_active_exact'] == result['episodes']
    assert result['false_accepts'] == 0
    assert result['renaming_invariance'] is True
    assert result['max_oracle_calls'] <= 120
    assert result['max_interventions_considered'] <= 12
    assert result['trainable_parameter_count'] == 0


def test_r258_external_harness_has_no_manual_probe_rows_or_field_hints():
    def linearstep(x, a, b, fa, fb):
        t = min(max((x - a) / (b - a), 0.0), 1.0)
        return fa + t * (fb - fa)

    result = run_external_transfer(
        linearstep,
        source_id='synthetic-control:linearstep',
        source_commit='local-test',
    )
    assert result['passed'] is True
    assert result['source_exposure'] == 'io_only'
    assert result['manual_probe_rows'] == 0
    assert result['probe_field_hints'] == 0
    assert result['harness_free_base_passed'] is False
    assert result['active_probe_passed'] is True
    assert result['challenge_exact'] == result['challenge_cases'] == 8
    assert result['heldout_exact'] == result['heldout_cases'] == 24
    assert result['trainable_parameter_count'] == 0
