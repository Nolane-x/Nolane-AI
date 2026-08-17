from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r239_predicate_macros import ProbeMacro, instantiate_macro
from .r239_typed_probe_dsl import ProbeType, TypedProbe, evaluate_typed_probe, typed_prediction_row
from .r244_recursive_abstraction import (
    RecursiveAbstractionRecord,
    _CONNECTIVES,
    _base_argument_candidates,
    _program_atom_ids,
    propagate_quarantine,
)
from .r245_role_free_binding import RoleFreeBindingReceipt, binary_mutual_information


@dataclass(frozen=True)
class SparseFeedbackRound:
    round_index: int
    observed_test_ids: tuple[str, ...]
    candidate_probe_id: str | None
    candidate_exact_on_observed: bool
    counterexample_test_id: str | None
    candidates_evaluated: int


@dataclass(frozen=True)
class SparseFeedbackReceipt:
    status: str
    program: TypedProbe | None
    exact: bool
    initial_test_count: int
    counterexamples_revealed: int
    observed_test_ids: tuple[str, ...]
    feedback_fraction: float
    rounds: tuple[SparseFeedbackRound, ...]
    total_candidates_evaluated: int
    final_hidden_tests_exhaustively_verified: int
    privileged_role_scopes_used: bool
    reason: str


@dataclass(frozen=True)
class SparseAliasApplication:
    macro_id: str
    program: TypedProbe
    semantic_key: tuple[bool, ...]
    atom_footprint: tuple[str, ...]
    target_information: float
    observed_errors: int
    generation: int


def _default_initial_test_ids(all_test_ids: Sequence[str]) -> tuple[str, ...]:
    """Choose eight target-independent coverage anchors from the frozen test order."""
    ids = tuple(sorted(map(str, all_test_ids)))
    if not ids:
        raise ValueError('test suite must be non-empty')
    if len(ids) <= 8:
        return ids
    points = (0.0, 1.0, 1 / 3, 2 / 3, 1 / 5, 4 / 5, 2 / 5, 3 / 5)
    idxs = []
    for p in points:
        idx = int(round(p * (len(ids) - 1)))
        if idx not in idxs:
            idxs.append(idx)
    if len(idxs) < 8:
        for idx in range(len(ids)):
            if idx not in idxs:
                idxs.append(idx)
            if len(idxs) == 8:
                break
    return tuple(ids[i] for i in idxs[:8])


def _normalize_distribution(values: Mapping[str, float], expected_ids: Sequence[str]) -> dict[str, float]:
    ids = tuple(map(str, expected_ids))
    raw = {str(k): float(v) for k, v in values.items()}
    if set(raw) != set(ids):
        raise ValueError('posterior/hypothesis coverage mismatch')
    if any((not math.isfinite(v)) or v < 0.0 for v in raw.values()):
        raise ValueError('posterior must contain finite non-negative masses')
    total = sum(raw.values())
    if total <= 0.0:
        raise ValueError('posterior mass must be positive')
    return {hid: raw[hid] / total for hid in ids}


def _footprint(program: TypedProbe) -> tuple[str, ...]:
    return tuple(sorted(atom_id for _typ, atom_id in _program_atom_ids(program)))


