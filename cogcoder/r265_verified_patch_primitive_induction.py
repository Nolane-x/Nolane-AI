from __future__ import annotations

import ast
import hashlib
import json
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
from cogcoder.r261_version_space_expansion import expand_repository_candidates
from cogcoder.r264_unified_adaptive_repository_search_base import _canonical_candidates_by_content


_SUPPORTED_BINOPS = frozenset({'Add', 'Sub', 'Mult', 'Div', 'FloorDiv', 'Mod'})


class PatchPrimitiveMacro(PatchMacro):
    """R2.65 semantic view over the inherited verified PatchMacro contract.

    Runtime authority remains the inherited fields ``slot/kind/src/dst/support``.
    Read-only aliases expose the R2.65 induction vocabulary without modifying the
    accepted parent class or widening the patch language.
    """

    @property
    def operation(self) -> str:
        return self.kind

    @property
    def source_value(self) -> str | None:
        return self.src

    @property
    def target_value(self) -> str | None:
        return self.dst


@dataclass(frozen=True, slots=True)
class PatchPrimitiveGrammar:
    allowed_slots: tuple[str, ...] = ('binop',)
    allowed_operations: tuple[str, ...] = ('replace',)
    allowed_target_values: tuple[str, ...] = ('Add', 'Sub', 'Mult', 'Div', 'FloorDiv', 'Mod')
    max_hypotheses: int = 64


@dataclass(frozen=True, slots=True)
class PrimitiveCandidate:
    macro: PatchPrimitiveMacro
    candidate: RepositoryPatchCandidate
    content_digest: str


@dataclass(frozen=True, slots=True)
class PatchPrimitiveInductionReceipt:
    status: str
    candidate: RepositoryPatchCandidate | None
    exact: bool
    learned_macro: PatchPrimitiveMacro | None
    primitive_promoted: bool
    initial_unique_candidates: int
    initial_survivors: int
    diagnostic_oracle_calls: int
    challenge_oracle_calls: int
    final_verification_oracle_calls: int
    oracle_calls_total: int
    candidate_evaluations: int
    hypotheses_enumerated: int
    generated_candidates: int
    candidates_after_diagnostic: int
    independent_challenges_passed: int
    diagnostic_counterexamples: int
    observed_test_count: int
    observed_probe_ids: tuple[str, ...]
    accepted_content_digest: str | None
    generation_used_target_outputs: bool
    false_terminal_accepts: int
    verification_failures: int
    reason: str
    trainable_parameter_count: int = 0


def _hash_macro(slot: str, operation: str, source_value: str, target_value: str) -> str:
    raw = json.dumps(
        [slot, operation, source_value, target_value],
        separators=(',', ':'),
        ensure_ascii=False,
    ).encode('utf-8')
    return 'r265pm:' + hashlib.sha256(raw).hexdigest()


def _validate_grammar(grammar: PatchPrimitiveGrammar) -> None:
    if int(grammar.max_hypotheses) < 0:
        raise ValueError('max_hypotheses must be non-negative')
    if tuple(grammar.allowed_slots) != ('binop',):
        raise ValueError('R2.65 grammar currently supports only the binop slot')
    if tuple(grammar.allowed_operations) != ('replace',):
        raise ValueError('R2.65 grammar currently supports only replace operations')
    targets = tuple(str(value) for value in grammar.allowed_target_values)
    if not targets:
        raise ValueError('allowed_target_values must be non-empty')
    if any(value not in _SUPPORTED_BINOPS for value in targets):
        raise ValueError('unsupported binop target in closed grammar')


def _observed_binop_types(seeds: Sequence[RepositoryPatchCandidate]) -> tuple[str, ...]:
    observed: set[str] = set()
    for candidate in _canonical_candidates_by_content(tuple(seeds)):
        for _path, source in candidate.files:
            try:
                tree = ast.parse(source)
            except SyntaxError as exc:
                raise ValueError('malformed repository snapshot') from exc
            for node in ast.walk(tree):
                if isinstance(node, ast.BinOp):
                    name = type(node.op).__name__
                    if name in _SUPPORTED_BINOPS:
                        observed.add(name)
    return tuple(sorted(observed))


