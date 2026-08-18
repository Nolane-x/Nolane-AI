from benchmarks.kfigg.r257_verified_vocabulary_growth import run_benchmark


def test_r257_frozen_vocabulary_growth_benchmark():
    result = run_benchmark()
    assert result['milestone'] == 'R2.57'
    assert result['learned_abstractions'] == 3
    assert result['all_positive_compression'] is True
    assert result['min_support_tasks'] >= 6
    assert result['heldout_episodes'] >= 6
    assert result['extended_exact'] == result['heldout_episodes']
    assert result['base_exact'] == 0
    assert result['false_accepts'] == 0
    assert result['bad_candidate_quarantined'] is True
    assert result['live_revocation_rollback'] is True
    assert result['trainable_parameter_count'] == 0
    assert len(result['abstraction_digests']) == 3
