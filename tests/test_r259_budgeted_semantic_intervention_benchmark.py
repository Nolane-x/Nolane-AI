from __future__ import annotations

from benchmarks.kfigg.r259_budgeted_semantic_intervention_index import run_benchmark


def test_r259_frozen_budgeted_semantic_intervention_gate():
    result = run_benchmark()
    assert result['milestone'] == 'R2.59'
    assert result['configurations'] == result['discovered'] == 3
    assert result['no_seed_failures'] == result['seeded_successes'] == 3
    assert result['probe_validation_exact'] == result['probe_validation_cases'] == 12
    assert result['position_rename_invariant'] is True
    assert result['argument_permutation_tracks_roles'] is True
    assert result['wrong_role_false_accepts'] == 0
    assert result['derived_anchor_values'] == [0.0, 1.0]
    assert result['global_budget_respected'] is True
    assert result['max_total_synthesis_candidates_per_full_search'] == 15000
    assert result['r259_synthesis_candidates_considered'] <= 30000
    assert result['r258_frozen_synthesis_candidates'] == 261169
    assert result['synthesis_reduction_ratio'] >= 8.0
    assert result['trainable_parameter_count'] == 0


def test_r259_benchmark_preserves_strict_bounded_claim():
    result = run_benchmark()
    claim = result['claim_boundary'].lower()
    assert 'budgeted' in claim
    assert 'not' in claim
    assert 'open-ended' in claim