def enumerate_patch_macro_hypotheses(
    seeds: Sequence[RepositoryPatchCandidate],
    grammar: PatchPrimitiveGrammar,
) -> tuple[PatchPrimitiveMacro, ...]:
    """Enumerate a closed, target-output-free primitive hypothesis language."""
    _validate_grammar(grammar)
    limit = int(grammar.max_hypotheses)
    if limit == 0:
        return ()
    observed = _observed_binop_types(tuple(seeds))
    targets = tuple(sorted(set(str(value) for value in grammar.allowed_target_values)))
    rows: list[PatchPrimitiveMacro] = []
    for source_value in observed:
        for target_value in targets:
            if source_value == target_value:
                continue
            rows.append(PatchPrimitiveMacro(
                _hash_macro('binop', 'replace', source_value, target_value),
                'binop',
                'replace',
                source_value,
                target_value,
                support=1,
            ))
    rows.sort(key=lambda row: (
        row.slot, row.kind, row.src or '', row.dst or '', row.macro_id,
    ))
    return tuple(rows[:limit])


def _probe_ids(probes: Sequence[RepositoryProbe]) -> tuple[str, ...]:
    return tuple(probe.probe_id for probe in probes)


def _test_probe_ids(tests: Sequence[PatchTest]) -> set[str]:
    result: set[str] = set()
    for test in tests:
        try:
            result.add(RepositoryProbe(tuple(test.args)).probe_id)
        except (TypeError, ValueError):
            continue
    return result


def _hypothesis_structural_capacity(
    seeds: Sequence[RepositoryPatchCandidate],
    macro: PatchPrimitiveMacro,
    *,
    max_sites_per_hypothesis: int,
) -> int:
    """Return a target-output-free upper bound on legal sites for one primitive."""
    site_budget = int(max_sites_per_hypothesis)
    if site_budget < 0:
        raise ValueError('max_sites_per_hypothesis must be non-negative')
    if site_budget == 0:
        return 0
    capacity = 0
    for seed in tuple(seeds):
        for _path, source in sorted(seed.files):
            tree = ast.parse(source)
            site_count = sum(
                1
                for node in ast.walk(tree)
                if isinstance(node, ast.BinOp)
                and type(node.op).__name__ == macro.source_value
            )
            capacity += min(site_count, site_budget)
    return capacity


def _generate_hypothesis_fair_candidates(
    seeds: Sequence[RepositoryPatchCandidate],
    hypotheses: Sequence[PatchPrimitiveMacro],
    *,
    max_generated_candidates: int,
    max_sites_per_hypothesis: int,
) -> tuple[PrimitiveCandidate, ...]:
    """Generate fairly while enforcing the generation budget before expansion.

    The global budget is first distributed round-robin across structurally
    applicable primitive hypotheses. Each underlying expansion call receives
    only its assigned quota, so the sum of requested and returned upstream
    candidates cannot exceed ``max_generated_candidates``. No oracle, target
    output, expected repository, or learned ranking signal participates.
    """
    budget = int(max_generated_candidates)
    site_budget = int(max_sites_per_hypothesis)
    if budget < 0 or site_budget < 0:
        raise ValueError('generation budgets must be non-negative')
    seeds = tuple(seeds)
    hypotheses = tuple(hypotheses)
    if budget == 0 or site_budget == 0 or not seeds or not hypotheses:
        return ()

    capacities = tuple(
        _hypothesis_structural_capacity(
            seeds, macro, max_sites_per_hypothesis=site_budget,
        )
        for macro in hypotheses
    )
    quotas = [0 for _ in hypotheses]
    remaining = budget
    while remaining > 0:
        progressed = False
        for index, capacity in enumerate(capacities):
            if quotas[index] >= capacity:
                continue
            quotas[index] += 1
            remaining -= 1
            progressed = True
            if remaining == 0:
                break
        if not progressed:
            break

    banks: list[tuple[PatchPrimitiveMacro, tuple[object, ...]]] = []
    for macro, quota in zip(hypotheses, quotas):
        if quota <= 0:
            banks.append((macro, ()))
            continue
        generated = expand_repository_candidates(
            seeds,
            (macro,),
            max_generated_candidates=quota,
            max_sites_per_macro=site_budget,
        )
        banks.append((macro, tuple(generated)))

    rows: list[PrimitiveCandidate] = []
    seen_pairs: set[tuple[str, str]] = set()
    rank = 0
    while len(rows) < budget:
        progressed = False
        for macro, generated in banks:
            if rank >= len(generated):
                continue
            progressed = True
            row = generated[rank]
            digest = repository_content_digest(row.candidate)
            key = (macro.macro_id, digest)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            rows.append(PrimitiveCandidate(macro, row.candidate, digest))
            if len(rows) >= budget:
                break
        if not progressed:
            break
        rank += 1
    return tuple(rows)


