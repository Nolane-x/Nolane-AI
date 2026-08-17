from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .r239_predicate_macros import ProbeMacro
from .r239_typed_probe_dsl import TypedProbe, evaluate_typed_probe
from .r244_recursive_abstraction import RecursiveAbstractionRecord
from .r245_role_free_binding import RoleFreeBindingReceipt, solve_role_free_recursive_macro


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


def _default_initial_test_ids(all_test_ids: Sequence[str]) -> tuple[str, ...]:
    """Choose eight target-independent coverage anchors from the frozen test order."""
    ids = tuple(sorted(map(str, all_test_ids)))
    if not ids:
        raise ValueError('test suite must be non-empty')
    if len(ids) <= 8:
        return ids
    # Spread anchors over the entire suite. Selection uses only test identity/order,
    # never hidden labels or semantic roles.
    points = (0.0, 1.0, 1/3, 2/3, 1/5, 4/5, 2/5, 3/5)
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

    The search receives only the current observed tests. A hidden fail-fast test
    runner may reveal one new failing test after each candidate. Hidden labels
    are never passed to R2.45 scoring until their test is explicitly revealed.
    Exhaustive hidden evaluation is used only to certify termination.
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
    last_receipt: RoleFreeBindingReceipt | None = None
    counterexamples = 0

    for round_index in range(int(max_counterexamples) + 1):
        visible_values = {tid: atom_values_by_test[tid] for tid in observed_list}
        visible_labels = {tid: labels[tid] for tid in observed_list}
        visible_posterior = {tid: 1.0 / len(observed_list) for tid in observed_list}
        last_receipt = solve_role_free_recursive_macro(
            macro_id,
            base_macros=base_macros,
            records=records,
            atom_ids=atom_ids,
            posterior=visible_posterior,
            atom_values_by_hypothesis=visible_values,
            target_labels=visible_labels,
            blocked_macro_ids=blocked_macro_ids,
            beam_width=beam_width,
        )
        total_candidates += int(last_receipt.candidates_evaluated)
        program = last_receipt.program
        if program is None:
            rounds.append(SparseFeedbackRound(
                round_index, tuple(observed_list), None, False, None,
                last_receipt.candidates_evaluated,
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
            bool(last_receipt.exact), counterexample,
            last_receipt.candidates_evaluated,
        ))
        if counterexample is None:
            # Certification is separate from search feedback: no hidden labels are
            # added to scoring here. This mirrors a final clean test-suite pass.
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
