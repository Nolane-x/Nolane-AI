from __future__ import annotations

import itertools
import json
import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary, evaluate_expr, expr_digest


_PROBE_ROLES = ('__p0', '__p1', '__p2')
_NUMERIC_BINARY_OPS = ('add', 'sub', 'mul', 'div', 'min', 'max')


def _used_fields(expr: Expr) -> frozenset[str]:
    if isinstance(expr, Field):
        return frozenset((expr.name,))
    if isinstance(expr, Const):
        return frozenset()
    if isinstance(expr, Unary):
        return _used_fields(expr.arg)
    if isinstance(expr, Binary):
        return _used_fields(expr.left) | _used_fields(expr.right)
    if isinstance(expr, IfElse):
        return (
            _used_fields(expr.condition)
            | _used_fields(expr.when_true)
            | _used_fields(expr.when_false)
        )
    raise TypeError(f'unsupported expression type: {type(expr).__name__}')


def _rewrite_fields(expr: Expr, mapping: Mapping[str, str]) -> Expr:
    if isinstance(expr, Field):
        return Field(mapping.get(expr.name, expr.name))
    if isinstance(expr, Const):
        return expr
    if isinstance(expr, Unary):
        return Unary(expr.op, _rewrite_fields(expr.arg, mapping))
    if isinstance(expr, Binary):
        return Binary(
            expr.op,
            _rewrite_fields(expr.left, mapping),
            _rewrite_fields(expr.right, mapping),
        )
    if isinstance(expr, IfElse):
        return IfElse(
            _rewrite_fields(expr.condition, mapping),
            _rewrite_fields(expr.when_true, mapping),
            _rewrite_fields(expr.when_false, mapping),
        )
    raise TypeError(f'unsupported expression type: {type(expr).__name__}')


def _one_binary_mutations(expr: Expr) -> tuple[Expr, ...]:
    out: list[Expr] = []
    if isinstance(expr, Binary):
        for op in _NUMERIC_BINARY_OPS:
            if op != expr.op:
                out.append(Binary(op, expr.left, expr.right))
        for mutated_left in _one_binary_mutations(expr.left):
            out.append(Binary(expr.op, mutated_left, expr.right))
        for mutated_right in _one_binary_mutations(expr.right):
            out.append(Binary(expr.op, expr.left, mutated_right))
    elif isinstance(expr, Unary):
        for mutated in _one_binary_mutations(expr.arg):
            out.append(Unary(expr.op, mutated))
    elif isinstance(expr, IfElse):
        for mutated in _one_binary_mutations(expr.condition):
            out.append(IfElse(mutated, expr.when_true, expr.when_false))
        for mutated in _one_binary_mutations(expr.when_true):
            out.append(IfElse(expr.condition, mutated, expr.when_false))
        for mutated in _one_binary_mutations(expr.when_false):
            out.append(IfElse(expr.condition, expr.when_true, mutated))
    return tuple(out)


def _finite_number(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError('numeric finite value required')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('numeric finite value required')
    return value


def _canonical_number(value: object) -> int | float:
    numeric = _finite_number(value)
    if isinstance(numeric, float) and numeric.is_integer():
        return int(numeric)
    return numeric


def _equivalent(left: object, right: object) -> bool:
    try:
        a = _finite_number(left)
        b = _finite_number(right)
    except (TypeError, ValueError):
        return False
    if isinstance(a, float) or isinstance(b, float):
        return math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-10)
    return a == b


def _context_values(context: Mapping[str, object]) -> tuple[int | float, int | float, int | float]:
    try:
        values = tuple(_canonical_number(context[role]) for role in _PROBE_ROLES)
    except KeyError as exc:
        raise ValueError(f'missing probe role: {exc.args[0]}') from exc
    return values  # type: ignore[return-value]


def _context_key(context: Mapping[str, object]) -> str:
    return json.dumps(_context_values(context), separators=(',', ':'), allow_nan=False)


def _safe_prediction(expr: Expr, context: Mapping[str, object]) -> tuple[bool, object]:
    try:
        value = _canonical_number(evaluate_expr(expr, context))
    except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return False, None
    return True, value


