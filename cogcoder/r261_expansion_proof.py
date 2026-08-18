from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Sequence

from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r261_version_space_expansion import ExpansionCandidate, VersionSpaceExpansionReceipt


def _sha256(prefix: str, payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    ).encode('utf-8')
    return prefix + hashlib.sha256(raw).hexdigest()


def repository_content_digest(candidate: RepositoryPatchCandidate) -> str:
    """Digest repository semantics without trusting caller-supplied candidate ids."""
    files = tuple(sorted((str(path), str(source)) for path, source in candidate.files))
    return _sha256('r261repo:', [[path, source] for path, source in files])


def initial_version_space_digest(candidates: Sequence[RepositoryPatchCandidate]) -> str:
    """Order/id-invariant digest of the unique repository contents in the initial space."""
    digests = tuple(sorted({repository_content_digest(candidate) for candidate in candidates}))
    return _sha256('r261space:', list(digests))


@dataclass(frozen=True, slots=True)
class ExpansionNoveltyProof:
    valid: bool
    initial_space_digest: str
    initial_candidate_digests: tuple[str, ...]
    accepted_candidate_digest: str | None
    generated_candidate_digests: tuple[str, ...]
    accepted_candidate_initially_absent: bool
    accepted_candidate_in_generated_set: bool
    accepted_mutation_id: str | None
    accepted_mutation_recorded_in_receipt: bool
    expansion_round_count: int
    proof_digest: str
    reason: str


def prove_expansion_novelty(
    initial_candidates: Sequence[RepositoryPatchCandidate],
    generated_candidates: Sequence[ExpansionCandidate],
    receipt: VersionSpaceExpansionReceipt,
) -> ExpansionNoveltyProof:
    """Independently prove that an accepted R2.61 repair is genuinely expansion-derived.

    The proof intentionally ignores caller candidate ids when determining novelty. It
    requires the accepted repository content to be absent from the initial space,
    present in independently supplied generated evidence, and linked to a mutation id
    recorded by the solver's expansion-round receipt.
    """
    initial_digests = tuple(sorted({repository_content_digest(candidate) for candidate in initial_candidates}))
    initial_space = initial_version_space_digest(initial_candidates)

    generated_by_digest: dict[str, list[ExpansionCandidate]] = {}
    for row in generated_candidates:
        digest = repository_content_digest(row.candidate)
        generated_by_digest.setdefault(digest, []).append(row)
    generated_digests = tuple(sorted(generated_by_digest))

    accepted = receipt.candidate
    accepted_digest = repository_content_digest(accepted) if accepted is not None else None
    initially_absent = accepted_digest is not None and accepted_digest not in set(initial_digests)
    in_generated = accepted_digest is not None and accepted_digest in generated_by_digest

    accepted_mutation_id: str | None = None
    if in_generated and accepted_digest is not None:
        accepted_mutation_id = min(
            row.mutation.mutation_id for row in generated_by_digest[accepted_digest]
        )

    recorded_mutation_ids = {
        mutation_id
        for expansion_round in receipt.expansion_rounds
        for mutation_id in expansion_round.mutation_ids
    }
    mutation_recorded = (
        accepted_mutation_id is not None
        and accepted_mutation_id in recorded_mutation_ids
    )

    valid = all((
        receipt.status == 'accept',
        receipt.exact is True,
        accepted is not None,
        receipt.reason == 'expanded_candidate_verified',
        int(receipt.expansion_round_count) > 0,
        initially_absent,
        in_generated,
        mutation_recorded,
        int(receipt.false_terminal_accepts) == 0,
        int(receipt.verification_failures) == 0,
    ))

    if accepted is None:
        reason = 'no_accepted_candidate'
    elif not initially_absent:
        reason = 'accepted_candidate_was_in_initial_space'
    elif not in_generated:
        reason = 'accepted_candidate_missing_from_generated_evidence'
    elif not mutation_recorded:
        reason = 'accepted_mutation_missing_from_solver_receipt'
    elif receipt.status != 'accept' or receipt.exact is not True:
        reason = 'solver_did_not_accept_exact_candidate'
    elif receipt.reason != 'expanded_candidate_verified' or receipt.expansion_round_count <= 0:
        reason = 'solver_did_not_accept_via_expansion'
    elif receipt.false_terminal_accepts or receipt.verification_failures:
        reason = 'terminal_verification_not_clean'
    else:
        reason = 'verified_expansion_novelty'

    proof_payload = {
        'valid': bool(valid),
        'initial_space_digest': initial_space,
        'initial_candidate_digests': list(initial_digests),
        'accepted_candidate_digest': accepted_digest,
        'generated_candidate_digests': list(generated_digests),
        'accepted_candidate_initially_absent': bool(initially_absent),
        'accepted_candidate_in_generated_set': bool(in_generated),
        'accepted_mutation_id': accepted_mutation_id,
        'accepted_mutation_recorded_in_receipt': bool(mutation_recorded),
        'expansion_round_count': int(receipt.expansion_round_count),
        'receipt_reason': str(receipt.reason),
        'false_terminal_accepts': int(receipt.false_terminal_accepts),
        'verification_failures': int(receipt.verification_failures),
        'reason': reason,
    }
    proof_digest = _sha256('r261proof:', proof_payload)

    return ExpansionNoveltyProof(
        bool(valid),
        initial_space,
        initial_digests,
        accepted_digest,
        generated_digests,
        bool(initially_absent),
        bool(in_generated),
        accepted_mutation_id,
        bool(mutation_recorded),
        int(receipt.expansion_round_count),
        proof_digest,
        reason,
    )


__all__ = [
    'ExpansionNoveltyProof',
    'repository_content_digest',
    'initial_version_space_digest',
    'prove_expansion_novelty',
]
