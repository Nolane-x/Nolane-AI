from __future__ import annotations

import itertools
import json
import math
from collections import deque
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r256_operator_dsl import Binary, Expr, Field, IfElse, Unary, expr_digest
from .r256_operator_invention import OperatorExample, OperatorInventionNeed
from .r257_vocabulary import AbstractionCall, CognitiveVocabulary, evaluate_with_vocabulary
from .r257_vocabulary_synthesis import VocabularySynthesisReceipt, synthesize_with_vocabulary
from .r258_intervention_discovery import InterventionSpec, PositionalSchema, enumerate_interventions


def _semantic_value(value: object) -> object:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('semantic values must be finite')
        value = 0.0 if value == 0.0 else round(value, 12)
        return int(value) if value.is_integer() else value
    if isinstance(value, tuple):
        return [_semantic_value(row) for row in value]
    if isinstance(value, list):
        return [_semantic_value(row) for row in value]
    if isinstance(value, Mapping):
        return {str(key): _semantic_value(row) for key, row in sorted(value.items(), key=lambda item: str(item[0]))}
    raise TypeError('semantic values must be finite JSON-compatible values')


def semantic_vector_key(values: Sequence[object]) -> str:
    return json.dumps(
        [_semantic_value(value) for value in values],
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
        allow_nan=False,
    )


def derive_anchor_values(need: OperatorInventionNeed, *, min_count: int = 2) -> tuple[float, ...]:
    if not isinstance(need, OperatorInventionNeed):
        raise TypeError('need must be OperatorInventionNeed')
    min_count = int(min_count)
    if min_count < 1:
        raise ValueError('min_count must be positive')
    values: set[float] = set()
    for raw in need.constants:
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            continue
        value = float(raw)
        if math.isfinite(value):
            values.add(0.0 if value == 0.0 else value)
    anchors = tuple(sorted(values))
    if len(anchors) < min_count:
        raise ValueError(f'at least {min_count} distinct finite numeric downstream constants are required')
    return anchors


def _equivalent(actual: object, expected: object) -> bool:
    if (
        isinstance(actual, (int, float)) and not isinstance(actual, bool)
        and isinstance(expected, (int, float)) and not isinstance(expected, bool)
    ):
        try:
            return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)
        except (TypeError, ValueError, OverflowError):
            return False
    return actual == expected


def _oracle_value(oracle: Callable[[Mapping[str, object]], object], context: Mapping[str, object]) -> object:
    value = oracle(dict(context))
    semantic_vector_key((value,))
    return value


def _children(expr: Expr) -> tuple[Expr, ...]:
    if isinstance(expr, Unary):
        return (expr.arg,)
    if isinstance(expr, Binary):
        return (expr.left, expr.right)
    if isinstance(expr, IfElse):
        return (expr.condition, expr.when_true, expr.when_false)
    if isinstance(expr, AbstractionCall):
        return tuple(expr.args)
    return ()


def _used_abstractions(expr: Expr) -> tuple[str, ...]:
    out: set[str] = set()

    def walk(node: Expr) -> None:
        if isinstance(node, AbstractionCall):
            out.add(node.abstraction_id)
        for child in _children(node):
            walk(child)

    walk(expr)
    return tuple(sorted(out))


def _used_fields(expr: Expr) -> tuple[str, ...]:
    out: set[str] = set()

    def walk(node: Expr) -> None:
        if isinstance(node, Field):
            out.add(node.name)
        for child in _children(node):
            walk(child)

    walk(expr)
    return tuple(sorted(out))


def _project_canonical_context(
    schema: PositionalSchema,
    context: Mapping[str, object],
    free_positions: tuple[int, ...],
) -> dict[str, object]:
    canonical = schema.to_canonical_context(context)
    return {schema.canonical_fields[position]: canonical[schema.canonical_fields[position]] for position in free_positions}


@dataclass(frozen=True, slots=True)
class SemanticProbeHit:
    expression: Expr
    expression_digest: str
    used_abstraction_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SemanticProbeIndex:
    free_positions: tuple[int, ...]
    by_semantics: Mapping[str, SemanticProbeHit]
    candidates_considered: int
    search_evaluations: int
    semantic_duplicates: int
    exhausted: bool


@dataclass(frozen=True, slots=True)
class BudgetedInterventionCandidateReceipt:
    intervention: InterventionSpec
    passed: bool
    reason: str
    target_distinct_outputs: int = 0
    probe_expression: Expr | None = None
    used_abstraction_ids: tuple[str, ...] = ()
    probe_validation_cases: int = 0
    probe_validation_exact: int = 0
    seeded_downstream_passed: bool = False
    seeded_downstream_candidates_considered: int = 0
    seeded_downstream_expression: Expr | None = None


@dataclass(frozen=True, slots=True)
class BudgetedInterventionDiscoveryReceipt:
    passed: bool
    selected: BudgetedInterventionCandidateReceipt | None
    candidates: tuple[BudgetedInterventionCandidateReceipt, ...]
    derived_anchor_values: tuple[float, ...]
    no_seed_passed: bool
    no_seed_candidates_considered: int
    probe_index_candidates_considered: int
    seeded_downstream_candidates_considered: int
    total_synthesis_candidates: int
    max_total_synthesis_candidates: int
    oracle_calls: int
    projection_index_builds: int
    projection_index_reuses: int
    downstream_cache_hits: int
    reason: str
    trainable_parameter_count: int = 0