def _prediction_key(prediction: tuple[bool, object]) -> str:
    valid, value = prediction
    if not valid:
        return 'invalid'
    return json.dumps(_canonical_number(value), separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True, slots=True)
class PortableCausalProgram:
    expression: Expr
    expression_digest: str
    probe_roles: tuple[str, str, str] = _PROBE_ROLES
    trainable_parameter_count: int = 0

    def to_data(self) -> dict[str, object]:
        return {
            'schema_version': 1,
            'capability': 'portable-three-probe-causal-program',
            'probe_roles': list(self.probe_roles),
            'expression': self.expression.to_data(),
            'expression_digest': self.expression_digest,
            'trainable_parameter_count': self.trainable_parameter_count,
        }


@dataclass(frozen=True, slots=True)
class TransferCandidate:
    expression: Expr
    candidate_id: str
    repair_distance: int
    role_permutation_distance: int


@dataclass(frozen=True, slots=True)
class TransferQueryTrace:
    context_key: str
    context_values: tuple[int | float, int | float, int | float]
    live_before: int
    live_after: int
    oracle_call_index: int


@dataclass(frozen=True, slots=True)
class TransferReceipt:
    passed: bool
    selected_expression: Expr | None
    selected_candidate_id: str | None
    candidates_generated: int
    candidates_live_after_selection: int
    selection_queries: int
    terminal_queries: int
    terminal_exact: int
    source_expression_selected: bool
    repaired_expression_selected: bool
    false_accepts: int
    reason: str
    query_trace: tuple[TransferQueryTrace, ...]
    trainable_parameter_count: int = 0


def export_expression_prior(expression: Expr) -> PortableCausalProgram:
    if not isinstance(expression, Expr):
        raise TypeError('expression must be Expr')
    used = _used_fields(expression)
    if used != frozenset(_PROBE_ROLES):
        raise ValueError('expression must depend on exactly three abstract probe roles')
    return PortableCausalProgram(
        expression=expression,
        expression_digest=expr_digest(expression),
    )


def generate_transfer_candidates(portable: PortableCausalProgram) -> tuple[TransferCandidate, ...]:
    if not isinstance(portable, PortableCausalProgram):
        raise TypeError('portable must be PortableCausalProgram')

    bases: list[tuple[Expr, int]] = [(portable.expression, 0)]
    bases.extend((row, 1) for row in _one_binary_mutations(portable.expression))

    by_digest: dict[str, TransferCandidate] = {}
    for expression, repair_distance in bases:
        for permutation in itertools.permutations(_PROBE_ROLES):
            mapping = dict(zip(_PROBE_ROLES, permutation, strict=True))
            rewritten = _rewrite_fields(expression, mapping)
            digest = expr_digest(rewritten)
            candidate = TransferCandidate(
                expression=rewritten,
                candidate_id=f'r268.{digest}',
                repair_distance=repair_distance,
                role_permutation_distance=0 if permutation == _PROBE_ROLES else 1,
            )
            previous = by_digest.get(digest)
            if previous is None or (
                candidate.repair_distance,
                candidate.role_permutation_distance,
                candidate.candidate_id,
            ) < (
                previous.repair_distance,
                previous.role_permutation_distance,
                previous.candidate_id,
            ):
                by_digest[digest] = candidate

    return tuple(sorted(by_digest.values(), key=lambda row: (row.repair_distance, row.candidate_id)))


def _dedupe_live_candidates(
    candidates: Sequence[TransferCandidate],
    diagnostic_contexts: Sequence[Mapping[str, object]],
) -> list[TransferCandidate]:
    by_signature: dict[tuple[str, ...], TransferCandidate] = {}
    for candidate in candidates:
        signature = tuple(
            _prediction_key(_safe_prediction(candidate.expression, context))
            for context in diagnostic_contexts
        )
        previous = by_signature.get(signature)
        if previous is None or (
            candidate.repair_distance,
            candidate.role_permutation_distance,
            candidate.candidate_id,
        ) < (
            previous.repair_distance,
            previous.role_permutation_distance,
            previous.candidate_id,
        ):
            by_signature[signature] = candidate
    return sorted(
        by_signature.values(),
        key=lambda row: (row.repair_distance, row.role_permutation_distance, row.candidate_id),
    )


