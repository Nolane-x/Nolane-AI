import json
from pathlib import Path


def test_r214_result_matches_frozen_gate_and_is_accepted_without_parameter_growth():
    root = Path(__file__).resolve().parents[1]
    lock = json.loads((root / 'research' / 'R2_14_PRE_HELDOUT_LOCK.json').read_text())
    result = json.loads((root / 'research' / 'R2_14_PHASE_A_RESULT.json').read_text())
    assert result['lock_sha256'] == 'f1760126547b4ec88f524d7cc105df5e4efbb0051739c978504ee7b6225cc001'
    assert result['seed'] == lock['heldout']['seed']
    m = result['metrics']
    g = lock['gate']
    checks = {
        'main_active_accuracy': m['main_active_accuracy'] >= g['main_active_accuracy_min'],
        'gain_over_shortest': m['gain_over_shortest_consistent'] >= g['gain_over_shortest_consistent_min'],
        'gain_over_passive': m['gain_over_passive_fixed'] >= g['gain_over_passive_fixed_min'],
        'gain_over_random': m['gain_over_random_budgeted'] >= g['gain_over_random_budgeted_min'],
        'depth3_accuracy': m['depth3_active_accuracy'] >= g['depth3_active_accuracy_min'],
        'retention': m['retention_accuracy'] >= g['retention_accuracy_min'],
        'out_of_class_abstention': m['out_of_class_abstention'] >= g['out_of_class_abstention_min'],
        'permutation_invariance': m['identity_permutation_invariance'] >= g['identity_permutation_invariance_min'],
        'false_accepts': m['false_resolved_accepts'] <= g['false_resolved_accepts_max'],
        'oracle_budget': m['max_active_oracle_calls'] <= g['max_active_oracle_calls'],
    }
    assert all(checks.values())
    assert result['gate_checks'] == checks
    assert result['accepted'] is True
    assert result['new_neural_parameters'] == 0
    assert result['effective_neural_parameters'] == 79_450_489
    assert result['agi_engineering_readiness_before'] == 19.2
    assert result['agi_engineering_readiness_after'] == 20.0
    assert result['external_coding_claim'] is False
    assert result['agi_claim'] is False
