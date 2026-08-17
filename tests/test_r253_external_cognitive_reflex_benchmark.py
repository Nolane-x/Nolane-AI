from benchmarks.kfigg.r253_external_cognitive_reflex import run_frozen_heldout


def test_r253_frozen_external_cognitive_reflex():
    result = run_frozen_heldout(); s = result['summary']
    assert result['all_gates_pass'] is True
    assert s['episodes'] >= 8
    assert s['exact'] == s['episodes']
    assert s['false_accepts'] == 0
    assert s['no_reflex_exact'] == 0
    assert s['self_confidence_only_exact'] == 0
    assert s['retrieve_once_exact'] == 0
    assert s['high_confidence_objective_deficits'] >= s['episodes']
    assert s['interleaved_procedure_retrievals'] >= 2 * s['episodes']
    assert s['episodes_with_new_midtrajectory_deficit'] == s['episodes']
    assert s['distinct_deficit_kinds'] >= 8
    assert s['counterexample_repeats_avoided'] >= 1
    assert s['unsafe_procedure_executions'] == 0
    assert s['provenance_failures'] == 0
    assert s['max_procedure_steps'] <= 3