def _rank_sparse_aliases(
    macro_id: str,
    generation: int,
    programs: Sequence[TypedProbe],
    *,
    hypothesis_ids: Sequence[str],
    posterior: Mapping[str, float],
    atom_values_by_hypothesis: Mapping[str, Mapping[str, int | bool]],
    target: Mapping[str, bool],
    representatives_per_footprint: int,
) -> tuple[SparseAliasApplication, ...]:
    """Preserve observational aliases when they imply different future compositions.

    Sparse tests can make two structurally different programs produce the same
    observed row. R2.45's global semantic dedupe was sound under dense feedback
    but is too destructive here: a discarded atom footprint can be the only one
    that composes legally with a disjoint peer later. We therefore dedupe by
    (observed semantics, atom footprint), then keep a bounded version-space per
    footprint. Counterexamples, not premature equivalence, collapse aliases.
    """
    k = int(representatives_per_footprint)
    if k <= 0:
        raise ValueError('representatives_per_footprint must be positive')
    target_key = tuple(bool(target[h]) for h in hypothesis_ids)
    by_alias: dict[tuple[tuple[bool, ...], tuple[str, ...]], SparseAliasApplication] = {}
    for program in programs:
        row = typed_prediction_row(program, atom_values_by_hypothesis)
        semantic_key = tuple(bool(row[h]) for h in hypothesis_ids)
        footprint = _footprint(program)
        info = binary_mutual_information(row, target, posterior)
        errors = sum(a != b for a, b in zip(semantic_key, target_key))
        app = SparseAliasApplication(
            str(macro_id), program, semantic_key, footprint, info, errors, int(generation)
        )
        alias_key = (semantic_key, footprint)
        prior = by_alias.get(alias_key)
        if prior is None or (
            app.observed_errors,
            -app.target_information,
            app.program.execution_cost,
            app.program.probe_id,
        ) < (
            prior.observed_errors,
            -prior.target_information,
            prior.program.execution_cost,
            prior.program.probe_id,
        ):
            by_alias[alias_key] = app

    by_footprint: dict[tuple[str, ...], list[SparseAliasApplication]] = {}
    for app in by_alias.values():
        by_footprint.setdefault(app.atom_footprint, []).append(app)

    kept: list[SparseAliasApplication] = []
    for footprint in sorted(by_footprint):
        ranked = sorted(
            by_footprint[footprint],
            key=lambda app: (
                -app.target_information,
                app.observed_errors,
                app.program.execution_cost,
                app.program.probe_id,
            ),
        )
        kept.extend(ranked[:k])
    return tuple(sorted(
        kept,
        key=lambda app: (
            -app.target_information,
            app.observed_errors,
            len(app.atom_footprint),
            app.atom_footprint,
            app.program.execution_cost,
            app.program.probe_id,
        ),
    ))


