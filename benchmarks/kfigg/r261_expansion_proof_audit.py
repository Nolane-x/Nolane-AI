from __future__ import annotations

from benchmarks.kfigg.r261_version_space_expansion_transfer import (
    HELDOUT_EPISODES,
    _callable,
    _candidate,
    _macro,
    _repository,
    _verification_inputs,
)
from cogcoder.r247_executable_patch_cegis import PatchTest
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_expansion_proof import prove_expansion_novelty
from cogcoder.r261_version_space_expansion import (
    expand_repository_candidates,
    solve_repository_patch_with_version_space_expansion,
)


def _audit_episode(seed: int) -> dict[str, object]:
    index = HELDOUT_EPISODES.index(seed)
    relay_count = 1 + (index % 3)
    coefficient = 7 + index * 2

    source = _repository(
        seed,
        relay_count=relay_count,
        coefficient=coefficient,
        target_op='//',
        decoy_op='//',
    )
    wrong = _repository(
        seed,
        relay_count=relay_count,
        coefficient=coefficient,
        target_op='//',
        decoy_op='%',
    )
    target = _repository(
        seed,
        relay_count=relay_count,
        coefficient=coefficient,
        target_op='%',
        decoy_op='//',
    )

    source_candidate = _candidate(f'proof:seed:{seed}', source)
    wrong_candidate = _candidate(f'proof:wrong:{seed}', wrong, edits=1)
    initial_candidates = (source_candidate, wrong_candidate)
    oracle = _callable(target)

    initial_args = (3, 2)
    initial_tests = (
        PatchTest(f'proof:initial:{seed}', initial_args, oracle(*initial_args)),
    )
    diagnostic = (RepositoryProbe((5, 2)),)
    verification = _verification_inputs()

    generated = expand_repository_candidates(
        (source_candidate,),
        (_macro(),),
        max_generated_candidates=8,
        max_sites_per_macro=8,
    )
    receipt = solve_repository_patch_with_version_space_expansion(
        initial_candidates,
        initial_tests,
        diagnostic,
        oracle,
        verification_inputs=verification,
        expansion_seeds=(source_candidate,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_expansion_rounds=1,
        max_generated_candidates_per_round=8,
        max_sites_per_macro=8,
    )
    proof = prove_expansion_novelty(initial_candidates, generated, receipt)

    return {
        'seed': seed,
        'proof_valid': proof.valid,
        'proof_reason': proof.reason,
        'proof_digest': proof.proof_digest,
        'initial_space_digest': proof.initial_space_digest,
        'accepted_candidate_digest': proof.accepted_candidate_digest,
        'accepted_candidate_initially_absent': proof.accepted_candidate_initially_absent,
        'accepted_candidate_in_generated_set': proof.accepted_candidate_in_generated_set,
        'accepted_mutation_recorded_in_receipt': proof.accepted_mutation_recorded_in_receipt,
        'accepted_mutation_id': proof.accepted_mutation_id,
        'expansion_round_count': proof.expansion_round_count,
        'generated_candidate_count': len(generated),
        'solver_status': receipt.status,
        'solver_reason': receipt.reason,
        'false_terminal_accepts': receipt.false_terminal_accepts,
        'verification_failures': receipt.verification_failures,
    }


def run_expansion_novelty_audit() -> dict[str, object]:
    rows = [_audit_episode(seed) for seed in HELDOUT_EPISODES]
    proof_digests = {str(row['proof_digest']) for row in rows}
    summary = {
        'episodes': len(rows),
        'valid_novelty_proofs': sum(bool(row['proof_valid']) for row in rows),
        'initially_absent': sum(bool(row['accepted_candidate_initially_absent']) for row in rows),
        'present_in_generated_evidence': sum(bool(row['accepted_candidate_in_generated_set']) for row in rows),
        'mutation_recorded': sum(bool(row['accepted_mutation_recorded_in_receipt']) for row in rows),
        'unique_proof_digests': len(proof_digests),
        'false_proofs': sum(not bool(row['proof_valid']) for row in rows),
        'false_terminal_accepts': sum(int(row['false_terminal_accepts']) for row in rows),
        'verification_failures': sum(int(row['verification_failures']) for row in rows),
    }
    gates = {
        'all_authored_repairs_have_valid_novelty_proof': summary['valid_novelty_proofs'] == len(rows),
        'all_accepted_content_absent_initially': summary['initially_absent'] == len(rows),
        'all_accepted_content_reconstructed_in_generated_evidence': summary['present_in_generated_evidence'] == len(rows),
        'all_accepted_mutations_recorded_by_solver': summary['mutation_recorded'] == len(rows),
        'proofs_episode_specific': summary['unique_proof_digests'] == len(rows),
        'zero_false_proofs': summary['false_proofs'] == 0,
        'zero_false_terminal_accepts': summary['false_terminal_accepts'] == 0,
        'zero_verification_failures': summary['verification_failures'] == 0,
        'zero_trainable_parameters': True,
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.61 Expansion Novelty Proof Audit',
        'capability': 'content-addressed-expansion-novelty-evidence',
        'claim_boundary': (
            'Independent content-addressed evidence that accepted authored R2.61 repairs are absent from the '
            'initial repository-content version space, reconstructible by the bounded target-output-free expander, '
            'and linked to mutation ids recorded in expansion receipts. This does not by itself establish open-ended '
            'candidate invention, temporal causality beyond the solver receipt, or general repository repair.'
        ),
        'heldout_episodes': list(HELDOUT_EPISODES),
        'rows': rows,
        'summary': summary,
        'gates': gates,
        'all_gates_pass': all(gates.values()),
        'trainable_parameter_count': 0,
    }


if __name__ == '__main__':
    import json

    print(json.dumps(run_expansion_novelty_audit(), indent=2, sort_keys=True))
