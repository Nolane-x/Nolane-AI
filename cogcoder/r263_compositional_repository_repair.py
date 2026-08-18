from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from cogcoder.r247_executable_patch_cegis import PatchMacro, PatchTest
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import (
    RepositoryProbe,
    _best_probe,
    _compile_candidates,
    _filter_initial,
    _oracle_outcome,
    _outcome,
)
from cogcoder.r261_expansion_proof import repository_content_digest
from cogcoder.r261_version_space_expansion import ExpansionCandidate, expand_repository_candidates


@dataclass(frozen=True, slots=True)
class RefinementRoundReceipt:
    round_index: int
    triggering_probe_id: str
    triggering_probe_args: tuple[object, ...]
    seed_content_digest: str
    generated_candidates: int
    admitted_candidates: int
    selected_content_digest: str | None
    selected_mutation_id: str | None


@dataclass(frozen=True, slots=True)
class CompositionalRepositoryRepairReceipt:
    status: str
    candidate: RepositoryPatchCandidate | None
    exact: bool
    initial_unique_candidates: int
    initial_survivors: int
    final_survivors: int
    selection_oracle_calls: int
    refinement_oracle_calls: int
    final_verification_oracle_calls: int
    oracle_calls_total: int
    candidate_evaluations: int
    expansion_round_count: int
    generated_candidates: int
    admitted_generated_candidates: int
    refinement_counterexamples: int
    expansion_rounds: tuple[RefinementRoundReceipt, ...]
    accepted_mutation_chain: tuple[str, ...]
    accepted_edit_count: int
    accepted_content_digest: str | None
    generation_used_target_outputs: bool
    false_terminal_accepts: int
    verification_failures: int
    reason: str
    trainable_parameter_count: int = 0


def _canonical_initial_candidates(
    candidates: Sequence[RepositoryPatchCandidate],
) -> tuple[RepositoryPatchCandidate, ...]:
    """Deduplicate initial repository contents and remove caller IDs from search identity."""
    by_files: dict[tuple[tuple[str, str], ...], RepositoryPatchCandidate] = {}
    for candidate in candidates:
        prior = by_files.get(candidate.files)
        if prior is None or (
            int(candidate.edit_count),
            -int(candidate.support_score),
            tuple(candidate.macro_ids),
            str(candidate.candidate_id),
        ) < (
            int(prior.edit_count),
            -int(prior.support_score),
            tuple(prior.macro_ids),
            str(prior.candidate_id),
        ):
            by_files[candidate.files] = candidate
    rows: list[RepositoryPatchCandidate] = []
    for files, candidate in by_files.items():
        digest = repository_content_digest(candidate)
        rows.append(RepositoryPatchCandidate(
            f'r263seed:{digest.split(":", 1)[-1]}',
            tuple(candidate.macro_ids),
            files,
            int(candidate.support_score),
            int(candidate.edit_count),
        ))
    return tuple(sorted(rows, key=lambda row: (repository_content_digest(row), row.files)))


def _receipt(
    status: str,
    candidate: RepositoryPatchCandidate | None,
    exact: bool,
    *,
    initial_unique_candidates: int,
    initial_survivors: int,
    final_survivors: int,
    selection_oracle_calls: int,
    refinement_oracle_calls: int,
    final_verification_oracle_calls: int,
    candidate_evaluations: int,
    expansion_rounds: Sequence[RefinementRoundReceipt],
    generated_candidates: int,
    admitted_generated_candidates: int,
    refinement_counterexamples: int,
    accepted_mutation_chain: Sequence[str],
    false_terminal_accepts: int,
    verification_failures: int,
    reason: str,
) -> CompositionalRepositoryRepairReceipt:
    accepted_digest = repository_content_digest(candidate) if candidate is not None else None
    return CompositionalRepositoryRepairReceipt(
        status,
        candidate,
        bool(exact),
        int(initial_unique_candidates),
        int(initial_survivors),
        int(final_survivors),
        int(selection_oracle_calls),
        int(refinement_oracle_calls),
        int(final_verification_oracle_calls),
        int(selection_oracle_calls) + int(refinement_oracle_calls) + int(final_verification_oracle_calls),
        int(candidate_evaluations),
        len(tuple(expansion_rounds)),
        int(generated_candidates),
        int(admitted_generated_candidates),
        int(refinement_counterexamples),
        tuple(expansion_rounds),
        tuple(accepted_mutation_chain),
        int(candidate.edit_count) if candidate is not None else 0,
        accepted_digest,
        False,
        int(false_terminal_accepts),
        int(verification_failures),
        str(reason),
    )


