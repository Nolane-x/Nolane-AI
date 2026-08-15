import json
from pathlib import Path

from scripts.measure_r29_patch_search import measure_r29_patch_search


def test_r29_measurement_satisfies_locked_schema_and_claim_boundary():
    lock = json.loads(Path('research/R2_9_PRE_DEV_LOCK.json').read_text())
    result = measure_r29_patch_search()

    assert result['cases'] == lock['protocol']['case_count']
    assert result['verified_solves'] >= lock['acceptance']['verified_solves_min']
    assert result['false_terminal_accepts'] <= lock['acceptance']['false_terminal_accepts_max']
    assert result['duplicate_evaluator_calls'] <= lock['acceptance']['duplicate_evaluator_calls_max']
    assert result['rename_invariant_cases'] >= lock['acceptance']['rename_invariant_cases_min']
    assert result['max_evaluator_calls_observed'] <= lock['acceptance']['max_evaluator_calls_observed_max']
    assert result['new_r29_neural_parameters'] == 0
    assert result['candidate_effective_parameters'] == lock['candidate_parameter_ceiling']
    assert result['external_coding_claim_allowed'] is False
    assert result['agi_claim_allowed'] is False
    assert result['phase_a_gate_pass'] is True
