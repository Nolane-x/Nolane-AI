from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from typing import Callable, Sequence

from cogcoder.r247_executable_patch_cegis import PatchMacro, PatchTest, _BINOPS, _CMPOPS, _wrap
from cogcoder.r252_repository_query import RepositoryPatchCandidate, compile_repository_candidate
from cogcoder.r260_active_repository_probes import (
    RepositoryProbe,
    _best_probe,
    _compile_candidates,
    _filter_initial,
    _oracle_outcome,
    _outcome,
)


@dataclass(frozen=True, slots=True)
class ExpansionMutation:
    mutation_id: str
    seed_candidate_id: str
    macro_id: str
    path: str
    site_index: int


@dataclass(frozen=True, slots=True)
class ExpansionCandidate:
    candidate: RepositoryPatchCandidate
    mutation: ExpansionMutation


@dataclass(frozen=True, slots=True)
class ExpansionRoundReceipt:
    round_index: int
    triggering_probe_id: str
    triggering_probe_args: tuple[object, ...]
    survivors_before: int
    generated_candidates: int
    admitted_candidates: int
    mutation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VersionSpaceExpansionReceipt:
    status: str
    candidate: RepositoryPatchCandidate | None
    exact: bool
    initial_survivors: int
    final_survivors: int
    selection_oracle_calls: int
    verification_oracle_calls: int
    oracle_calls_total: int
    candidate_evaluations: int
    expansion_round_count: int
    generated_candidates: int
    admitted_generated_candidates: int
    expansion_rounds: tuple[ExpansionRoundReceipt, ...]
    false_terminal_accepts: int
    verification_failures: int
    reason: str
    trainable_parameter_count: int = 0


def _macro_key(macro: PatchMacro) -> tuple[object, ...]:
    return (macro.slot, macro.kind, macro.src or '', macro.dst or '', macro.macro_id)


def _seed_key(seed: RepositoryPatchCandidate) -> tuple[object, ...]:
    payload = json.dumps(seed.files, separators=(',', ':'), ensure_ascii=False)
    return (hashlib.sha256(payload.encode('utf-8')).hexdigest(), seed.candidate_id)


def _compatible(node: ast.AST, macro: PatchMacro) -> bool:
    if macro.slot == 'binop' and macro.kind == 'replace':
        return isinstance(node, ast.BinOp) and type(node.op).__name__ == macro.src and macro.dst in _BINOPS
    if macro.slot == 'operand_wrapper' and macro.kind == 'wrap':
        return (
            isinstance(node, ast.BinOp)
            and isinstance(node.left, ast.Name)
            and isinstance(node.right, ast.Name)
            and macro.dst in {'abs', 'neg', 'max0'}
        )
    if macro.slot == 'compare' and macro.kind == 'replace':
        return (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and type(node.ops[0]).__name__ == macro.src
            and macro.dst in _CMPOPS
        )
    if macro.slot == 'return_wrapper' and macro.kind == 'wrap':
        return isinstance(node, ast.Return) and node.value is not None and macro.dst in {'abs', 'neg', 'max0'}
    return False


def _apply(node: ast.AST, macro: PatchMacro) -> None:
    if macro.slot == 'binop':
        assert isinstance(node, ast.BinOp)
        node.op = _BINOPS[str(macro.dst)]()
        return
    if macro.slot == 'operand_wrapper':
        assert isinstance(node, ast.BinOp)
        node.left = _wrap(node.left, str(macro.dst))
        node.right = _wrap(node.right, str(macro.dst))
        return
    if macro.slot == 'compare':
        assert isinstance(node, ast.Compare)
        node.ops[0] = _CMPOPS[str(macro.dst)]()
        return
    if macro.slot == 'return_wrapper':
        assert isinstance(node, ast.Return) and node.value is not None
        node.value = _wrap(node.value, str(macro.dst))
        return
    raise ValueError('unsupported patch macro')


