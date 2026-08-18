from __future__ import annotations

import copy
import itertools
import json
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r253_external_cognition import ExternalWorkingState
from .r255_lifecycle import ProcedureLifecycleLedger
from .r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary, enumerate_expressions, evaluate_expr, expr_digest
from .r256_operator_invention import OperatorExample, OperatorInventionNeed
from .r257_vocabulary import AbstractionCall, CognitiveVocabulary, evaluate_with_vocabulary

_UNARY_OPS = ('abs', 'neg', 'strip', 'lower', 'upper', 'len', 'not')
_BINARY_OPS = ('add', 'sub', 'mul', 'div', 'min', 'max', 'eq', 'ne', 'lt', 'le', 'gt', 'ge', 'and', 'or')


@dataclass(frozen=True, slots=True)
class VocabularySynthesisReceipt:
    passed: bool
    expression: Expr | None
    candidates_considered: int
    search_evaluations: int
    used_abstraction_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class LiveVocabularyExecutionReceipt:
    success: bool
    rolled_back: bool
    reason: str
    output: object = None


def _vector(expr: Expr, examples: Sequence[OperatorExample], vocabulary: CognitiveVocabulary | None) -> tuple[tuple[object, ...] | None, int]:
    values: list[object] = []
    count = 0
    for row in examples:
        try:
            value = evaluate_with_vocabulary(expr, row.context, vocabulary) if vocabulary is not None else evaluate_expr(expr, row.context)
            json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
        except (KeyError, TypeError, ValueError, OverflowError):
            return None, count + 1
        count += 1
        values.append(value)
    return tuple(values), count


def _expected(examples: Sequence[OperatorExample]) -> tuple[object, ...]:
    return tuple(row.expected for row in examples)


def _used_abstractions(expr: Expr) -> tuple[str, ...]:
    out: set[str] = set()
    def walk(node: Expr) -> None:
        if isinstance(node, AbstractionCall):
            out.add(node.abstraction_id)
            for arg in node.args:
                walk(arg)
        elif isinstance(node, Unary):
            walk(node.arg)
        elif isinstance(node, Binary):
            walk(node.left); walk(node.right)
        elif isinstance(node, IfElse):
            walk(node.condition); walk(node.when_true); walk(node.when_false)
    walk(expr)
    return tuple(sorted(out))


def synthesize_base_with_budget(need: OperatorInventionNeed, examples: Sequence[OperatorExample]) -> VocabularySynthesisReceipt:
    target = _expected(examples)
    evaluations = 0
    candidates = enumerate_expressions(
        need.field_names,
        constants=need.constants,
        max_depth=need.max_depth,
        max_candidates=need.max_candidates,
    )
    for index, expr in enumerate(candidates, 1):
        vector, count = _vector(expr, examples, None)
        evaluations += count
        if vector == target:
            return VocabularySynthesisReceipt(True, expr, index, evaluations, (), 'base_exact')
    return VocabularySynthesisReceipt(False, None, len(candidates), evaluations, (), 'base_budget_exhausted')