def _solve_sparse_role_free_recursive_macro(
    macro_id: str,
    *,
    base_macros: Sequence[ProbeMacro],
    records: Sequence[RecursiveAbstractionRecord],
    atom_ids: Sequence[str],
    posterior: Mapping[str, float],
    atom_values_by_hypothesis: Mapping[str, Mapping[str, int | bool]],
    target_labels: Mapping[str, bool],
    blocked_macro_ids: Sequence[str] = (),
    representatives_per_footprint: int = 8,
) -> RoleFreeBindingReceipt:
    """Sparse-feedback variant of R2.45 that keeps structural alias diversity."""
    k = int(representatives_per_footprint)
    if k <= 0:
        raise ValueError('representatives_per_footprint must be positive')
    atoms = tuple(sorted({str(a).strip().lower() for a in atom_ids if str(a).strip()}))
    if not atoms:
        raise ValueError('atom_ids must be non-empty')

    base_by_id = {str(m.macro_id): m for m in base_macros}
    rec_by_id = {str(r.macro.macro_id): r for r in records}
    if len(base_by_id) != len(tuple(base_macros)) or len(rec_by_id) != len(tuple(records)):
        raise ValueError('duplicate macro ids')
    if set(base_by_id) & set(rec_by_id):
        raise ValueError('base/recursive macro id collision')
    all_ids = set(base_by_id) | set(rec_by_id)
    target_id = str(macro_id)
    if target_id not in all_ids:
        raise KeyError(target_id)
    for macro in base_macros:
        if any(t is not ProbeType.BOOL for t in macro.parameter_types):
            raise TypeError('R2.46 sparse solver currently requires Boolean base parameters')
    for rec in records:
        if any(parent not in all_ids for parent in rec.parent_macro_ids):
            raise ValueError('recursive parent missing from registry')
        if any(
            rec_by_id[parent].generation >= rec.generation
            for parent in rec.parent_macro_ids
            if parent in rec_by_id
        ):
            raise ValueError('recursive lineage must be acyclic by generation')

    blocked = propagate_quarantine(records, blocked_macro_ids)
    if target_id in blocked:
        return RoleFreeBindingReceipt(
            'blocked', target_id, None, False, 0, 0, 0, len(atoms), len(base_by_id),
            False, k, tuple(sorted(blocked)), 0, (), 'target_or_ancestor_quarantined',
        )

    hypothesis_ids = tuple(sorted(map(str, atom_values_by_hypothesis)))
    if not hypothesis_ids:
        raise ValueError('hypotheses must be non-empty')
    post = _normalize_distribution(posterior, hypothesis_ids)
    target = {str(h): bool(v) for h, v in target_labels.items()}
    if set(target) != set(hypothesis_ids):
        raise ValueError('target label coverage mismatch')
    for hid in hypothesis_ids:
        missing = set(atoms) - set(map(str, atom_values_by_hypothesis[hid]))
        if missing:
            raise ValueError(f'hypothesis {hid} missing atoms')

    memo: dict[str, tuple[SparseAliasApplication, ...]] = {}
    base_evals = 0
    pair_evals = 0
    max_generation = 0

    def build(mid: str) -> tuple[SparseAliasApplication, ...]:
        nonlocal base_evals, pair_evals, max_generation
        if mid in memo:
            return memo[mid]
        if mid in blocked:
            memo[mid] = ()
            return ()
        if mid in base_by_id:
            macro = base_by_id[mid]
            args = _base_argument_candidates(macro, {ProbeType.BOOL: atoms})
            base_evals += len(args)
            programs = tuple(instantiate_macro(macro, args_row) for args_row in args)
            memo[mid] = _rank_sparse_aliases(
                mid, 0, programs,
                hypothesis_ids=hypothesis_ids,
                posterior=post,
                atom_values_by_hypothesis=atom_values_by_hypothesis,
                target=target,
                representatives_per_footprint=k,
            )
            return memo[mid]

        rec = rec_by_id[mid]
        max_generation = max(max_generation, int(rec.generation))
        left_id, right_id = rec.parent_macro_ids
        left_apps = build(left_id)
        right_apps = build(right_id)
        if not left_apps or not right_apps:
            memo[mid] = ()
            return ()
        ctor = _CONNECTIVES[rec.connective]
        programs: list[TypedProbe] = []
        for left in left_apps:
            left_atoms = set(left.atom_footprint)
            for right in right_apps:
                if left_atoms & set(right.atom_footprint):
                    continue
                pair_evals += 1
                programs.append(ctor(left.program, right.program))
        memo[mid] = _rank_sparse_aliases(
            mid, int(rec.generation), programs,
            hypothesis_ids=hypothesis_ids,
            posterior=post,
            atom_values_by_hypothesis=atom_values_by_hypothesis,
            target=target,
            representatives_per_footprint=k,
        )
        return memo[mid]

    final_apps = build(target_id)
    target_key = tuple(target[h] for h in hypothesis_ids)
    exact_apps = [app for app in final_apps if app.semantic_key == target_key]
    chosen = min(
        exact_apps,
        key=lambda app: (app.program.execution_cost, app.program.probe_id),
        default=(final_apps[0] if final_apps else None),
    )
    exact = bool(exact_apps)
    status = 'accept' if exact else ('abstain' if chosen is None else 'candidate')
    return RoleFreeBindingReceipt(
        status=status,
        target_macro_id=target_id,
        program=None if chosen is None else chosen.program,
        exact=exact,
        candidates_evaluated=base_evals + pair_evals,
        base_bindings_evaluated=base_evals,
        recursive_pairs_evaluated=pair_evals,
        shared_atom_count=len(atoms),
        base_macro_count=len(base_by_id),
        privileged_role_scopes_used=False,
        beam_width=k,
        blocked_closure=tuple(sorted(blocked)),
        max_generation=max_generation,
        frontier_sizes=tuple(sorted((mid, len(apps)) for mid, apps in memo.items())),
        reason='exact_sparse_alias_binding' if exact else 'sparse_alias_binding_not_exact',
    )


def _first_hidden_counterexample(
    program: TypedProbe,
    *,
    oracle_order: Sequence[str],
    observed: set[str],
    atom_values_by_test: Mapping[str, Mapping[str, int | bool]],
    hidden_target_labels: Mapping[str, bool],
) -> str | None:
    """Act like a fail-fast test runner: reveal at most one unseen failing test."""
    for test_id in oracle_order:
        tid = str(test_id)
        if tid in observed:
            continue
        predicted = bool(evaluate_typed_probe(program, atom_values_by_test[tid]))
        if predicted != bool(hidden_target_labels[tid]):
            return tid
    return None