def _choose_diagnostic(
    live: Sequence[TransferCandidate],
    contexts: Sequence[Mapping[str, object]],
    used_keys: frozenset[str],
) -> Mapping[str, object] | None:
    best: tuple[tuple[int, int, str], Mapping[str, object]] | None = None
    for context in contexts:
        key = _context_key(context)
        if key in used_keys:
            continue
        partitions: dict[str, int] = {}
        for candidate in live:
            prediction = _prediction_key(_safe_prediction(candidate.expression, context))
            partitions[prediction] = partitions.get(prediction, 0) + 1
        if len(live) > 1 and len(partitions) <= 1:
            continue
        score = (max(partitions.values()), -len(partitions), key)
        if best is None or score < best[0]:
            best = (score, context)
    return None if best is None else best[1]


def _failed_receipt(
    *,
    candidates_generated: int,
    live: Sequence[TransferCandidate],
    selection_queries: int,
    terminal_queries: int,
    terminal_exact: int,
    reason: str,
    trace: Sequence[TransferQueryTrace],
) -> TransferReceipt:
    return TransferReceipt(
        passed=False,
        selected_expression=None,
        selected_candidate_id=None,
        candidates_generated=candidates_generated,
        candidates_live_after_selection=len(live),
        selection_queries=selection_queries,
        terminal_queries=terminal_queries,
        terminal_exact=terminal_exact,
        source_expression_selected=False,
        repaired_expression_selected=False,
        false_accepts=0,
        reason=reason,
        query_trace=tuple(trace),
    )


def adapt_portable_program(
    portable: PortableCausalProgram,
    *,
    diagnostic_contexts: Sequence[Mapping[str, object]],
    terminal_contexts: Sequence[Mapping[str, object]],
    oracle: Callable[[Mapping[str, object]], object],
    max_selection_queries: int,
    max_candidates: int,
) -> TransferReceipt:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    max_selection_queries = int(max_selection_queries)
    max_candidates = int(max_candidates)
    if max_selection_queries < 1:
        raise ValueError('max_selection_queries must be positive')
    if max_candidates < 1:
        raise ValueError('max_candidates must be positive')

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

    generated = generate_transfer_candidates(portable)[:max_candidates]
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
                candidates_generated=len(generated),
                live=live,
                selection_queries=selection_queries + 1,
                terminal_queries=0,
                terminal_exact=0,
                reason='invalid_oracle_output',
                trace=trace,
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
                candidates_generated=len(generated),
                live=live,
                selection_queries=selection_queries,
                terminal_queries=0,
                terminal_exact=0,
                reason='target_outside_transfer_neighborhood',
                trace=trace,
            )

    if selection_queries == 0:
        return _failed_receipt(
            candidates_generated=len(generated),
            live=live,
            selection_queries=0,
            terminal_queries=0,
            terminal_exact=0,
            reason='no_discriminating_diagnostic',
            trace=trace,
        )

    live_after_selection = len(live)
    terminal_queries = 0
    terminal_exact = 0
    for context in terminals:
        try:
            observed = _canonical_number(oracle(context))
        except (ArithmeticError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            return _failed_receipt(
                candidates_generated=len(generated),
                live=live,
                selection_queries=selection_queries,
                terminal_queries=terminal_queries + 1,
                terminal_exact=terminal_exact,
                reason='invalid_terminal_oracle_output',
                trace=trace,
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
                candidates_generated=len(generated),
                live=live,
                selection_queries=selection_queries,
                terminal_queries=terminal_queries,
                terminal_exact=terminal_exact,
                reason='terminal_mismatch',
                trace=trace,
            )
        terminal_exact += 1

    if len(live) != 1:
        return _failed_receipt(
            candidates_generated=len(generated),
            live=live,
            selection_queries=selection_queries,
            terminal_queries=terminal_queries,
            terminal_exact=terminal_exact,
            reason='ambiguous_after_terminal',
            trace=trace,
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
        source_expression_selected=expr_digest(selected.expression) == portable.expression_digest,
        repaired_expression_selected=selected.repair_distance > 0,
        false_accepts=0,
        reason='verified_transfer',
        query_trace=tuple(trace),
        trainable_parameter_count=0,
    )
