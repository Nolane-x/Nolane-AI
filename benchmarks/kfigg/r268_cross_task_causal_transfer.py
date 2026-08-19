from __future__ import annotations

from typing import Callable, Mapping

from cogcoder.r256_operator_dsl import Binary, Field, expr_digest
from cogcoder.r268_cross_task_causal_transfer import adapt_portable_program, export_expression_prior
from cogcoder.r268_cross_task_transfer_baseline import solve_from_scratch


Context = Mapping[str, object]
Oracle = Callable[[Context], object]


def _source_expression():
    return Binary('sub', Binary('add', Field('__p0'), Field('__p1')), Field('__p2'))


def _source_prior_ablation_expression():
    # Preserve three-role arity and comparable expression depth while destroying
    # the transferred causal skeleton. The same one-node repair machinery and
    # candidate budget are then used unchanged.
    return Binary('div', Field('__p0'), Binary('mul', Field('__p1'), Field('__p2')))


def _diagnostics() -> tuple[dict[str, int | float], ...]:
    return (
        {'__p0': 1, '__p1': 2, '__p2': 3},
        {'__p0': 2, '__p1': 4, '__p2': 1},
        {'__p0': -1, '__p1': 3, '__p2': 2},
        {'__p0': 5, '__p1': -2, '__p2': 4},
        {'__p0': 3, '__p1': 3, '__p2': 1},
        {'__p0': 6, '__p1': 2, '__p2': -3},
        {'__p0': -4, '__p1': 5, '__p2': 2},
        # Python floating subtraction is not reassociative. These public,
        # non-integral rows make that semantic distinction observable instead
        # of treating finite behavioral fingerprints as equivalence proofs.
        {'__p0': 1000000000000000.25, '__p1': 1000000000000000.125, '__p2': 0.1},
        {'__p0': 0.1, '__p1': 10000000000.1, '__p2': 10000000000.1},
    )


def _terminals() -> tuple[dict[str, int], ...]:
    return (
        {'__p0': 7, '__p1': 2, '__p2': 5},
        {'__p0': 4, '__p1': 6, '__p2': -1},
        {'__p0': -3, '__p1': -2, '__p2': 4},
    )


def _summary(receipt) -> dict[str, object]:
    return {
        'passed': bool(receipt.passed),
        'reason': str(receipt.reason),
        'selection_queries': int(receipt.selection_queries),
        'terminal_queries': int(receipt.terminal_queries),
        'terminal_exact': int(receipt.terminal_exact),
        'candidates_generated': int(receipt.candidates_generated),
        'false_accepts': int(receipt.false_accepts),
        'selected_expression_digest': (
            None if receipt.selected_expression is None else expr_digest(receipt.selected_expression)
        ),
        'trainable_parameter_count': int(receipt.trainable_parameter_count),
    }


def _run_positive(name: str, oracle: Oracle) -> dict[str, object]:
    portable = export_expression_prior(_source_expression())
    ablated_portable = export_expression_prior(_source_prior_ablation_expression())
    diagnostics = _diagnostics()
    terminals = _terminals()

    transfer = adapt_portable_program(
        portable,
        diagnostic_contexts=diagnostics,
        terminal_contexts=terminals,
        oracle=oracle,
        max_selection_queries=3,
        max_candidates=96,
    )
    source_prior_ablation = adapt_portable_program(
        ablated_portable,
        diagnostic_contexts=diagnostics,
        terminal_contexts=terminals,
        oracle=oracle,
        max_selection_queries=3,
        max_candidates=96,
    )
    tight_scratch = solve_from_scratch(
        diagnostic_contexts=diagnostics,
        terminal_contexts=terminals,
        oracle=oracle,
        max_selection_queries=3,
        max_candidates=96,
        max_depth=2,
    )
    roomy_scratch = solve_from_scratch(
        diagnostic_contexts=diagnostics,
        terminal_contexts=terminals,
        oracle=oracle,
        max_selection_queries=len(diagnostics),
        max_candidates=600,
        max_depth=2,
    )
    return {
        'name': name,
        'transfer': _summary(transfer),
        'source_prior_ablation': _summary(source_prior_ablation),
        'transfer_candidate_budget': 96,
        'source_prior_ablation_candidate_budget': 96,
        'tight_scratch': _summary(tight_scratch),
        'roomy_scratch': _summary(roomy_scratch),
    }


def _run_negative_outside_neighborhood() -> dict[str, object]:
    portable = export_expression_prior(_source_expression())

    def oracle(context: Context) -> object:
        return (context['__p0'] - context['__p1']) * context['__p2']

    receipt = adapt_portable_program(
        portable,
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=oracle,
        max_selection_queries=3,
        max_candidates=96,
    )
    return {'name': 'outside_one_repair_neighborhood', 'transfer': _summary(receipt)}


def _run_negative_terminal_contradiction() -> dict[str, object]:
    portable = export_expression_prior(_source_expression())
    terminal_keys = {
        (row['__p0'], row['__p1'], row['__p2'])
        for row in _terminals()
    }

    def oracle(context: Context) -> object:
        base = context['__p0'] * context['__p1'] - context['__p2']
        key = (context['__p0'], context['__p1'], context['__p2'])
        return base + 1 if key in terminal_keys else base

    receipt = adapt_portable_program(
        portable,
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=oracle,
        max_selection_queries=3,
        max_candidates=96,
    )
    return {'name': 'terminal_contradiction', 'transfer': _summary(receipt)}


