from benchmarks.kfigg.r259_dual_intervention_portfolio import run_benchmark
from research.r259_external_portfolio_transfer import run_external_transfer


def test_r259_frozen_portfolio_benchmark_exercises_both_engines_and_consensus():
    result = run_benchmark()
    assert result['milestone'] == 'R2.59'
    assert result['capability'] == 'dual-intervention-portfolio'
    assert result['configurations'] >= 4
    assert result['passed'] == result['configurations']
    assert result['false_accepts'] == 0
    assert result['exposure_selected'] >= 2
    assert result['positional_selected'] >= 1
    assert result['consensus_selected'] >= 1
    assert result['rename_invariant'] is True
    assert result['max_oracle_calls'] <= 1400
    assert result['trainable_parameter_count'] == 0


def test_r259_external_transfer_requires_robust_cross_mechanism_evidence():
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
    assert result['selected_method'] == 'consensus'
    assert result['exposure_passed'] is True
    assert result['positional_passed'] is True
    assert result['methods_agree'] is True
    assert result['challenge_exact'] == result['challenge_cases'] == 8
    assert result['heldout_exact'] == result['heldout_cases'] == 24
    assert result['trainable_parameter_count'] == 0