def _mutation_id(seed: RepositoryPatchCandidate, macro: PatchMacro, path: str, site_index: int) -> str:
    payload = json.dumps(
        {
            'seed_candidate_id': seed.candidate_id,
            'macro_id': macro.macro_id,
            'path': path,
            'site_index': int(site_index),
        },
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    )
    return 'r261m:' + hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _candidate_id(files: tuple[tuple[str, str], ...], mutation: ExpansionMutation) -> str:
    payload = json.dumps(
        {
            'files': files,
            'mutation': {
                'mutation_id': mutation.mutation_id,
                'seed_candidate_id': mutation.seed_candidate_id,
                'macro_id': mutation.macro_id,
                'path': mutation.path,
                'site_index': mutation.site_index,
            },
        },
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    )
    return 'r261c:' + hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _mutate_one(
    seed: RepositoryPatchCandidate,
    macro: PatchMacro,
    path: str,
    site_index: int,
) -> ExpansionCandidate | None:
    source_by_path = dict(seed.files)
    if path not in source_by_path:
        return None
    tree = ast.parse(source_by_path[path], filename=path)
    sites = [node for node in ast.walk(tree) if _compatible(node, macro)]
    if site_index < 0 or site_index >= len(sites):
        return None
    _apply(sites[site_index], macro)
    ast.fix_missing_locations(tree)
    updated = dict(source_by_path)
    updated[path] = ast.unparse(tree) + '\n'
    files = tuple(sorted(updated.items()))
    mutation = ExpansionMutation(
        _mutation_id(seed, macro, path, site_index),
        seed.candidate_id,
        macro.macro_id,
        path,
        int(site_index),
    )
    candidate = RepositoryPatchCandidate(
        _candidate_id(files, mutation),
        tuple(sorted((*seed.macro_ids, macro.macro_id))),
        files,
        int(seed.support_score) + int(macro.support),
        int(seed.edit_count) + 1,
    )
    try:
        compile_repository_candidate(candidate)
    except Exception:
        return None
    return ExpansionCandidate(candidate, mutation)


def expand_repository_candidates(
    seeds: Sequence[RepositoryPatchCandidate],
    macros: Sequence[PatchMacro],
    *,
    max_generated_candidates: int = 256,
    max_sites_per_macro: int = 64,
) -> tuple[ExpansionCandidate, ...]:
    max_generated_candidates = int(max_generated_candidates)
    max_sites_per_macro = int(max_sites_per_macro)
    if max_generated_candidates < 0:
        raise ValueError('max_generated_candidates must be non-negative')
    if max_sites_per_macro < 0:
        raise ValueError('max_sites_per_macro must be non-negative')
    if max_generated_candidates == 0 or max_sites_per_macro == 0:
        return ()

    rows: list[ExpansionCandidate] = []
    seen_files: set[tuple[tuple[str, str], ...]] = set()
    for seed in sorted(tuple(seeds), key=_seed_key):
        for macro in sorted(tuple(macros), key=_macro_key):
            for path, source in sorted(seed.files):
                tree = ast.parse(source, filename=path)
                site_count = sum(1 for node in ast.walk(tree) if _compatible(node, macro))
                for site_index in range(min(site_count, max_sites_per_macro)):
                    row = _mutate_one(seed, macro, path, site_index)
                    if row is None or row.candidate.files in seen_files:
                        continue
                    seen_files.add(row.candidate.files)
                    rows.append(row)

    rows.sort(key=lambda row: (row.candidate.files, row.mutation.mutation_id, row.candidate.candidate_id))
    return tuple(rows[:max_generated_candidates])


def _receipt(
    status: str,
    candidate: RepositoryPatchCandidate | None,
    exact: bool,
    initial_survivors: int,
    final_survivors: int,
    selection_calls: int,
    verification_calls: int,
    candidate_evaluations: int,
    expansion_rounds: Sequence[ExpansionRoundReceipt],
    generated_candidates: int,
    admitted_generated_candidates: int,
    false_terminal_accepts: int,
    verification_failures: int,
    reason: str,
) -> VersionSpaceExpansionReceipt:
    return VersionSpaceExpansionReceipt(
        status,
        candidate,
        exact,
        int(initial_survivors),
        int(final_survivors),
        int(selection_calls),
        int(verification_calls),
        int(selection_calls) + int(verification_calls),
        int(candidate_evaluations),
        len(tuple(expansion_rounds)),
        int(generated_candidates),
        int(admitted_generated_candidates),
        tuple(expansion_rounds),
        int(false_terminal_accepts),
        int(verification_failures),
        reason,
    )