def _matching_generated_row(
    selected: RepositoryPatchCandidate,
    generated: Sequence[ExpansionCandidate],
) -> ExpansionCandidate | None:
    digest = repository_content_digest(selected)
    rows = [row for row in generated if repository_content_digest(row.candidate) == digest]
    if not rows:
        return None
    return min(rows, key=lambda row: (row.mutation.mutation_id, row.candidate.candidate_id))


def solve_compositional_repository_patch(
    candidates: Sequence[RepositoryPatchCandidate],
    initial_tests: Sequence[PatchTest],
    diagnostic_inputs: Sequence[RepositoryProbe],
    refinement_inputs: Sequence[RepositoryProbe],
    oracle: Callable[..., object],
    *,
    final_verification_inputs: Sequence[RepositoryProbe],
    expansion_macros: Sequence[PatchMacro],
    max_selection_oracle_calls: int = 8,
    max_refinement_oracle_calls: int = 8,
    max_expansion_rounds: int = 4,
    max_generated_candidates_per_round: int = 256,
    max_sites_per_macro: int = 64,
) -> CompositionalRepositoryRepairReceipt:
    """Refine a partial repository repair with bounded counterexample-guided composition.

    Candidate generation itself is target-output-free: trusted PatchMacro mutations are
    enumerated before their generated candidates are filtered against already-public
    observations. Final verification is disjoint and terminal; it can never trigger
    another expansion round.
    """
    if not callable(oracle):
        raise TypeError('oracle must be callable')

    initial_tests = tuple(initial_tests)
    diagnostic_inputs = tuple(diagnostic_inputs)
    refinement_inputs = tuple(refinement_inputs)
    final_inputs = tuple(final_verification_inputs)
    macros = tuple(expansion_macros)
    selection_budget = int(max_selection_oracle_calls)
    refinement_budget = int(max_refinement_oracle_calls)
    expansion_budget = int(max_expansion_rounds)
    generation_budget = int(max_generated_candidates_per_round)
    site_budget = int(max_sites_per_macro)
    if min(selection_budget, refinement_budget, expansion_budget, generation_budget, site_budget) < 0:
        raise ValueError('budgets must be non-negative')
    if not final_inputs:
        raise ValueError('final_verification_inputs must be non-empty')
    if not refinement_inputs:
        raise ValueError('refinement_inputs must be non-empty')

    all_probe_sets = (diagnostic_inputs, refinement_inputs, final_inputs)
    arities = {len(probe.args) for group in all_probe_sets for probe in group}
    test_arities = {len(test.args) for test in initial_tests}
    if len(arities) != 1 or (test_arities and test_arities != arities):
        raise ValueError('initial, diagnostic, refinement, and final inputs must share arity')

    learning_args = {tuple(test.args) for test in initial_tests}
    learning_args.update(tuple(probe.args) for probe in diagnostic_inputs)
    learning_args.update(tuple(probe.args) for probe in refinement_inputs)
    if any(tuple(probe.args) in learning_args for probe in final_inputs):
        raise ValueError('final verification inputs must be disjoint from learning inputs')
    final_ids = [probe.probe_id for probe in final_inputs]
    if len(set(final_ids)) != len(final_ids):
        raise ValueError('final verification inputs must be unique')

    unique_candidates = _canonical_initial_candidates(tuple(candidates))
    initial_unique = len(unique_candidates)
    if not unique_candidates:
        return _receipt(
            'abstain', None, False,
            initial_unique_candidates=0, initial_survivors=0, final_survivors=0,
            selection_oracle_calls=0, refinement_oracle_calls=0,
            final_verification_oracle_calls=0, candidate_evaluations=0,
            expansion_rounds=(), generated_candidates=0,
            admitted_generated_candidates=0, refinement_counterexamples=0,
            accepted_mutation_chain=(), false_terminal_accepts=0,
            verification_failures=0, reason='no_candidates',
        )

    compiled, candidate_evaluations = _compile_candidates(unique_candidates)
    survivors, initial_evals = _filter_initial(compiled, initial_tests)
    candidate_evaluations += initial_evals
    initial_survivors = len(survivors)
    if not survivors:
        return _receipt(
            'abstain', None, False,
            initial_unique_candidates=initial_unique, initial_survivors=0, final_survivors=0,
            selection_oracle_calls=0, refinement_oracle_calls=0,
            final_verification_oracle_calls=0, candidate_evaluations=candidate_evaluations,
            expansion_rounds=(), generated_candidates=0,
            admitted_generated_candidates=0, refinement_counterexamples=0,
            accepted_mutation_chain=(), false_terminal_accepts=0,
            verification_failures=0, reason='repository_version_space_empty',
        )

    observed_tests = list(initial_tests)
    used_probe_ids: set[str] = set()
    selection_calls = 0
    refinement_calls = 0
    final_calls = 0
    expansion_rows: list[RefinementRoundReceipt] = []
    generated_total = 0
    admitted_total = 0
    refinement_counterexamples = 0
    mutation_chain: list[str] = []

    def abstain(reason: str, *, final_survivors: int | None = None, verification_failures: int = 0):
        return _receipt(
            'abstain', None, False,
            initial_unique_candidates=initial_unique,
            initial_survivors=initial_survivors,
            final_survivors=len(survivors) if final_survivors is None else final_survivors,
            selection_oracle_calls=selection_calls,
            refinement_oracle_calls=refinement_calls,
            final_verification_oracle_calls=final_calls,
            candidate_evaluations=candidate_evaluations,
            expansion_rounds=expansion_rows,
            generated_candidates=generated_total,
            admitted_generated_candidates=admitted_total,
            refinement_counterexamples=refinement_counterexamples,
            accepted_mutation_chain=mutation_chain,
            false_terminal_accepts=0,
            verification_failures=verification_failures,
            reason=reason,
        )

    # Resolve any initial ambiguity without consuming refinement observations.
    while len(survivors) > 1:
        if selection_calls >= selection_budget:
            return abstain('selection_oracle_budget_exhausted')
        probe, partitions, evals = _best_probe(survivors, diagnostic_inputs, used_probe_ids)
        candidate_evaluations += evals
        if probe is None or partitions is None:
            return abstain('no_informative_diagnostic_probe')
        oracle_key, oracle_value, oracle_ok = _oracle_outcome(oracle, probe.args)
        selection_calls += 1
        used_probe_ids.add(probe.probe_id)
        if not oracle_ok:
            return abstain('diagnostic_oracle_error')
        test_id = 'r263:diagnostic:' + probe.probe_id.split(':', 1)[-1]
        observed_tests.append(PatchTest(test_id, tuple(probe.args), oracle_value))
        matching = partitions.get(oracle_key, ())
        if not matching:
            return abstain('oracle_outside_initial_candidate_version_space', final_survivors=0)
        survivors = matching

    for refinement_probe in refinement_inputs:
        if refinement_calls >= refinement_budget:
            return abstain('refinement_oracle_budget_exhausted')
        selected = survivors[0]
        candidate_key, _candidate_value = _outcome(selected.fn, refinement_probe.args)
        candidate_evaluations += 1
        oracle_key, oracle_value, oracle_ok = _oracle_outcome(oracle, refinement_probe.args)
        refinement_calls += 1
        used_probe_ids.add(refinement_probe.probe_id)
        if not oracle_ok:
            return abstain('refinement_oracle_error')
        test_id = 'r263:refinement:' + refinement_probe.probe_id.split(':', 1)[-1]
        if all(test.test_id != test_id for test in observed_tests):
            observed_tests.append(PatchTest(test_id, tuple(refinement_probe.args), oracle_value))
        if candidate_key == oracle_key:
            continue

        refinement_counterexamples += 1
        if len(expansion_rows) >= expansion_budget:
            return abstain('expansion_round_budget_exhausted')
        if not macros:
            return abstain('no_expansion_macros')
        if generation_budget == 0 or site_budget == 0:
            return abstain('expansion_generation_budget_exhausted')

        seed_candidate = selected.candidate
        seed_digest = repository_content_digest(seed_candidate)
        # Crucial information-flow boundary: target/oracle output is not an argument
        # to expansion. It is used only afterwards to filter generated hypotheses.
        generated = expand_repository_candidates(
            (seed_candidate,),
            macros,
            max_generated_candidates=generation_budget,
            max_sites_per_macro=site_budget,
        )
        generated_total += len(generated)
        if not generated:
            return abstain('no_generated_candidates', final_survivors=0)
        generated_compiled, compile_evals = _compile_candidates(tuple(row.candidate for row in generated))
        candidate_evaluations += compile_evals
        admitted, filter_evals = _filter_initial(generated_compiled, tuple(observed_tests))
        candidate_evaluations += filter_evals
        admitted_total += len(admitted)
        if not admitted:
            expansion_rows.append(RefinementRoundReceipt(
                len(expansion_rows), refinement_probe.probe_id, tuple(refinement_probe.args),
                seed_digest, len(generated), 0, None, None,
            ))
            return abstain('expansion_no_candidate_matches_counterexample', final_survivors=0)
        survivors = admitted

        while len(survivors) > 1:
            if selection_calls >= selection_budget:
                return abstain('selection_oracle_budget_exhausted_during_refinement')
            probe, partitions, evals = _best_probe(survivors, diagnostic_inputs, used_probe_ids)
            candidate_evaluations += evals
            if probe is None or partitions is None:
                return abstain('refinement_ambiguous_no_informative_probe')
            oracle_key2, oracle_value2, oracle_ok2 = _oracle_outcome(oracle, probe.args)
            selection_calls += 1
            used_probe_ids.add(probe.probe_id)
            if not oracle_ok2:
                return abstain('diagnostic_oracle_error_during_refinement')
            diagnostic_test_id = 'r263:diagnostic:' + probe.probe_id.split(':', 1)[-1]
            if all(test.test_id != diagnostic_test_id for test in observed_tests):
                observed_tests.append(PatchTest(diagnostic_test_id, tuple(probe.args), oracle_value2))
            survivors = partitions.get(oracle_key2, ())
            if not survivors:
                return abstain('oracle_outside_generated_candidate_version_space', final_survivors=0)

        selected_row = _matching_generated_row(survivors[0].candidate, generated)
        mutation_id = selected_row.mutation.mutation_id if selected_row is not None else None
        selected_digest = repository_content_digest(survivors[0].candidate)
        expansion_rows.append(RefinementRoundReceipt(
            len(expansion_rows), refinement_probe.probe_id, tuple(refinement_probe.args),
            seed_digest, len(generated), len(admitted), selected_digest, mutation_id,
        ))
        if mutation_id is None:
            return abstain('selected_generated_candidate_missing_mutation_provenance')
        mutation_chain.append(mutation_id)

    selected = survivors[0]
    verification_failures = 0
    for probe in final_inputs:
        candidate_key, _candidate_value = _outcome(selected.fn, probe.args)
        candidate_evaluations += 1
        oracle_key, _oracle_value, oracle_ok = _oracle_outcome(oracle, probe.args)
        final_calls += 1
        if not oracle_ok or candidate_key != oracle_key:
            verification_failures += 1
            return abstain(
                'independent_final_verification_failed',
                final_survivors=1,
                verification_failures=verification_failures,
            )

    return _receipt(
        'accept', selected.candidate, True,
        initial_unique_candidates=initial_unique,
        initial_survivors=initial_survivors,
        final_survivors=1,
        selection_oracle_calls=selection_calls,
        refinement_oracle_calls=refinement_calls,
        final_verification_oracle_calls=final_calls,
        candidate_evaluations=candidate_evaluations,
        expansion_rounds=expansion_rows,
        generated_candidates=generated_total,
        admitted_generated_candidates=admitted_total,
        refinement_counterexamples=refinement_counterexamples,
        accepted_mutation_chain=mutation_chain,
        false_terminal_accepts=0,
        verification_failures=0,
        reason='compositional_candidate_verified' if expansion_rows else 'existing_candidate_verified',
    )


__all__ = [
    'RefinementRoundReceipt',
    'CompositionalRepositoryRepairReceipt',
    'solve_compositional_repository_patch',
]