def solve_with_sparse_counterexamples(
    macro_id: str,
    *,
    base_macros: Sequence[ProbeMacro],
    records: Sequence[RecursiveAbstractionRecord],
    atom_ids: Sequence[str],
    atom_values_by_test: Mapping[str, Mapping[str, int | bool]],
    hidden_target_labels: Mapping[str, bool],
    initial_test_ids: Sequence[str] | None = None,
    oracle_order: Sequence[str] | None = None,
    blocked_macro_ids: Sequence[str] = (),
    beam_width: int = 8,
    max_counterexamples: int = 48,
) -> SparseFeedbackReceipt:
    """CEGIS-style role-free binding with sparse observable feedback.

    Search sees only tests revealed so far. Sparse observational aliases remain in
    a bounded version-space when their atom footprints differ, so absence of
    evidence is not mistaken for semantic equivalence. A hidden fail-fast runner
    may reveal exactly one new failing test per round. The full suite is used
    only to certify a candidate once no unseen counterexample remains.
    """
    all_ids = tuple(sorted(map(str, atom_values_by_test)))
    if not all_ids:
        raise ValueError('atom_values_by_test must be non-empty')
    labels = {str(k): bool(v) for k, v in hidden_target_labels.items()}
    if set(labels) != set(all_ids):
        raise ValueError('hidden target/test coverage mismatch')
    if int(max_counterexamples) < 0:
        raise ValueError('max_counterexamples must be non-negative')

    initial = tuple(map(str, initial_test_ids)) if initial_test_ids is not None else _default_initial_test_ids(all_ids)
    if not initial or len(set(initial)) != len(initial) or any(tid not in labels for tid in initial):
        raise ValueError('invalid initial test set')
    order = tuple(map(str, oracle_order)) if oracle_order is not None else all_ids
    if set(order) != set(all_ids) or len(order) != len(all_ids):
        raise ValueError('oracle_order must be a permutation of the test suite')

    observed_list = list(initial)
    observed = set(observed_list)
    rounds: list[SparseFeedbackRound] = []
    total_candidates = 0
    program: TypedProbe | None = None
    counterexamples = 0

    for round_index in range(int(max_counterexamples) + 1):
        visible_values = {tid: atom_values_by_test[tid] for tid in observed_list}
        visible_labels = {tid: labels[tid] for tid in observed_list}
        visible_posterior = {tid: 1.0 / len(observed_list) for tid in observed_list}
        receipt = _solve_sparse_role_free_recursive_macro(
            macro_id,
            base_macros=base_macros,
            records=records,
            atom_ids=atom_ids,
            posterior=visible_posterior,
            atom_values_by_hypothesis=visible_values,
            target_labels=visible_labels,
            blocked_macro_ids=blocked_macro_ids,
            representatives_per_footprint=beam_width,
        )
        total_candidates += int(receipt.candidates_evaluated)
        program = receipt.program
        if program is None:
            rounds.append(SparseFeedbackRound(
                round_index, tuple(observed_list), None, False, None,
                receipt.candidates_evaluated,
            ))
            return SparseFeedbackReceipt(
                'abstain', None, False, len(initial), counterexamples,
                tuple(observed_list), len(observed_list) / len(all_ids), tuple(rounds),
                total_candidates, 0, False, 'no_candidate_under_sparse_feedback',
            )

        counterexample = _first_hidden_counterexample(
            program, oracle_order=order, observed=observed,
            atom_values_by_test=atom_values_by_test,
            hidden_target_labels=labels,
        )
        rounds.append(SparseFeedbackRound(
            round_index, tuple(observed_list), program.probe_id,
            bool(receipt.exact), counterexample,
            receipt.candidates_evaluated,
        ))
        if counterexample is None:
            exact_rows = sum(
                bool(evaluate_typed_probe(program, atom_values_by_test[tid])) == labels[tid]
                for tid in all_ids
            )
            exact = exact_rows == len(all_ids)
            return SparseFeedbackReceipt(
                'accept' if exact else 'abstain', program, exact,
                len(initial), counterexamples, tuple(observed_list),
                len(observed_list) / len(all_ids), tuple(rounds), total_candidates,
                exact_rows, False,
                'sparse_counterexample_converged' if exact else 'final_verification_failed',
            )

        if counterexamples >= int(max_counterexamples):
            break
        observed.add(counterexample)
        observed_list.append(counterexample)
        counterexamples += 1

    return SparseFeedbackReceipt(
        'abstain', program, False, len(initial), counterexamples,
        tuple(observed_list), len(observed_list) / len(all_ids), tuple(rounds),
        total_candidates, 0, False, 'counterexample_budget_exhausted',
    )