def solve_repository_patch_with_version_space_expansion(
    candidates: Sequence[RepositoryPatchCandidate],
    initial_tests: Sequence[PatchTest],
    probe_inputs: Sequence[RepositoryProbe],
    oracle: Callable[..., object],
    *,
    verification_inputs: Sequence[RepositoryProbe],
    expansion_seeds: Sequence[RepositoryPatchCandidate],
    expansion_macros: Sequence[PatchMacro],
    max_selection_oracle_calls: int = 8,
    max_expansion_rounds: int = 2,
    max_generated_candidates_per_round: int = 256,
    max_sites_per_macro: int = 64,
) -> VersionSpaceExpansionReceipt:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    candidates = tuple(candidates)
    initial_tests = tuple(initial_tests)
    probes = tuple(probe_inputs)
    verification = tuple(verification_inputs)
    expansion_seeds = tuple(expansion_seeds)
    expansion_macros = tuple(expansion_macros)
    selection_budget = int(max_selection_oracle_calls)
    expansion_budget = int(max_expansion_rounds)
    generation_budget = int(max_generated_candidates_per_round)
    site_budget = int(max_sites_per_macro)
    if selection_budget < 0 or expansion_budget < 0 or generation_budget < 0 or site_budget < 0:
        raise ValueError('budgets must be non-negative')
    if not candidates:
        return _receipt('abstain', None, False, 0, 0, 0, 0, 0, (), 0, 0, 0, 0, 'no_candidates')
    if not probes:
        raise ValueError('probe_inputs must be non-empty')
    if not verification:
        raise ValueError('verification_inputs must be non-empty')
    arities = {len(probe.args) for probe in probes}
    verification_arities = {len(probe.args) for probe in verification}
    test_arities = {len(test.args) for test in initial_tests}
    if len(arities) != 1 or len(verification_arities) != 1:
        raise ValueError('probe arity must be consistent')
    if arities != verification_arities or (test_arities and test_arities != arities):
        raise ValueError('initial, selection, and verification inputs must share arity')

    compiled, candidate_evaluations = _compile_candidates(candidates)
    survivors, initial_evals = _filter_initial(compiled, initial_tests)
    candidate_evaluations += initial_evals
    initial_survivors = len(survivors)
    if not survivors:
        return _receipt('abstain', None, False, 0, 0, 0, 0, candidate_evaluations, (), 0, 0, 0, 0, 'repository_version_space_empty')

    observed_tests = list(initial_tests)
    used_probe_ids: set[str] = set()
    selection_calls = 0
    verification_calls = 0
    expansion_receipts: list[ExpansionRoundReceipt] = []
    generated_total = 0
    admitted_total = 0
    current_expansion_seeds = expansion_seeds

    while len(survivors) > 1:
        if selection_calls >= selection_budget:
            return _receipt('abstain', None, False, initial_survivors, len(survivors), selection_calls, verification_calls, candidate_evaluations, expansion_receipts, generated_total, admitted_total, 0, 0, 'selection_oracle_budget_exhausted')
        probe, partitions, evals = _best_probe(survivors, probes, used_probe_ids)
        candidate_evaluations += evals
        if probe is None or partitions is None:
            return _receipt('abstain', None, False, initial_survivors, len(survivors), selection_calls, verification_calls, candidate_evaluations, expansion_receipts, generated_total, admitted_total, 0, 0, 'no_informative_probe')
        oracle_key, oracle_value, oracle_ok = _oracle_outcome(oracle, probe.args)
        selection_calls += 1
        used_probe_ids.add(probe.probe_id)
        if not oracle_ok:
            return _receipt('abstain', None, False, initial_survivors, len(survivors), selection_calls, verification_calls, candidate_evaluations, expansion_receipts, generated_total, admitted_total, 0, 0, 'selection_oracle_error')

        matching = partitions.get(oracle_key)
        if matching:
            survivors = matching
            continue

        if len(expansion_receipts) >= expansion_budget:
            return _receipt('abstain', None, False, initial_survivors, 0, selection_calls, verification_calls, candidate_evaluations, expansion_receipts, generated_total, admitted_total, 0, 0, 'expansion_round_budget_exhausted')
        if not current_expansion_seeds:
            return _receipt('abstain', None, False, initial_survivors, 0, selection_calls, verification_calls, candidate_evaluations, expansion_receipts, generated_total, admitted_total, 0, 0, 'no_expansion_seeds')
        if not expansion_macros:
            return _receipt('abstain', None, False, initial_survivors, 0, selection_calls, verification_calls, candidate_evaluations, expansion_receipts, generated_total, admitted_total, 0, 0, 'no_expansion_macros')
        if generation_budget == 0 or site_budget == 0:
            return _receipt('abstain', None, False, initial_survivors, 0, selection_calls, verification_calls, candidate_evaluations, expansion_receipts, generated_total, admitted_total, 0, 0, 'expansion_generation_budget_exhausted')

        test_id = 'r261:oracle:' + probe.probe_id.split(':', 1)[-1]
        if all(test.test_id != test_id for test in observed_tests):
            observed_tests.append(PatchTest(test_id, tuple(probe.args), oracle_value))
        generated = expand_repository_candidates(
            current_expansion_seeds,
            expansion_macros,
            max_generated_candidates=generation_budget,
            max_sites_per_macro=site_budget,
        )
        generated_total += len(generated)
        if not generated:
            return _receipt('abstain', None, False, initial_survivors, 0, selection_calls, verification_calls, candidate_evaluations, expansion_receipts, generated_total, admitted_total, 0, 0, 'no_generated_candidates')
        generated_compiled, compile_evals = _compile_candidates(tuple(row.candidate for row in generated))
        candidate_evaluations += compile_evals
        admitted, filter_evals = _filter_initial(generated_compiled, tuple(observed_tests))
        candidate_evaluations += filter_evals
        admitted_total += len(admitted)
        receipt = ExpansionRoundReceipt(
            len(expansion_receipts),
            probe.probe_id,
            tuple(probe.args),
            len(survivors),
            len(generated),
            len(admitted),
            tuple(row.mutation.mutation_id for row in generated),
        )
        expansion_receipts.append(receipt)
        if not admitted:
            return _receipt('abstain', None, False, initial_survivors, 0, selection_calls, verification_calls, candidate_evaluations, expansion_receipts, generated_total, admitted_total, 0, 0, 'expansion_no_candidate_matches_counterexample')
        survivors = admitted
        current_expansion_seeds = tuple(row.candidate for row in admitted)

    selected = survivors[0]
    verification_failures = 0
    for probe in verification:
        candidate_key, _candidate_value = _outcome(selected.fn, probe.args)
        candidate_evaluations += 1
        oracle_key, _oracle_value, oracle_ok = _oracle_outcome(oracle, probe.args)
        verification_calls += 1
        if not oracle_ok or candidate_key != oracle_key:
            verification_failures += 1
            return _receipt('abstain', None, False, initial_survivors, 1, selection_calls, verification_calls, candidate_evaluations, expansion_receipts, generated_total, admitted_total, 0, verification_failures, 'independent_verification_failed')

    reason = 'expanded_candidate_verified' if expansion_receipts else 'existing_candidate_verified'
    return _receipt('accept', selected.candidate, True, initial_survivors, 1, selection_calls, verification_calls, candidate_evaluations, expansion_receipts, generated_total, admitted_total, 0, 0, reason)


__all__ = [
    'ExpansionMutation',
    'ExpansionCandidate',
    'ExpansionRoundReceipt',
    'VersionSpaceExpansionReceipt',
    'expand_repository_candidates',
    'solve_repository_patch_with_version_space_expansion',
]
