from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

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
from cogcoder.r261_version_space_expansion import ExpansionMutation, expand_repository_candidates


@dataclass(frozen=True, slots=True)
class CompositionalFrontierCandidate:
    candidate: RepositoryPatchCandidate
    mutation: ExpansionMutation
    depth: int
    parent_content_digest: str
    child_content_digest: str


@dataclass(frozen=True, slots=True)
class CompositionalExpansionRound:
    round_index: int
    trigger_kind: str
    triggering_probe_id: str
    triggering_probe_args: tuple[object, ...]
    survivors_before: int
    generated_candidates: int
    admitted_candidates: int
    composition_depth: int
    mutation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompositionalVersionSpaceReceipt:
    status: str
    candidate: RepositoryPatchCandidate | None
    exact: bool
    initial_survivors: int
    final_survivors: int
    selection_oracle_calls: int
    refinement_oracle_calls: int
    verification_oracle_calls: int
    oracle_calls_total: int
    candidate_evaluations: int
    expansion_round_count: int
    max_composition_depth_reached: int
    generated_candidates: int
    admitted_generated_candidates: int
    expansion_rounds: tuple[CompositionalExpansionRound, ...]
    observed_test_count: int
    observed_probe_ids: tuple[str, ...]
    false_terminal_accepts: int
    verification_failures: int
    reason: str
    trainable_parameter_count: int = 0


def _candidate_id_map(candidates: Sequence[RepositoryPatchCandidate]) -> dict[str, RepositoryPatchCandidate]:
    rows: dict[str, RepositoryPatchCandidate] = {}
    for candidate in candidates:
        prior = rows.get(candidate.candidate_id)
        if prior is not None and prior.files != candidate.files:
            raise ValueError('candidate ids must not alias different repository contents')
        rows[candidate.candidate_id] = candidate
    return rows


def expand_compositional_frontier(
    seeds: Sequence[RepositoryPatchCandidate],
    macros: Sequence[PatchMacro],
    *,
    parent_depths: Mapping[str, int] | None = None,
    seen_content_digests: Sequence[str] = (),
    max_composition_depth: int = 2,
    max_generated_candidates: int = 256,
    max_sites_per_macro: int = 64,
) -> tuple[CompositionalFrontierCandidate, ...]:
    """Generate one target-independent trusted-macro step from a repository frontier."""
    seeds = tuple(seeds)
    macros = tuple(macros)
    depth_budget = int(max_composition_depth)
    generation_budget = int(max_generated_candidates)
    site_budget = int(max_sites_per_macro)
    if depth_budget < 0 or generation_budget < 0 or site_budget < 0:
        raise ValueError('budgets must be non-negative')
    if not seeds or not macros or depth_budget == 0 or generation_budget == 0 or site_budget == 0:
        return ()

    seed_by_id = _candidate_id_map(seeds)
    depths = {str(key): int(value) for key, value in dict(parent_depths or {}).items()}
    if any(value < 0 for value in depths.values()):
        raise ValueError('parent depths must be non-negative')
    seen = {str(value) for value in seen_content_digests}

    generated = expand_repository_candidates(
        seeds,
        macros,
        max_generated_candidates=generation_budget,
        max_sites_per_macro=site_budget,
    )
    rows: list[CompositionalFrontierCandidate] = []
    child_seen: set[str] = set()
    for row in generated:
        parent = seed_by_id.get(row.mutation.seed_candidate_id)
        if parent is None:
            continue
        parent_depth = depths.get(parent.candidate_id, 0)
        child_depth = parent_depth + 1
        if child_depth > depth_budget:
            continue
        parent_digest = repository_content_digest(parent)
        child_digest = repository_content_digest(row.candidate)
        if child_digest in seen or child_digest in child_seen:
            continue
        child_seen.add(child_digest)
        rows.append(CompositionalFrontierCandidate(
            row.candidate, row.mutation, child_depth, parent_digest, child_digest,
        ))
    rows.sort(key=lambda item: (
        item.depth, item.child_content_digest, item.mutation.mutation_id, item.candidate.candidate_id,
    ))
    return tuple(rows[:generation_budget])


