from __future__ import annotations

from benchmarks.kfigg.r261_expansion_proof_audit import run_expansion_novelty_audit


def test_r261_all_authored_expansion_repairs_have_valid_novelty_proofs() -> None:
    result = run_expansion_novelty_audit()
    summary = result['summary']

    assert result['all_gates_pass'] is True
    assert summary['episodes'] == 6
    assert summary['valid_novelty_proofs'] == 6
    assert summary['initially_absent'] == 6
    assert summary['present_in_generated_evidence'] == 6
    assert summary['mutation_recorded'] == 6
    assert summary['unique_proof_digests'] == 6
    assert summary['false_proofs'] == 0
    assert result['trainable_parameter_count'] == 0
