from __future__ import annotations

from dataclasses import replace

from cogcoder.r247_executable_patch_cegis import PatchMacro, PatchTest
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_expansion_proof import (
    initial_version_space_digest,
    prove_expansion_novelty,
    repository_content_digest,
)
from cogcoder.r261_version_space_expansion import (
    expand_repository_candidates,
    solve_repository_patch_with_version_space_expansion,
)


def _candidate(candidate_id: str, expression: str) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(
        candidate_id,
        (),
        (('a.py', f'def f(x, y):\n    return {expression}\n'),),
        0,
        0,
    )


def _macro() -> PatchMacro:
    return PatchMacro('pm:floor-to-mod', 'binop', 'replace', 'FloorDiv', 'Mod', support=3)


def _accepted_case():
    floor = _candidate('seed:floor', 'x // y')
    subtract = _candidate('seed:subtract', 'x - y')
    initial = (floor, subtract)
    tests = (PatchTest('initial', (3, 2), 1),)
    probes = (RepositoryProbe((5, 2)),)
    verification = (
        RepositoryProbe((5, 2)),
        RepositoryProbe((7, 3)),
        RepositoryProbe((8, 3)),
        RepositoryProbe((11, 4)),
    )
    generated = expand_repository_candidates(
        (floor,), (_macro(),),
        max_generated_candidates=8,
        max_sites_per_macro=8,
    )
    receipt = solve_repository_patch_with_version_space_expansion(
        initial,
        tests,
        probes,
        lambda x, y: x % y,
        verification_inputs=verification,
        expansion_seeds=(floor,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_expansion_rounds=1,
        max_generated_candidates_per_round=8,
        max_sites_per_macro=8,
    )
    assert receipt.status == 'accept'
    assert receipt.candidate is not None
    return initial, generated, receipt


def test_repository_content_digest_ignores_caller_candidate_id() -> None:
    first = _candidate('caller:a', 'x // y')
    renamed = replace(first, candidate_id='caller:renamed')
    changed = _candidate('caller:a', 'x % y')

    assert repository_content_digest(first) == repository_content_digest(renamed)
    assert repository_content_digest(first) != repository_content_digest(changed)


def test_initial_space_digest_is_order_and_id_invariant() -> None:
    left = _candidate('a', 'x // y')
    right = _candidate('b', 'x - y')
    renamed_left = replace(left, candidate_id='renamed-left')
    renamed_right = replace(right, candidate_id='renamed-right')

    assert initial_version_space_digest((left, right)) == initial_version_space_digest((renamed_right, renamed_left))


def test_proof_certifies_accepted_candidate_was_generated_and_initially_absent() -> None:
    initial, generated, receipt = _accepted_case()

    proof = prove_expansion_novelty(initial, generated, receipt)

    assert proof.valid is True
    assert proof.accepted_candidate_initially_absent is True
    assert proof.accepted_candidate_in_generated_set is True
    assert proof.accepted_mutation_recorded_in_receipt is True
    assert proof.expansion_round_count == 1
    assert proof.accepted_candidate_digest == repository_content_digest(receipt.candidate)
    assert proof.initial_space_digest == initial_version_space_digest(initial)
    assert proof.proof_digest.startswith('r261proof:')


def test_proof_fails_closed_when_generated_evidence_is_missing() -> None:
    initial, _generated, receipt = _accepted_case()

    proof = prove_expansion_novelty(initial, (), receipt)

    assert proof.valid is False
    assert proof.accepted_candidate_initially_absent is True
    assert proof.accepted_candidate_in_generated_set is False
    assert proof.accepted_mutation_recorded_in_receipt is False


def test_proof_fails_closed_when_receipt_candidate_is_initial_content_under_new_id() -> None:
    initial, generated, receipt = _accepted_case()
    forged = replace(receipt, candidate=replace(initial[0], candidate_id='forged:new-id'))

    proof = prove_expansion_novelty(initial, generated, forged)

    assert proof.valid is False
    assert proof.accepted_candidate_initially_absent is False


def test_proof_digest_changes_when_evidence_changes() -> None:
    initial, generated, receipt = _accepted_case()
    proof = prove_expansion_novelty(initial, generated, receipt)
    proof_without_generated = prove_expansion_novelty(initial, (), receipt)

    assert proof.proof_digest != proof_without_generated.proof_digest
