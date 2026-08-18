from __future__ import annotations

from typing import Callable, Mapping, Sequence

from cogcoder import r264_unified_adaptive_repository_search_base as _base


RepositoryPatchCandidate = _base.RepositoryPatchCandidate
RepositoryProbe = _base.RepositoryProbe
PatchMacro = _base.PatchMacro
PatchTest = _base.PatchTest
UnifiedAdaptiveRepositoryReceipt = _base.UnifiedAdaptiveRepositoryReceipt
AdaptiveExpansionRound = _base.AdaptiveExpansionRound


def _content_digest(candidate: RepositoryPatchCandidate) -> str:
    return _base.repository_content_digest(candidate)


def solve_unified_adaptive_repository_patch(
    candidates: Sequence[RepositoryPatchCandidate],
    initial_tests: Sequence[PatchTest],
    diagnostic_inputs: Sequence[RepositoryProbe],
    oracle: Callable[..., object],
    *,
    refinement_inputs: Sequence[RepositoryProbe],
    final_verification_inputs: Sequence[RepositoryProbe],
    expansion_seeds: Sequence[RepositoryPatchCandidate],
    expansion_macros: Sequence[PatchMacro],
    max_selection_oracle_calls: int = 8,
    max_refinement_oracle_calls: int = 8,
    max_expansion_rounds: int = 4,
    max_composition_depth: int = 4,
    max_generated_candidates_per_round: int = 256,
    max_sites_per_macro: int = 64,
) -> UnifiedAdaptiveRepositoryReceipt:
    """R2.64 solver with evidence-aware deterministic frontier fairness.

    The accepted R2.64 solver kept an authorized expansion frontier broader than
    the candidates still consistent with previously observed diagnostic evidence.
    Because generation is globally capped and content-sorted, a contradicted seed
    could consume every slot before a currently-live parent was expanded.

    This hotfix preserves the broader frontier because a contradicted ancestor can
    still mutate into a candidate that repairs all public evidence.  It only changes
    bounded scheduling: currently-live authorized parents get the first generation
    slots; unused slots then fall back to the remaining authorized parents.  Every
    generated child is still filtered by the complete public evidence ledger and
    generation receives neither the oracle nor target outputs.
    """
    if not callable(oracle):
        raise TypeError('oracle must be callable')

    raw_candidates = tuple(candidates)
    initial_tests = tuple(initial_tests)
    diagnostics = tuple(diagnostic_inputs)
    refinements = tuple(refinement_inputs)
    final_inputs = tuple(final_verification_inputs)
    raw_seeds = tuple(expansion_seeds)
    macros = tuple(expansion_macros)

    selection_budget = int(max_selection_oracle_calls)
    refinement_budget = int(max_refinement_oracle_calls)
    expansion_budget = int(max_expansion_rounds)
    depth_budget = int(max_composition_depth)
    generation_budget = int(max_generated_candidates_per_round)
    site_budget = int(max_sites_per_macro)
    if min(selection_budget, refinement_budget, expansion_budget, depth_budget, generation_budget, site_budget) < 0:
        raise ValueError('budgets must be non-negative')
    if not raw_candidates:
        return UnifiedAdaptiveRepositoryReceipt(
            'abstain', None, False, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, (), len(initial_tests), (), (), 0, None, False, 0, 0,
            'no_candidates', 0,
        )
    if not diagnostics:
        raise ValueError('diagnostic_inputs must be non-empty')
    if not refinements:
        raise ValueError('refinement_inputs must be non-empty')
    if not final_inputs:
        raise ValueError('final_verification_inputs must be non-empty')

    final_ids = tuple(probe.probe_id for probe in final_inputs)
    if len(set(final_ids)) != len(final_ids):
        raise ValueError('final verification inputs must be unique')
    learning_ids = _base._probe_ids(diagnostics) | _base._probe_ids(refinements) | _base._test_probe_ids(initial_tests)
    if learning_ids & set(final_ids):
        raise ValueError('final verification inputs must be disjoint from initial, diagnostic, and refinement evidence')

    probe_groups = (diagnostics, refinements, final_inputs)
    arities = {len(probe.args) for group in probe_groups for probe in group}
    test_arities = {len(test.args) for test in initial_tests}
    if len(arities) != 1 or (test_arities and test_arities != arities):
        raise ValueError('initial, diagnostic, refinement, and final inputs must share arity')

    candidates = _base._canonical_candidates_by_content(raw_candidates)
    seeds = _base._canonical_candidates_by_content(raw_seeds)
    initial_unique = len(candidates)
    compiled, candidate_evaluations = _base._compile_candidates(candidates)
    survivors, initial_evals = _base._filter_initial(compiled, initial_tests)
    candidate_evaluations += initial_evals
    initial_survivors = len(survivors)

    observed_tests = list(initial_tests)
    observed_test_ids = {test.test_id for test in observed_tests}
    observed_probe_ids: list[str] = []
    used_diagnostic_ids: set[str] = set()
    used_refinement_ids: set[str] = set()
    selection_calls = 0
    refinement_calls = 0
    final_calls = 0
    diagnostic_counterexamples = 0
    refinement_counterexamples = 0
    rounds: list[AdaptiveExpansionRound] = []
    generated_total = 0
    admitted_total = 0
    max_depth_reached = 0
    provenance: dict[str, tuple[str, str]] = {}

    current_frontier = seeds
    frontier_depths = {candidate.candidate_id: 0 for candidate in seeds}
    authorized_ids = set(frontier_depths)
    seen_digests = {_content_digest(candidate) for candidate in (*candidates, *seeds)}

    def receipt(
        status: str,
        candidate: RepositoryPatchCandidate | None,
        exact: bool,
        final_survivors: int,
        reason: str,
        *,
        verification_failures: int = 0,
    ) -> UnifiedAdaptiveRepositoryReceipt:
        accepted_digest = _content_digest(candidate) if candidate is not None else None
        mutation_chain = _base._trace_mutation_chain(candidate, provenance)
        return UnifiedAdaptiveRepositoryReceipt(
            status=status,
            candidate=candidate,
            exact=bool(exact),
            initial_unique_candidates=initial_unique,
            initial_survivors=initial_survivors,
            final_survivors=int(final_survivors),
            selection_oracle_calls=selection_calls,
            refinement_oracle_calls=refinement_calls,
            final_verification_oracle_calls=final_calls,
            oracle_calls_total=selection_calls + refinement_calls + final_calls,
            candidate_evaluations=candidate_evaluations,
            expansion_round_count=len(rounds),
            max_composition_depth_reached=max_depth_reached,
            generated_candidates=generated_total,
            admitted_generated_candidates=admitted_total,
            diagnostic_counterexamples=diagnostic_counterexamples,
            refinement_counterexamples=refinement_counterexamples,
            expansion_rounds=tuple(rounds),
            observed_test_count=len(observed_tests),
            observed_probe_ids=tuple(observed_probe_ids),
            accepted_mutation_chain=mutation_chain,
            accepted_edit_count=(int(candidate.edit_count) if candidate is not None else 0),
            accepted_content_digest=accepted_digest,
            generation_used_target_outputs=False,
            false_terminal_accepts=0,
            verification_failures=int(verification_failures),
            reason=reason,
            trainable_parameter_count=0,
        )

    if not survivors:
        return receipt('abstain', None, False, 0, 'repository_version_space_empty')

    def record_observation(kind: str, probe: RepositoryProbe, value: object) -> None:
        test_id = f'r264:{kind}:' + probe.probe_id.split(':', 1)[-1]
        if test_id not in observed_test_ids:
            observed_tests.append(PatchTest(test_id, tuple(probe.args), value))
            observed_test_ids.add(test_id)
        if probe.probe_id not in observed_probe_ids:
            observed_probe_ids.append(probe.probe_id)

    def expand_after_counterexample(
        trigger_kind: str,
        probe: RepositoryProbe,
        expansion_from: Sequence[RepositoryPatchCandidate],
        depths: Mapping[str, int],
        *,
        preferred_from: Sequence[RepositoryPatchCandidate] = (),
    ):
        nonlocal candidate_evaluations, generated_total, admitted_total, max_depth_reached
        if len(rounds) >= expansion_budget:
            return None, 'expansion_round_budget_exhausted', {}
        expansion_from = tuple(expansion_from)
        if not expansion_from:
            return None, 'no_expansion_seeds', {}
        if not macros:
            return None, 'no_expansion_macros', {}
        if generation_budget == 0 or site_budget == 0:
            return None, 'expansion_generation_budget_exhausted', {}

        eligible = tuple(
            seed for seed in expansion_from
            if int(depths.get(seed.candidate_id, 0)) < depth_budget
        )
        if not eligible:
            return None, 'composition_depth_budget_exhausted', {}
        parent_max_depth = max(int(depths.get(seed.candidate_id, 0)) for seed in eligible)

        preferred_digests = {_content_digest(seed) for seed in preferred_from}
        preferred = tuple(seed for seed in eligible if _content_digest(seed) in preferred_digests)
        fallback = tuple(seed for seed in eligible if _content_digest(seed) not in preferred_digests)

        generated_rows: list[_base.AdaptiveFrontierCandidate] = []
        generation_seen = set(seen_digests)
        remaining_budget = generation_budget
        for tier in (preferred, fallback):
            if not tier or remaining_budget <= 0:
                continue
            tier_rows = _base.expand_adaptive_repository_frontier(
                tier, macros,
                parent_depths=depths,
                seen_content_digests=tuple(generation_seen),
                max_composition_depth=depth_budget,
                max_generated_candidates=remaining_budget,
                max_sites_per_macro=site_budget,
            )
            generated_rows.extend(tier_rows)
            generation_seen.update(row.child_content_digest for row in tier_rows)
            remaining_budget -= len(tier_rows)

        generated = tuple(generated_rows)
        generated_total += len(generated)
        if not generated:
            return None, 'no_generated_candidates', {}
        for row in generated:
            seen_digests.add(row.child_content_digest)
            max_depth_reached = max(max_depth_reached, row.depth)
            provenance.setdefault(
                row.child_content_digest,
                (row.parent_content_digest, row.mutation.mutation_id),
            )

        generated_compiled, compile_evals = _base._compile_candidates(tuple(row.candidate for row in generated))
        candidate_evaluations += compile_evals
        admitted, filter_evals = _base._filter_initial(generated_compiled, tuple(observed_tests))
        candidate_evaluations += filter_evals
        admitted_total += len(admitted)
        depth_by_id = {row.candidate.candidate_id: row.depth for row in generated}
        rounds.append(AdaptiveExpansionRound(
            len(rounds), trigger_kind, probe.probe_id, tuple(probe.args), len(survivors),
            len(generated), len(admitted),
            max((row.depth for row in generated), default=parent_max_depth),
            tuple(row.mutation.mutation_id for row in generated),
        ))
        if not admitted:
            return None, 'expansion_no_candidate_matches_counterexample', {}
        return admitted, None, {
            row.candidate.candidate_id: depth_by_id[row.candidate.candidate_id]
            for row in admitted
        }

    while True:
        if len(survivors) > 1:
            if selection_calls >= selection_budget:
                return receipt('abstain', None, False, len(survivors), 'selection_oracle_budget_exhausted')
            probe, partitions, evals = _base._best_probe(survivors, diagnostics, used_diagnostic_ids)
            candidate_evaluations += evals
            if probe is None or partitions is None:
                return receipt('abstain', None, False, len(survivors), 'no_informative_diagnostic_probe')
            oracle_key, oracle_value, oracle_ok = _base._oracle_outcome(oracle, probe.args)
            selection_calls += 1
            used_diagnostic_ids.add(probe.probe_id)
            if not oracle_ok:
                return receipt('abstain', None, False, len(survivors), 'diagnostic_oracle_error')
            record_observation('diagnostic', probe, oracle_value)
            matching = partitions.get(oracle_key)
            if matching:
                survivors = matching
                continue

            diagnostic_counterexamples += 1
            live_parents = tuple(row.candidate for row in survivors)
            admitted, reason, admitted_depths = expand_after_counterexample(
                'diagnostic', probe, current_frontier, frontier_depths,
                preferred_from=live_parents,
            )
            if admitted is None:
                return receipt('abstain', None, False, 0, str(reason))
            survivors = admitted
            current_frontier = tuple(row.candidate for row in admitted)
            frontier_depths = admitted_depths
            authorized_ids.update(frontier_depths)
            continue

        selected = survivors[0]
        next_refinement = next(
            (probe for probe in refinements if probe.probe_id not in used_refinement_ids),
            None,
        )
        if next_refinement is not None:
            if refinement_calls >= refinement_budget:
                return receipt('abstain', None, False, 1, 'refinement_oracle_budget_exhausted')
            candidate_key, _candidate_value = _base._outcome(selected.fn, next_refinement.args)
            candidate_evaluations += 1
            oracle_key, oracle_value, oracle_ok = _base._oracle_outcome(oracle, next_refinement.args)
            refinement_calls += 1
            used_refinement_ids.add(next_refinement.probe_id)
            if not oracle_ok:
                return receipt('abstain', None, False, 1, 'refinement_oracle_error')
            record_observation('refinement', next_refinement, oracle_value)
            if candidate_key == oracle_key:
                continue

            refinement_counterexamples += 1
            if selected.candidate.candidate_id not in authorized_ids:
                return receipt('abstain', None, False, 1, 'survivor_not_authorized_as_expansion_seed')
            selected_depth = frontier_depths.get(selected.candidate.candidate_id, 0)
            admitted, reason, admitted_depths = expand_after_counterexample(
                'refinement', next_refinement, (selected.candidate,),
                {selected.candidate.candidate_id: selected_depth},
                preferred_from=(selected.candidate,),
            )
            if admitted is None:
                return receipt('abstain', None, False, 0, str(reason))
            survivors = admitted
            current_frontier = tuple(row.candidate for row in admitted)
            frontier_depths = admitted_depths
            authorized_ids.update(frontier_depths)
            continue

        for probe in final_inputs:
            candidate_key, _candidate_value = _base._outcome(selected.fn, probe.args)
            candidate_evaluations += 1
            oracle_key, _oracle_value, oracle_ok = _base._oracle_outcome(oracle, probe.args)
            final_calls += 1
            if not oracle_ok or candidate_key != oracle_key:
                return receipt(
                    'abstain', None, False, 1,
                    'independent_final_verification_failed', verification_failures=1,
                )

        selected_depth = frontier_depths.get(selected.candidate.candidate_id, 0)
        reason = 'unified_candidate_verified' if (
            diagnostic_counterexamples > 0 and selected_depth >= 2
        ) else 'candidate_verified'
        return receipt('accept', selected.candidate, True, 1, reason)


__all__ = ['solve_unified_adaptive_repository_patch']
