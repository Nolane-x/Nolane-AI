from benchmarks.kfigg.r258_autonomous_intervention_discovery import merge_benchmark_parts, run_benchmark_part


def test_r258_rename_search_and_replay_part():
    part = run_benchmark_part('rename')
    assert part['part'] == 'rename'
    assert part['discovered'] == 2
    assert part['no_seed_failures'] == 2
    assert part['seeded_successes'] == 2
    assert part['probe_validation_exact'] == part['probe_validation_cases'] == 8
    assert part['position_rename_invariant'] is True
    assert part['wrong_role_false_accepts'] == 0
    assert part['noncausal_candidates_rejected'] > 0


def test_r258_reordered_full_search_part():
    part = run_benchmark_part('reordered')
    assert part['part'] == 'reordered'
    assert part['discovered'] == 1
    assert part['no_seed_failures'] == 1
    assert part['seeded_successes'] == 1
    assert part['probe_validation_exact'] == part['probe_validation_cases'] == 4
    assert part['argument_permutation_tracks_roles'] is True
    assert part['wrong_role_false_accepts'] == 0
    assert part['noncausal_candidates_rejected'] > 0


def test_r258_merge_contract_is_pure_and_preserves_strict_claim_boundary():
    rename = {
        'part': 'rename', 'discovered': 2, 'no_seed_failures': 2, 'seeded_successes': 2,
        'probe_validation_exact': 8, 'probe_validation_cases': 8, 'position_rename_invariant': True,
        'wrong_role_false_accepts': 0, 'noncausal_candidates_rejected': 3,
        'selected_intervention_ids': ['a', 'a'], 'selected_position_sets': [[3, 4], [3, 4]], 'oracle_calls': 209,
        'synthesis_candidates_considered': 100,
    }
    reordered = {
        'part': 'reordered', 'discovered': 1, 'no_seed_failures': 1, 'seeded_successes': 1,
        'probe_validation_exact': 4, 'probe_validation_cases': 4, 'argument_permutation_tracks_roles': True,
        'wrong_role_false_accepts': 0, 'noncausal_candidates_rejected': 2,
        'selected_intervention_ids': ['b'], 'selected_position_sets': [[0, 2]], 'oracle_calls': 201,
        'synthesis_candidates_considered': 200,
    }
    result = merge_benchmark_parts(rename, reordered)
    assert result['milestone'] == 'R2.58'
    assert result['capability'] == 'autonomous-bounded-intervention-discovery'
    assert result['configurations'] == 3
    assert result['discovered'] == 3
    assert result['probe_validation_exact'] == result['probe_validation_cases'] == 12
    assert result['wrong_role_false_accepts'] == 0
    assert result['oracle_calls'] == 410
    assert result['synthesis_candidates_considered'] > 0
    assert result['trainable_parameter_count'] == 0
    assert 'not open-ended' in result['claim_boundary']
