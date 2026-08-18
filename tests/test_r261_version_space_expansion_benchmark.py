from __future__ import annotations

from benchmarks.kfigg.r261_version_space_expansion_transfer import run_frozen_heldout


def test_r261_frozen_multifile_causal_gate() -> None:
    result = run_frozen_heldout()
    summary = result['summary']

    assert result['all_gates_pass'] is True
    assert summary['episodes'] == 6
    assert summary['r260_out_of_space_abstains'] == 6
    assert summary['r261_exact'] == 6
    assert summary['correct_candidate_initially_absent'] == 6
    assert summary['repairs_generated_after_counterexample'] == 6
    assert summary['expansion_rounds'] == 6
    assert summary['false_terminal_accepts'] == 0
    assert summary['min_file_count'] >= 3
    assert summary['min_verification_cases'] >= 40
    assert summary['candidate_order_invariant'] is True
    assert summary['generation_uses_target_outputs'] is False
    assert result['trainable_parameter_count'] == 0