def synthesize_with_vocabulary(
    need: OperatorInventionNeed,
    examples: Sequence[OperatorExample],
    vocabulary: CognitiveVocabulary,
    *,
    seed_expressions: Sequence[Expr] = (),
) -> VocabularySynthesisReceipt:
    if not examples:
        raise ValueError('examples must be non-empty')
    target = _expected(examples)
    max_candidates = int(need.max_candidates)
    max_depth = int(need.max_depth)
    bases: list[Expr] = [Field(name) for name in need.field_names]
    bases.extend(Const(value) for value in need.constants)
    out: list[Expr] = []
    seen: set[str] = set()
    semantic_seen: set[str] = set()
    evaluations = 0
    considered = 0

    def try_expr(expr: Expr) -> VocabularySynthesisReceipt | None:
        nonlocal evaluations, considered
        if expr.depth > max_depth or considered >= max_candidates:
            return None
        digest = expr_digest(expr)
        if digest in seen:
            return None
        seen.add(digest)
        considered += 1
        vector, count = _vector(expr, examples, vocabulary)
        evaluations += count
        if vector is None:
            return None
        sem = json.dumps(vector, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if sem in semantic_seen:
            return None
        semantic_seen.add(sem)
        out.append(expr)
        if vector == target:
            return VocabularySynthesisReceipt(True, expr, considered, evaluations, _used_abstractions(expr), 'vocabulary_exact')
        return None

    for expr in bases:
        hit = try_expr(expr)
        if hit:
            return hit

    seeds = tuple(seed_expressions)
    if not all(isinstance(expr, Expr) for expr in seeds):
        raise TypeError('seed_expressions must contain Expr values')
    seed_digests = {expr_digest(expr) for expr in seeds}
    for expr in sorted(seeds, key=lambda e: (e.depth, e.cost, expr_digest(e))):
        hit = try_expr(expr)
        if hit:
            return hit

    def frontier_rank(expr: Expr) -> tuple[int, int, int, str]:
        digest = expr_digest(expr)
        return (
            0 if digest in seed_digests else 1 if _used_abstractions(expr) else 2,
            expr.cost,
            expr.depth,
            digest,
        )

    # Verified working-memory intermediates get a narrow expansion pass before the
    # generic search re-enumerates lower layers. This is intentionally bounded: one
    # seed-bearing child per learned call, or one atomic partner for a base binary.
    if seeds:
        atomic_bases = tuple(sorted((expr for expr in out if expr.depth == 0), key=lambda e: (e.cost, expr_digest(e))))
        seed_frontier = tuple(sorted(seeds, key=frontier_rank))
        while seed_frontier:
            generated: list[Expr] = []
            for seed in seed_frontier:
                if seed.depth + 1 > max_depth:
                    continue
                for op in _UNARY_OPS:
                    before_len = len(out)
                    hit = try_expr(Unary(op, seed))
                    if hit:
                        return hit
                    if len(out) > before_len:
                        generated.append(out[-1])
                    if considered >= max_candidates:
                        return VocabularySynthesisReceipt(False, None, considered, evaluations, (), 'vocabulary_budget_exhausted')

            call_generators = []
            for abstraction in vocabulary.abstractions():
                if abstraction.parameter_count < 1:
                    continue
                rows = []
                for seed in seed_frontier:
                    if seed.depth + 1 > max_depth:
                        continue
                    for complex_index in range(abstraction.parameter_count):
                        pools = [atomic_bases] * abstraction.parameter_count
                        pools[complex_index] = (seed,)
                        rows.append(itertools.product(*pools))
                if rows:
                    call_generators.append((abstraction.abstraction_id, iter(itertools.chain.from_iterable(rows))))
            active_seed_calls = call_generators
            while active_seed_calls:
                next_active = []
                for abstraction_id, generator in active_seed_calls:
                    try:
                        args = next(generator)
                    except StopIteration:
                        continue
                    next_active.append((abstraction_id, generator))
                    call = AbstractionCall(abstraction_id, tuple(args))
                    if call.depth > max_depth:
                        continue
                    before_len = len(out)
                    hit = try_expr(call)
                    if hit:
                        return hit
                    if len(out) > before_len:
                        generated.append(out[-1])
                    if considered >= max_candidates:
                        return VocabularySynthesisReceipt(False, None, considered, evaluations, (), 'vocabulary_budget_exhausted')
                active_seed_calls = next_active

            for seed in seed_frontier:
                if seed.depth + 1 > max_depth:
                    continue
                for atom in atomic_bases:
                    for left, right in ((seed, atom), (atom, seed)):
                        for op in _BINARY_OPS:
                            before_len = len(out)
                            hit = try_expr(Binary(op, left, right))
                            if hit:
                                return hit
                            if len(out) > before_len:
                                generated.append(out[-1])
                            if considered >= max_candidates:
                                return VocabularySynthesisReceipt(False, None, considered, evaluations, (), 'vocabulary_budget_exhausted')
            next_depth = min((expr.depth for expr in generated), default=max_depth + 1)
            seed_frontier = tuple(sorted((expr for expr in generated if expr.depth == next_depth), key=frontier_rank))

    for depth in range(1, max_depth + 1):
        previous = tuple(expr for expr in out if expr.depth <= depth - 1)
        frontier = tuple(expr for expr in out if expr.depth == depth - 1)
        atomic = tuple(sorted((expr for expr in out if expr.depth == 0), key=lambda e: (e.cost, expr_digest(e))))

        # Reuse an already learned abstraction before opening a new Cartesian search layer.
        # This makes vocabulary growth reduce search rather than merely enlarge the grammar.
        priority_frontier = tuple(expr for expr in sorted(frontier, key=frontier_rank) if frontier_rank(expr)[0] < 2)
        generic_frontier = tuple(expr for expr in sorted(frontier, key=frontier_rank) if frontier_rank(expr)[0] == 2)

        # Reuse verified seeds and already-learned expressions before opening new search.
        for arg in priority_frontier:
            for op in _UNARY_OPS:
                hit = try_expr(Unary(op, arg))
                if hit:
                    return hit
                if considered >= max_candidates:
                    return VocabularySynthesisReceipt(False, None, considered, evaluations, (), 'vocabulary_budget_exhausted')

        # Bounded compositional call policy: at depth 1 all arguments are atomic. At
        # deeper layers exactly one argument may come from the current frontier and
        # every other argument is atomic. Generators are interleaved round-robin so
        # no abstraction can monopolize the candidate budget by identifier order.
        ordered_frontier = tuple(sorted(frontier, key=frontier_rank))
        call_generators = []
        for abstraction in vocabulary.abstractions():
            if depth == 1:
                combinations = itertools.product(atomic, repeat=abstraction.parameter_count)
            else:
                rows = []
                for complex_index in range(abstraction.parameter_count):
                    pools = [atomic] * abstraction.parameter_count
                    pools[complex_index] = ordered_frontier
                    rows.append(itertools.product(*pools))
                combinations = itertools.chain.from_iterable(rows)
            call_generators.append((
                abstraction.abstraction_id,
                iter(combinations),
            ))

        active = call_generators
        while active:
            next_active = []
            for abstraction_id, generator in active:
                try:
                    args = next(generator)
                except StopIteration:
                    continue
                next_active.append((abstraction_id, generator))
                call = AbstractionCall(abstraction_id, tuple(args))
                if call.depth != depth:
                    continue
                hit = try_expr(call)
                if hit:
                    return hit
                if considered >= max_candidates:
                    return VocabularySynthesisReceipt(False, None, considered, evaluations, (), 'vocabulary_budget_exhausted')
            active = next_active

        for arg in generic_frontier:
            for op in _UNARY_OPS:
                hit = try_expr(Unary(op, arg))
                if hit:
                    return hit
                if considered >= max_candidates:
                    return VocabularySynthesisReceipt(False, None, considered, evaluations, (), 'vocabulary_budget_exhausted')

        small_previous = tuple(sorted(previous, key=frontier_rank)[:64])
        for left in small_previous:
            for right in small_previous:
                if max(left.depth, right.depth) != depth - 1:
                    continue
                for op in _BINARY_OPS:
                    hit = try_expr(Binary(op, left, right))
                    if hit:
                        return hit
                    if considered >= max_candidates:
                        return VocabularySynthesisReceipt(False, None, considered, evaluations, (), 'vocabulary_budget_exhausted')
    return VocabularySynthesisReceipt(False, None, considered, evaluations, (), 'vocabulary_no_exact_candidate')


def _restore_state(target: ExternalWorkingState, source: ExternalWorkingState) -> None:
    target.context.clear(); target.context.update(copy.deepcopy(source.context))
    target.capabilities.clear(); target.capabilities.update(source.capabilities)
    target.evidence[:] = list(source.evidence)
    target.hypotheses[:] = list(source.hypotheses)
    target.subgoals[:] = list(source.subgoals)
    target.representation_id = source.representation_id
    target.notes[:] = list(source.notes)


def execute_with_live_verification(
    expression: Expr,
    state: ExternalWorkingState,
    *,
    output_field: str,
    expected: object,
    vocabulary: CognitiveVocabulary,
    lifecycle: ProcedureLifecycleLedger,
) -> LiveVocabularyExecutionReceipt:
    before = copy.deepcopy(state)
    used = _used_abstractions(expression)
    try:
        value = evaluate_with_vocabulary(expression, state.context, vocabulary)
        if value != expected:
            raise ValueError('live_counterexample')
        state.context[str(output_field)] = value
        state.capabilities.add(str(output_field))
        state.evidence.append('r257:vocabulary-live-verified')
        return LiveVocabularyExecutionReceipt(True, False, 'verified', value)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        _restore_state(state, before)
        for aid in used:
            if lifecycle.state(aid) == 'promoted':
                lifecycle.transition(aid, 'rolled_back', reason=f'live_counterexample:{type(exc).__name__}:{exc}')
                try:
                    vocabulary.remove(aid)
                except KeyError:
                    pass
        return LiveVocabularyExecutionReceipt(False, True, f'live_failure:{type(exc).__name__}:{exc}')


__all__ = [
    'VocabularySynthesisReceipt', 'LiveVocabularyExecutionReceipt',
    'synthesize_base_with_budget', 'synthesize_with_vocabulary', 'execute_with_live_verification',
]