def _diagnostic_order_invariance(oracle: Oracle) -> bool:
    portable = export_expression_prior(_source_expression())
    forward = adapt_portable_program(
        portable,
        diagnostic_contexts=_diagnostics(),
        terminal_contexts=_terminals(),
        oracle=oracle,
        max_selection_queries=3,
        max_candidates=96,
    )
    reverse = adapt_portable_program(
        portable,
        diagnostic_contexts=tuple(reversed(_diagnostics())),
        terminal_contexts=_terminals(),
        oracle=oracle,
        max_selection_queries=3,
        max_candidates=96,
    )
    return (
        forward.passed
        and reverse.passed
        and forward.selected_expression is not None
        and reverse.selected_expression is not None
        and expr_digest(forward.selected_expression) == expr_digest(reverse.selected_expression)
        and tuple(row.context_key for row in forward.query_trace)
        == tuple(row.context_key for row in reverse.query_trace)
    )


def run_benchmark() -> dict[str, object]:
    def permuted_roles(context: Context) -> object:
        return context['__p2'] + context['__p0'] - context['__p1']

    def one_operator_mul(context: Context) -> object:
        return context['__p0'] * context['__p1'] - context['__p2']

    def one_operator_sub(context: Context) -> object:
        return context['__p0'] - context['__p1'] - context['__p2']

    positives = (
        _run_positive('probe_role_permutation', permuted_roles),
        _run_positive('one_operator_mul_adaptation', one_operator_mul),
        _run_positive('one_operator_sub_adaptation', one_operator_sub),
    )
    negatives = (
        _run_negative_outside_neighborhood(),
        _run_negative_terminal_contradiction(),
    )

    positive_transfer_exact = sum(bool(row['transfer']['passed']) for row in positives)
    tight_scratch_exact = sum(bool(row['tight_scratch']['passed']) for row in positives)
    roomy_scratch_exact = sum(bool(row['roomy_scratch']['passed']) for row in positives)
    source_prior_ablation_exact = sum(
        bool(row['source_prior_ablation']['passed']) for row in positives
    )
    source_prior_ablation_same_candidate_budget = all(
        int(row['transfer_candidate_budget']) == int(row['source_prior_ablation_candidate_budget']) == 96
        for row in positives
    )
    negative_transfer_abstained = sum(not bool(row['transfer']['passed']) for row in negatives)
    false_accepts = (
        sum(int(row['transfer']['false_accepts']) for row in positives)
        + sum(int(row['source_prior_ablation']['false_accepts']) for row in positives)
        + sum(int(row['transfer']['false_accepts']) for row in negatives)
    )
    trainable_parameter_count = max(
        [int(row['transfer']['trainable_parameter_count']) for row in positives]
        + [int(row['source_prior_ablation']['trainable_parameter_count']) for row in positives]
        + [int(row['transfer']['trainable_parameter_count']) for row in negatives]
    )
    diagnostic_order_invariance = _diagnostic_order_invariance(one_operator_mul)

    all_gates_pass = (
        positive_transfer_exact == len(positives)
        and tight_scratch_exact == 0
        and roomy_scratch_exact == len(positives)
        and source_prior_ablation_exact == 0
        and source_prior_ablation_same_candidate_budget
        and negative_transfer_abstained == len(negatives)
        and diagnostic_order_invariance
        and false_accepts == 0
        and trainable_parameter_count == 0
    )

    return {
        'milestone': 'R2.68',
        'research_track': 'R2.68-T',
        'canonical_r268_owner_pr': 73,
        'capability': 'cross-task-causal-program-transfer',
        'status': 'independent_research_candidate',
        'all_gates_pass': all_gates_pass,
        'positive_transfer_cases': len(positives),
        'positive_transfer_exact': positive_transfer_exact,
        'negative_transfer_cases': len(negatives),
        'negative_transfer_abstained': negative_transfer_abstained,
        'tight_scratch_exact': tight_scratch_exact,
        'roomy_scratch_exact': roomy_scratch_exact,
        'source_prior_ablation_cases': len(positives),
        'source_prior_ablation_exact': source_prior_ablation_exact,
        'source_prior_ablation_same_candidate_budget': source_prior_ablation_same_candidate_budget,
        'diagnostic_order_invariance': diagnostic_order_invariance,
        'transfer_selection_queries_total': sum(
            int(row['transfer']['selection_queries']) for row in positives
        ),
        'tight_scratch_selection_queries_total': sum(
            int(row['tight_scratch']['selection_queries']) for row in positives
        ),
        'roomy_scratch_selection_queries_total': sum(
            int(row['roomy_scratch']['selection_queries']) for row in positives
        ),
        'false_accepts': false_accepts,
        'trainable_parameter_count': trainable_parameter_count,
        'positive_cases': list(positives),
        'negative_cases': list(negatives),
    }