def _evaluate_vector(
    expression: Expr,
    contexts: Sequence[Mapping[str, object]],
    vocabulary: CognitiveVocabulary,
) -> tuple[tuple[object, ...] | None, int]:
    values: list[object] = []
    evaluations = 0
    for context in contexts:
        try:
            value = evaluate_with_vocabulary(expression, context, vocabulary)
            semantic_vector_key((value,))
        except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            return None, evaluations + 1
        values.append(value)
        evaluations += 1
    return tuple(values), evaluations


class _SemanticProbeSearchState:
    """Resumable, fair learned-vocabulary enumeration for one free-position projection."""

    def __init__(
        self,
        *,
        free_positions: tuple[int, ...],
        canonical_fields: tuple[str, ...],
        projected_contexts: Sequence[Mapping[str, object]],
        vocabulary: CognitiveVocabulary,
        max_depth: int,
        max_candidates: int,
    ) -> None:
        if not free_positions:
            raise ValueError('free_positions must be non-empty')
        if int(max_depth) < 1 or int(max_candidates) < 1:
            raise ValueError('semantic probe search budgets are invalid')
        self.free_positions = free_positions
        self.canonical_fields = canonical_fields
        self.contexts = tuple(dict(row) for row in projected_contexts)
        self.vocabulary = vocabulary
        self.max_depth = int(max_depth)
        self.max_candidates = int(max_candidates)
        self.atoms = tuple(Field(canonical_fields[position]) for position in free_positions)
        self.abstractions = tuple(sorted(vocabulary.abstractions(), key=lambda row: row.abstraction_id))
        self.by_semantics: dict[str, SemanticProbeHit] = {}
        self.seen_expr: set[str] = set()
        self.frontier_by_depth: dict[int, list[Expr]] = {}
        self.candidates_considered = 0
        self.search_evaluations = 0
        self.semantic_duplicates = 0
        self.atom_index = 0
        self.depth = 1
        self.active: deque[tuple[str, object]] = deque()
        self._depth_started = False
        self.exhausted = False

    def _add(self, expr: Expr) -> tuple[str | None, bool]:
        if self.candidates_considered >= self.max_candidates:
            self.exhausted = True
            return None, False
        digest = expr_digest(expr)
        if digest in self.seen_expr:
            return None, False
        self.seen_expr.add(digest)
        self.candidates_considered += 1
        vector, count = _evaluate_vector(expr, self.contexts, self.vocabulary)
        self.search_evaluations += count
        if vector is None:
            if self.candidates_considered >= self.max_candidates:
                self.exhausted = True
            return None, True
        key = semantic_vector_key(vector)
        hit = SemanticProbeHit(expr, digest, _used_abstractions(expr))
        existing = self.by_semantics.get(key)
        if existing is None:
            self.by_semantics[key] = hit
            self.frontier_by_depth.setdefault(expr.depth, []).append(expr)
        else:
            self.semantic_duplicates += 1
            old_rank = (existing.expression.cost, existing.expression.depth, existing.expression_digest)
            new_rank = (expr.cost, expr.depth, digest)
            if new_rank < old_rank:
                self.by_semantics[key] = hit
        if self.candidates_considered >= self.max_candidates:
            self.exhausted = True
        return key, True

    def _start_depth(self) -> bool:
        if self.depth > self.max_depth:
            self.exhausted = True
            return False
        if self.depth == 1:
            for abstraction in self.abstractions:
                self.active.append((
                    abstraction.abstraction_id,
                    iter(itertools.product(self.atoms, repeat=abstraction.parameter_count)),
                ))
        else:
            frontier = tuple(sorted(
                self.frontier_by_depth.get(self.depth - 1, ()),
                key=lambda expr: (-len(_used_fields(expr)), expr.cost, expr_digest(expr)),
            ))
            if not frontier:
                self.exhausted = True
                return False
            for abstraction in self.abstractions:
                rows = []
                for complex_index in range(abstraction.parameter_count):
                    pools = [self.atoms] * abstraction.parameter_count
                    pools[complex_index] = frontier
                    rows.append(itertools.product(*pools))
                self.active.append((
                    abstraction.abstraction_id,
                    iter(itertools.chain.from_iterable(rows)),
                ))
        self._depth_started = True
        return True

    def advance_until(self, target_key: str, *, max_new_candidates: int) -> SemanticProbeHit | None:
        if target_key in self.by_semantics:
            return self.by_semantics[target_key]
        max_new_candidates = int(max_new_candidates)
        if max_new_candidates < 1 or self.exhausted:
            return None
        start = self.candidates_considered
        while self.candidates_considered - start < max_new_candidates and not self.exhausted:
            if self.atom_index < len(self.atoms):
                key, considered = self._add(self.atoms[self.atom_index])
                self.atom_index += 1
                if key == target_key:
                    return self.by_semantics[target_key]
                if not considered:
                    continue
                continue

            if not self._depth_started:
                if not self._start_depth():
                    break
            if not self.active:
                self.depth += 1
                self._depth_started = False
                continue

            abstraction_id, generator = self.active.popleft()
            try:
                args = next(generator)
            except StopIteration:
                continue
            self.active.append((abstraction_id, generator))
            expr = AbstractionCall(abstraction_id, tuple(args))
            if expr.depth != self.depth:
                continue
            key, _considered = self._add(expr)
            if key == target_key:
                return self.by_semantics[target_key]

        return self.by_semantics.get(target_key)

    def snapshot(self) -> SemanticProbeIndex:
        return SemanticProbeIndex(
            self.free_positions,
            dict(self.by_semantics),
            self.candidates_considered,
            self.search_evaluations,
            self.semantic_duplicates,
            self.exhausted,
        )