def _receipt(
    status: str,
    candidate: RepositoryPatchCandidate | None,
    exact: bool,
    initial_survivors: int,
    final_survivors: int,
    selection_calls: int,
    refinement_calls: int,
    verification_calls: int,
    candidate_evaluations: int,
    expansion_rounds: Sequence[CompositionalExpansionRound],
    max_depth_reached: int,
    generated_candidates: int,
    admitted_generated_candidates: int,
    observed_tests: Sequence[PatchTest],
    observed_probe_ids: Sequence[str],
    false_terminal_accepts: int,
    verification_failures: int,
    reason: str,
) -> CompositionalVersionSpaceReceipt:
    return CompositionalVersionSpaceReceipt(
        status, candidate, bool(exact), int(initial_survivors), int(final_survivors),
        int(selection_calls), int(refinement_calls), int(verification_calls),
        int(selection_calls) + int(refinement_calls) + int(verification_calls),
        int(candidate_evaluations), len(tuple(expansion_rounds)), int(max_depth_reached),
        int(generated_candidates), int(admitted_generated_candidates), tuple(expansion_rounds),
        len(tuple(observed_tests)), tuple(observed_probe_ids), int(false_terminal_accepts),
        int(verification_failures), str(reason), 0,
    )


def _probe_ids(probes: Sequence[RepositoryProbe]) -> set[str]:
    return {probe.probe_id for probe in probes}


def _test_probe_ids(tests: Sequence[PatchTest]) -> set[str]:
    ids: set[str] = set()
    for test in tests:
        try:
            ids.add(RepositoryProbe(tuple(test.args)).probe_id)
        except (TypeError, ValueError):
            continue
    return ids