def solve_repository_patch_with_primitive_induction(
    candidates: Sequence[RepositoryPatchCandidate],
    initial_tests: Sequence[PatchTest],
    diagnostic_inputs: Sequence[RepositoryProbe],
    oracle: Callable[..., object],
    *,
    challenge_inputs: Sequence[RepositoryProbe],
    final_verification_inputs: Sequence[RepositoryProbe],
    expansion_seeds: Sequence[RepositoryPatchCandidate],
    grammar: PatchPrimitiveGrammar,
    max_selection_oracle_calls: int = 8,
    max_challenge_oracle_calls: int = 8,
    max_generated_candidates: int = 256,
    max_sites_per_hypothesis: int = 64,
    min_independent_challenges: int = 3,
) -> PatchPrimitiveInductionReceipt:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    _validate_grammar(grammar)

    raw_candidates = tuple(candidates)
    initial_tests = tuple(initial_tests)
    diagnostics = tuple(diagnostic_inputs)
    challenges = tuple(challenge_inputs)
    final_inputs = tuple(final_verification_inputs)
    raw_seeds = tuple(expansion_seeds)
    selection_budget = int(max_selection_oracle_calls)
    challenge_budget = int(max_challenge_oracle_calls)
    generation_budget = int(max_generated_candidates)
    site_budget = int(max_sites_per_hypothesis)
    min_challenges = int(min_independent_challenges)
    if min(selection_budget, challenge_budget, generation_budget, site_budget, min_challenges) < 0:
        raise ValueError('budgets must be non-negative')
    if not raw_candidates:
        return PatchPrimitiveInductionReceipt(
            'abstain', None, False, None, False, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, len(initial_tests), (), None, False, 0, 0, 'no_candidates', 0,
        )
    if not diagnostics:
        raise ValueError('diagnostic_inputs must be non-empty')
    if not challenges:
        raise ValueError('challenge_inputs must be non-empty')
    if not final_inputs:
        raise ValueError('final_verification_inputs must be non-empty')

    challenge_ids = _probe_ids(challenges)
    final_ids = _probe_ids(final_inputs)
    diagnostic_ids = _probe_ids(diagnostics)
    if len(set(diagnostic_ids)) != len(diagnostic_ids):
        raise ValueError('diagnostic_inputs must be unique')
    if len(set(challenge_ids)) != len(challenge_ids):
        raise ValueError('challenge_inputs must be unique')
    if len(set(final_ids)) != len(final_ids):
        raise ValueError('final verification inputs must be unique')
    learning_ids = set(diagnostic_ids) | set(challenge_ids) | _test_probe_ids(initial_tests)
    if learning_ids & set(final_ids):
        raise ValueError('final verification inputs must be disjoint from learning evidence')
    if set(diagnostic_ids) & set(challenge_ids):
        raise ValueError('challenge_inputs must be disjoint from diagnostic evidence')

    groups = (diagnostics, challenges, final_inputs)
    arities = {len(probe.args) for group in groups for probe in group}
    test_arities = {len(test.args) for test in initial_tests}
    if len(arities) != 1 or (test_arities and test_arities != arities):
        raise ValueError('all evidence inputs must share arity')

    candidates = _canonical_candidates_by_content(raw_candidates)
    seeds = _canonical_candidates_by_content(raw_seeds)
    initial_unique = len(candidates)
    compiled, candidate_evaluations = _compile_candidates(candidates)
    survivors, evals = _filter_initial(compiled, initial_tests)
    candidate_evaluations += evals
    initial_survivors = len(survivors)

    observed_tests = list(initial_tests)
    observed_test_ids = {test.test_id for test in observed_tests}
    observed_probe_ids: list[str] = []
    used_diagnostics: set[str] = set()
    diagnostic_calls = 0
    challenge_calls = 0
    final_calls = 0
    challenge_passes = 0
    diagnostic_counterexamples = 0
    hypotheses = enumerate_patch_macro_hypotheses(seeds, grammar)
    generated_total = 0
    candidates_after_diagnostic = 0

    def receipt(
        status: str,
        candidate: RepositoryPatchCandidate | None,
        learned_macro: PatchPrimitiveMacro | None,
        promoted: bool,
        reason: str,
        *,
        verification_failures: int = 0,
    ) -> PatchPrimitiveInductionReceipt:
        return PatchPrimitiveInductionReceipt(
            status=status,
            candidate=candidate,
            exact=(status == 'accept' and candidate is not None),
            learned_macro=learned_macro,
            primitive_promoted=bool(promoted),
            initial_unique_candidates=initial_unique,
            initial_survivors=initial_survivors,
            diagnostic_oracle_calls=diagnostic_calls,
            challenge_oracle_calls=challenge_calls,
            final_verification_oracle_calls=final_calls,
            oracle_calls_total=diagnostic_calls + challenge_calls + final_calls,
            candidate_evaluations=candidate_evaluations,
            hypotheses_enumerated=len(hypotheses),
            generated_candidates=generated_total,
            candidates_after_diagnostic=candidates_after_diagnostic,
            independent_challenges_passed=challenge_passes,
            diagnostic_counterexamples=diagnostic_counterexamples,
            observed_test_count=len(observed_tests),
            observed_probe_ids=tuple(observed_probe_ids),
            accepted_content_digest=(repository_content_digest(candidate) if candidate is not None else None),
            generation_used_target_outputs=False,
            false_terminal_accepts=0,
            verification_failures=int(verification_failures),
            reason=str(reason),
            trainable_parameter_count=0,
        )

    if min_challenges < 1 or challenge_budget < 1:
        return receipt('abstain', None, None, False, 'independent_challenge_required')

    if not survivors:
        return receipt('abstain', None, None, False, 'repository_version_space_empty')
    if not hypotheses:
        return receipt('abstain', None, None, False, 'no_patch_primitive_hypotheses')

    selected_probe: RepositoryProbe | None = None
    while len(survivors) > 1:
        if diagnostic_calls >= selection_budget:
            return receipt('abstain', None, None, False, 'selection_oracle_budget_exhausted')
        probe, partitions, probe_evals = _best_probe(survivors, diagnostics, used_diagnostics)
        candidate_evaluations += probe_evals
        if probe is None or partitions is None:
            # Zero entropy only means no remaining diagnostic splits the
            # current version space. It does not prove that the oracle lies
            # inside that space, so continue with bounded misspecification
            # probing below.
            break
        oracle_key, oracle_value, oracle_ok = _oracle_outcome(oracle, probe.args)
        diagnostic_calls += 1
        used_diagnostics.add(probe.probe_id)
        if not oracle_ok:
            return receipt('abstain', None, None, False, 'diagnostic_oracle_error')
        test_id = 'r265:diagnostic:' + probe.probe_id.split(':', 1)[-1]
        if test_id not in observed_test_ids:
            observed_tests.append(PatchTest(test_id, tuple(probe.args), oracle_value))
            observed_test_ids.add(test_id)
        if probe.probe_id not in observed_probe_ids:
            observed_probe_ids.append(probe.probe_id)
        matching = partitions.get(oracle_key)
        if matching:
            survivors = matching
            continue
        diagnostic_counterexamples += 1
        selected_probe = probe
        break

    if selected_probe is None and survivors:
        # Entropy-based probe selection is for discrimination. Once it cannot
        # split survivors (including a singleton), unused public diagnostics
        # still have a second role: falsify the entire surviving version space.
        # Oracle outputs are recorded only after the candidate outcomes for the
        # probe are computed, and candidate generation still receives no target
        # outputs.
        for probe in sorted(diagnostics, key=lambda row: row.probe_id):
            if probe.probe_id in used_diagnostics:
                continue
            if diagnostic_calls >= selection_budget:
                return receipt('abstain', None, None, False, 'selection_oracle_budget_exhausted')

            fallback_partitions = {}
            for compiled_row in survivors:
                candidate_key, _candidate_value = _outcome(compiled_row.fn, probe.args)
                candidate_evaluations += 1
                fallback_partitions.setdefault(candidate_key, []).append(compiled_row)

            oracle_key, oracle_value, oracle_ok = _oracle_outcome(oracle, probe.args)
            diagnostic_calls += 1
            used_diagnostics.add(probe.probe_id)
            if not oracle_ok:
                return receipt('abstain', None, None, False, 'diagnostic_oracle_error')
            test_id = 'r265:diagnostic:' + probe.probe_id.split(':', 1)[-1]
            if test_id not in observed_test_ids:
                observed_tests.append(PatchTest(test_id, tuple(probe.args), oracle_value))
                observed_test_ids.add(test_id)
            if probe.probe_id not in observed_probe_ids:
                observed_probe_ids.append(probe.probe_id)

            matching = fallback_partitions.get(oracle_key)
            if matching:
                survivors = tuple(matching)
                continue
            diagnostic_counterexamples += 1
            selected_probe = probe
            break

    if selected_probe is None:
        reason = (
            'no_informative_diagnostic_probe'
            if len(survivors) > 1
            else 'no_out_of_space_counterexample_for_induction'
        )
        return receipt('abstain', None, None, False, reason)
    if generation_budget == 0 or site_budget == 0:
        return receipt('abstain', None, None, False, 'primitive_generation_budget_exhausted')

    primitive_rows = list(_generate_hypothesis_fair_candidates(
        seeds,
        hypotheses,
        max_generated_candidates=generation_budget,
        max_sites_per_hypothesis=site_budget,
    ))
    generated_total = len(primitive_rows)
    if not primitive_rows:
        return receipt('abstain', None, None, False, 'no_generated_primitive_candidates')

    generated_candidates = tuple(row.candidate for row in primitive_rows)
    generated_compiled, compile_evals = _compile_candidates(generated_candidates)
    candidate_evaluations += compile_evals
    filtered, filter_evals = _filter_initial(generated_compiled, tuple(observed_tests))
    candidate_evaluations += filter_evals
    allowed_ids = {row.candidate.candidate_id for row in filtered}
    live = [row for row in primitive_rows if row.candidate.candidate_id in allowed_ids]
    candidates_after_diagnostic = len(live)
    if not live:
        return receipt('abstain', None, None, False, 'closed_grammar_cannot_express_counterexample')

    for probe in challenges:
        if challenge_calls >= challenge_budget:
            break
        oracle_key, oracle_value, oracle_ok = _oracle_outcome(oracle, probe.args)
        challenge_calls += 1
        if not oracle_ok:
            return receipt('abstain', None, None, False, 'challenge_oracle_error')
        test_id = 'r265:challenge:' + probe.probe_id.split(':', 1)[-1]
        if test_id not in observed_test_ids:
            observed_tests.append(PatchTest(test_id, tuple(probe.args), oracle_value))
            observed_test_ids.add(test_id)
        if probe.probe_id not in observed_probe_ids:
            observed_probe_ids.append(probe.probe_id)

        next_live: list[PrimitiveCandidate] = []
        for row in live:
            compiled_row, compile_evals = _compile_candidates((row.candidate,))
            candidate_evaluations += compile_evals
            if not compiled_row:
                continue
            candidate_key, _value = _outcome(compiled_row[0].fn, probe.args)
            candidate_evaluations += 1
            if candidate_key == oracle_key:
                next_live.append(row)
        live = next_live
        if not live:
            return receipt('abstain', None, None, False, 'all_primitive_hypotheses_rejected')
        challenge_passes += 1

    if challenge_passes < min_challenges:
        return receipt('abstain', None, None, False, 'insufficient_independent_challenges')

    unique_by_pair: dict[tuple[str, str], PrimitiveCandidate] = {
        (row.macro.macro_id, row.content_digest): row for row in live
    }
    live = sorted(unique_by_pair.values(), key=lambda row: (row.content_digest, row.macro.macro_id))
    if len(live) != 1:
        return receipt('abstain', None, None, False, 'primitive_hypothesis_ambiguous')

    selected = live[0]
    selected_compiled, compile_evals = _compile_candidates((selected.candidate,))
    candidate_evaluations += compile_evals
    if len(selected_compiled) != 1:
        return receipt('abstain', None, None, False, 'selected_candidate_not_executable')
    fn = selected_compiled[0].fn
    for probe in final_inputs:
        candidate_key, _candidate_value = _outcome(fn, probe.args)
        candidate_evaluations += 1
        oracle_key, _oracle_value, oracle_ok = _oracle_outcome(oracle, probe.args)
        final_calls += 1
        if not oracle_ok or candidate_key != oracle_key:
            return receipt(
                'abstain', None, None, False, 'independent_final_verification_failed',
                verification_failures=1,
            )

    return receipt('accept', selected.candidate, selected.macro, True, 'induced_patch_primitive_verified')


__all__ = [
    'PatchPrimitiveMacro',
    'PatchPrimitiveGrammar',
    'PrimitiveCandidate',
    'PatchPrimitiveInductionReceipt',
    'enumerate_patch_macro_hypotheses',
    'solve_repository_patch_with_primitive_induction',
]
