from __future__ import annotations

from typing import Callable, Mapping, Sequence

from .r256_operator_dsl import Binary, Expr, Field
from .r268_cross_task_causal_transfer import (
    TransferCandidate,
    TransferQueryTrace,
    TransferReceipt,
    _canonical_number,
    _choose_diagnostic,
    _context_key,
    _context_values,
    _dedupe_live_candidates,
    _equivalent,
    _failed_receipt,
    _safe_prediction,
)


_PROBE_ROLES = ('__p0', '__p1', '__p2')
_SCRATCH_OPS = ('add', 'sub', 'mul', 'min', 'max')


def generate_scratch_candidates(*, max_depth: int, max_candidates: int) -> tuple[TransferCandidate, ...]:
    max_depth = int(max_depth)
    max_candidates = int(max_candidates)
    if max_depth < 0 or max_depth > 2:
        raise ValueError('max_depth must be between 0 and 2')
    if max_candidates < 1:
        raise ValueError('max_candidates must be positive')

    out: list[TransferCandidate] = []
    seen: set[str] = set()

    def add(expr: Expr) -> bool:
        if len(out) >= max_candidates:
            return False
        from .r256_operator_dsl import expr_digest

        digest = expr_digest(expr)
        if digest in seen:
            return True
        seen.add(digest)
        ordinal = len(out)
        out.append(
            TransferCandidate(
                expression=expr,
                candidate_id=f'r268-scratch.{digest}',
                repair_distance=ordinal,
                role_permutation_distance=0,
            )
        )
        return len(out) < max_candidates

    fields = tuple(Field(role) for role in _PROBE_ROLES)
    for field in fields:
        if not add(field):
            return tuple(out)

    if max_depth == 0:
        return tuple(out)

    level1: list[Expr] = []
    for op in _SCRATCH_OPS:
        for left in fields:
            for right in fields:
                expr = Binary(op, left, right)
                level1.append(expr)
                if not add(expr):
                    return tuple(out)

    if max_depth == 1:
        return tuple(out)

    for op in _SCRATCH_OPS:
        for nested in level1:
            for field in fields:
                if not add(Binary(op, nested, field)):
                    return tuple(out)
                if not add(Binary(op, field, nested)):
                    return tuple(out)
    return tuple(out)


def solve_from_scratch(
    *,
    diagnostic_contexts: Sequence[Mapping[str, object]],
    terminal_contexts: Sequence[Mapping[str, object]],
    oracle: Callable[[Mapping[str, object]], object],
    max_selection_queries: int,
    max_candidates: int,
    max_depth: int,
) -> TransferReceipt:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    max_selection_queries = int(max_selection_queries)
    if max_selection_queries < 1:
        raise ValueError('max_selection_queries must be positive')

    diagnostics = tuple(diagnostic_contexts)
    terminals = tuple(terminal_contexts)
    if not diagnostics:
        raise ValueError('diagnostic_contexts must be non-empty')
    if not terminals:
        raise ValueError('terminal_contexts must be non-empty')

    diagnostic_keys = tuple(_context_key(row) for row in diagnostics)
    terminal_keys = tuple(_context_key(row) for row in terminals)
    if len(set(diagnostic_keys)) != len(diagnostic_keys):
        raise ValueError('diagnostic contexts must be unique')
    if len(set(terminal_keys)) != len(terminal_keys):
        raise ValueError('terminal contexts must be unique')
    if set(diagnostic_keys) & set(terminal_keys):
        raise ValueError('selection and terminal contexts must be disjoint')

    generated = generate_scratch_candidates(max_depth=max_depth, max_candidates=max_candidates)
    live = _dedupe_live_candidates(generated, diagnostics)
    trace: list[TransferQueryTrace] = []
    used_keys: set[str] = set()
    selection_queries = 0

    while live and selection_queries < max_selection_queries:
        if len(live) == 1 and selection_queries >= 1:
            break
        context = _choose_diagnostic(live, diagnostics, frozenset(used_keys))
        if context is None:
            break
        key = _context_key(context)
        values = _context_values(context)
        before = len(live)
        try:
            observed = _canonical_number(oracle(context))
        except (ArithmeticError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            return _failed_receipt(
                candidates_generated=len(generated), live=live,
                selection_queries=selection_queries + 1,
                terminal_queries=0, terminal_exact=0,
                reason='invalid_oracle_output', trace=trace,
            )
        selection_queries += 1
        used_keys.add(key)
        survivors: list[TransferCandidate] = []
        for candidate in live:
            valid, predicted = _safe_prediction(candidate.expression, context)
            if valid and _equivalent(predicted, observed):
                survivors.append(candidate)
        live = survivors
        trace.append(
            TransferQueryTrace(
                context_key=key,
                context_values=values,
                live_before=before,
                live_after=len(live),
                oracle_call_index=selection_queries,
            )
        )
        if not live:
            return _failed_receipt(
                candidates_generated=len(generated), live=live,
                selection_queries=selection_queries,
                terminal_queries=0, terminal_exact=0,
                reason='target_outside_scratch_space', trace=trace,
            )

    if selection_queries == 0:
        return _failed_receipt(
            candidates_generated=len(generated), live=live,
            selection_queries=0, terminal_queries=0, terminal_exact=0,
            reason='no_discriminating_diagnostic', trace=trace,
        )

    live_after_selection = len(live)
    terminal_queries = 0
    terminal_exact = 0
    for context in terminals:
        try:
            observed = _canonical_number(oracle(context))
        except (ArithmeticError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            return _failed_receipt(
                candidates_generated=len(generated), live=live,
                selection_queries=selection_queries,
                terminal_queries=terminal_queries + 1,
                terminal_exact=terminal_exact,
                reason='invalid_terminal_oracle_output', trace=trace,
            )
        terminal_queries += 1
        survivors = []
        for candidate in live:
            valid, predicted = _safe_prediction(candidate.expression, context)
            if valid and _equivalent(predicted, observed):
                survivors.append(candidate)
        live = survivors
        if not live:
            return _failed_receipt(
                candidates_generated=len(generated), live=live,
                selection_queries=selection_queries,
                terminal_queries=terminal_queries,
                terminal_exact=terminal_exact,
                reason='terminal_mismatch', trace=trace,
            )
        terminal_exact += 1

    if len(live) != 1:
        return _failed_receipt(
            candidates_generated=len(generated), live=live,
            selection_queries=selection_queries,
            terminal_queries=terminal_queries,
            terminal_exact=terminal_exact,
            reason='ambiguous_after_terminal', trace=trace,
        )

    selected = live[0]
    return TransferReceipt(
        passed=True,
        selected_expression=selected.expression,
        selected_candidate_id=selected.candidate_id,
        candidates_generated=len(generated),
        candidates_live_after_selection=live_after_selection,
        selection_queries=selection_queries,
        terminal_queries=terminal_queries,
        terminal_exact=terminal_exact,
        source_expression_selected=False,
        repaired_expression_selected=False,
        false_accepts=0,
        reason='verified_scratch',
        query_trace=tuple(trace),
        trainable_parameter_count=0,
    )