def solve_repository_patch_with_compositional_expansion(
    candidates: Sequence[RepositoryPatchCandidate],
    initial_tests: Sequence[PatchTest],
    probe_inputs: Sequence[RepositoryProbe],
    oracle: Callable[..., object],
    *,
    refinement_inputs: Sequence[RepositoryProbe],
    verification_inputs: Sequence[RepositoryProbe],
    expansion_seeds: Sequence[RepositoryPatchCandidate],
    expansion_macros: Sequence[PatchMacro],
    max_selection_oracle_calls: int = 8,
    max_refinement_oracle_calls: int = 8,
    max_expansion_rounds: int = 2,
    max_composition_depth: int = 2,
    max_generated_candidates_per_round: int = 256,
    max_sites_per_macro: int = 64,
) -> CompositionalVersionSpaceReceipt:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    candidates = tuple(candidates)
    initial_tests = tuple(initial_tests)
    diagnostics = tuple(probe_inputs)
    refinements = tuple(refinement_inputs)
    verification = tuple(verification_inputs)
    expansion_seeds = tuple(expansion_seeds)
    expansion_macros = tuple(expansion_macros)

    selection_budget = int(max_selection_oracle_calls)
    refinement_budget = int(max_refinement_oracle_calls)
    expansion_budget = int(max_expansion_rounds)
    depth_budget = int(max_composition_depth)
    generation_budget = int(max_generated_candidates_per_round)
    site_budget = int(max_sites_per_macro)
    if min(selection_budget, refinement_budget, expansion_budget, depth_budget, generation_budget, site_budget) < 0:
        raise ValueError('budgets must be non-negative')
    if not candidates:
        return _receipt('abstain', None, False, 0, 0, 0, 0, 0, 0, (), 0, 0, 0, initial_tests, (), 0, 0, 'no_candidates')
    if not diagnostics:
        raise ValueError('probe_inputs must be non-empty')
    if not refinements:
        raise ValueError('refinement_inputs must be non-empty')
    if not verification:
        raise ValueError('verification_inputs must be non-empty')

    learning_ids = _probe_ids(diagnostics) | _probe_ids(refinements) | _test_probe_ids(initial_tests)
    if learning_ids & _probe_ids(verification):
        raise ValueError('verification_inputs must be disjoint from initial, diagnostic, and refinement evidence')

    arity_sets = [
        {len(probe.args) for probe in diagnostics},
        {len(probe.args) for probe in refinements},
        {len(probe.args) for probe in verification},
    ]
    if any(len(values) != 1 for values in arity_sets):
        raise ValueError('probe arity must be consistent')
    if not (arity_sets[0] == arity_sets[1] == arity_sets[2]):
        raise ValueError('diagnostic, refinement, and verification inputs must share arity')
    test_arities = {len(test.args) for test in initial_tests}
    if test_arities and (len(test_arities) != 1 or test_arities != arity_sets[0]):
        raise ValueError('initial tests must share probe arity')

    _candidate_id_map(candidates)
    _candidate_id_map(expansion_seeds)
    compiled, candidate_evaluations = _compile_candidates(candidates)
    survivors, initial_evals = _filter_initial(compiled, initial_tests)
    candidate_evaluations += initial_evals
    initial_survivors = len(survivors)

    observed_tests = list(initial_tests)
    observed_test_ids = {test.test_id for test in observed_tests}
    observed_probe_ids: list[str] = []
    used_diagnostic_ids: set[str] = set()
    used_refinement_ids: set[str] = set()
    selection_calls = refinement_calls = verification_calls = 0
    expansion_receipts: list[CompositionalExpansionRound] = []
    generated_total = admitted_total = max_depth_reached = 0

    if not survivors:
        return _receipt('abstain', None, False, 0, 0, 0, 0, 0, candidate_evaluations, (), 0, 0, 0, observed_tests, observed_probe_ids, 0, 0, 'repository_version_space_empty')

    current_frontier = expansion_seeds
    frontier_depths = {candidate.candidate_id: 0 for candidate in expansion_seeds}
    authorized_ids = set(frontier_depths)
    seen_digests = {repository_content_digest(candidate) for candidate in (*candidates, *expansion_seeds)}

    def record_observation(kind: str, probe: RepositoryProbe, value: object) -> None:
        test_id = f'r263:{kind}:' + probe.probe_id.split(':', 1)[-1]
        if test_id not in observed_test_ids:
            observed_tests.append(PatchTest(test_id, tuple(probe.args), value))
            observed_test_ids.add(test_id)
        if probe.probe_id not in observed_probe_ids:
            observed_probe_ids.append(probe.probe_id)

    def expand_after_counterexample(
        trigger_kind: str,
        probe: RepositoryProbe,
        seeds: Sequence[RepositoryPatchCandidate],
        depths: Mapping[str, int],
    ):
        nonlocal candidate_evaluations, generated_total, admitted_total, max_depth_reached
        if len(expansion_receipts) >= expansion_budget:
            return None, 'expansion_round_budget_exhausted', {}
        if not seeds:
            return None, 'no_expansion_seeds', {}
        if not expansion_macros:
            return None, 'no_expansion_macros', {}
        if generation_budget == 0 or site_budget == 0:
            return None, 'expansion_generation_budget_exhausted', {}
        parent_max_depth = max((int(depths.get(seed.candidate_id, 0)) for seed in seeds), default=0)
        if parent_max_depth >= depth_budget:
            return None, 'composition_depth_budget_exhausted', {}

        generated = expand_compositional_frontier(
            seeds, expansion_macros, parent_depths=depths,
            seen_content_digests=tuple(seen_digests), max_composition_depth=depth_budget,
            max_generated_candidates=generation_budget, max_sites_per_macro=site_budget,
        )
        generated_total += len(generated)
        if not generated:
            return None, 'no_generated_candidates', {}
        for row in generated:
            seen_digests.add(row.child_content_digest)
            max_depth_reached = max(max_depth_reached, row.depth)
        generated_compiled, compile_evals = _compile_candidates(tuple(row.candidate for row in generated))
        candidate_evaluations += compile_evals
        admitted, filter_evals = _filter_initial(generated_compiled, tuple(observed_tests))
        candidate_evaluations += filter_evals
        admitted_total += len(admitted)
        depth_by_id = {row.candidate.candidate_id: row.depth for row in generated}
        expansion_receipts.append(CompositionalExpansionRound(
            len(expansion_receipts), trigger_kind, probe.probe_id, tuple(probe.args),
            len(survivors), len(generated), len(admitted),
            max((row.depth for row in generated), default=parent_max_depth),
            tuple(row.mutation.mutation_id for row in generated),
        ))
        if not admitted:
            return None, 'expansion_no_candidate_matches_counterexample', {}
        return admitted, None, {
            row.candidate.candidate_id: depth_by_id[row.candidate.candidate_id] for row in admitted
        }

    while True:
        if len(survivors) > 1:
            if selection_calls >= selection_budget:
                return _receipt('abstain', None, False, initial_survivors, len(survivors), selection_calls, refinement_calls, verification_calls, candidate_evaluations, expansion_receipts, max_depth_reached, generated_total, admitted_total, observed_tests, observed_probe_ids, 0, 0, 'selection_oracle_budget_exhausted')
            probe, partitions, evals = _best_probe(survivors, diagnostics, used_diagnostic_ids)
            candidate_evaluations += evals
            if probe is None or partitions is None:
                return _receipt('abstain', None, False, initial_survivors, len(survivors), selection_calls, refinement_calls, verification_calls, candidate_evaluations, expansion_receipts, max_depth_reached, generated_total, admitted_total, observed_tests, observed_probe_ids, 0, 0, 'no_informative_probe')
            oracle_key, oracle_value, oracle_ok = _oracle_outcome(oracle, probe.args)
            selection_calls += 1
            used_diagnostic_ids.add(probe.probe_id)
            if not oracle_ok:
                return _receipt('abstain', None, False, initial_survivors, len(survivors), selection_calls, refinement_calls, verification_calls, candidate_evaluations, expansion_receipts, max_depth_reached, generated_total, admitted_total, observed_tests, observed_probe_ids, 0, 0, 'selection_oracle_error')
            record_observation('diagnostic', probe, oracle_value)
            matching = partitions.get(oracle_key)
            if matching:
                survivors = matching
                continue
            admitted, reason, admitted_depths = expand_after_counterexample(
                'diagnostic', probe, current_frontier, frontier_depths
            )
            if admitted is None:
                return _receipt('abstain', None, False, initial_survivors, 0, selection_calls, refinement_calls, verification_calls, candidate_evaluations, expansion_receipts, max_depth_reached, generated_total, admitted_total, observed_tests, observed_probe_ids, 0, 0, str(reason))
            survivors = admitted
            current_frontier = tuple(row.candidate for row in admitted)
            frontier_depths = admitted_depths
            authorized_ids.update(frontier_depths)
            continue

        selected = survivors[0]
        next_refinement = next((probe for probe in refinements if probe.probe_id not in used_refinement_ids), None)
        if next_refinement is not None:
            if refinement_calls >= refinement_budget:
                return _receipt('abstain', None, False, initial_survivors, 1, selection_calls, refinement_calls, verification_calls, candidate_evaluations, expansion_receipts, max_depth_reached, generated_total, admitted_total, observed_tests, observed_probe_ids, 0, 0, 'refinement_oracle_budget_exhausted')
            candidate_key, _candidate_value = _outcome(selected.fn, next_refinement.args)
            candidate_evaluations += 1
            oracle_key, oracle_value, oracle_ok = _oracle_outcome(oracle, next_refinement.args)
            refinement_calls += 1
            used_refinement_ids.add(next_refinement.probe_id)
            if not oracle_ok:
                return _receipt('abstain', None, False, initial_survivors, 1, selection_calls, refinement_calls, verification_calls, candidate_evaluations, expansion_receipts, max_depth_reached, generated_total, admitted_total, observed_tests, observed_probe_ids, 0, 0, 'refinement_oracle_error')
            record_observation('refinement', next_refinement, oracle_value)
            if candidate_key == oracle_key:
                continue
            if selected.candidate.candidate_id not in authorized_ids:
                return _receipt('abstain', None, False, initial_survivors, 1, selection_calls, refinement_calls, verification_calls, candidate_evaluations, expansion_receipts, max_depth_reached, generated_total, admitted_total, observed_tests, observed_probe_ids, 0, 0, 'survivor_not_authorized_as_expansion_seed')
            selected_depth = frontier_depths.get(selected.candidate.candidate_id, 0)
            admitted, reason, admitted_depths = expand_after_counterexample(
                'refinement', next_refinement, (selected.candidate,),
                {selected.candidate.candidate_id: selected_depth},
            )
            if admitted is None:
                return _receipt('abstain', None, False, initial_survivors, 0, selection_calls, refinement_calls, verification_calls, candidate_evaluations, expansion_receipts, max_depth_reached, generated_total, admitted_total, observed_tests, observed_probe_ids, 0, 0, str(reason))
            survivors = admitted
            current_frontier = tuple(row.candidate for row in admitted)
            frontier_depths = admitted_depths
            authorized_ids.update(frontier_depths)
            continue

        verification_failures = 0
        for probe in verification:
            candidate_key, _candidate_value = _outcome(selected.fn, probe.args)
            candidate_evaluations += 1
            oracle_key, _oracle_value_result, oracle_ok = _oracle_outcome(oracle, probe.args)
            verification_calls += 1
            if not oracle_ok or candidate_key != oracle_key:
                verification_failures += 1
                return _receipt('abstain', None, False, initial_survivors, 1, selection_calls, refinement_calls, verification_calls, candidate_evaluations, expansion_receipts, max_depth_reached, generated_total, admitted_total, observed_tests, observed_probe_ids, 0, verification_failures, 'independent_verification_failed')

        selected_depth = frontier_depths.get(selected.candidate.candidate_id, 0)
        reason = 'compositional_candidate_verified' if selected_depth >= 2 else 'candidate_verified'
        return _receipt('accept', selected.candidate, True, initial_survivors, 1, selection_calls, refinement_calls, verification_calls, candidate_evaluations, expansion_receipts, max_depth_reached, generated_total, admitted_total, observed_tests, observed_probe_ids, 0, 0, reason)


__all__ = [
    'CompositionalFrontierCandidate', 'CompositionalExpansionRound',
    'CompositionalVersionSpaceReceipt', 'expand_compositional_frontier',
    'solve_repository_patch_with_compositional_expansion',
]
