from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r253_external_cognition import CognitiveOperatorRegistry, CognitiveOperatorSpec, ExternalWorkingState
from .r255_lifecycle import ProcedureLifecycleLedger
from .r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary, enumerate_expressions, evaluate_expr, expr_digest


def _nonempty(value: str, name: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f'{name} must be non-empty')
    return value


def _canonical_value(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TypeError('example outputs must be JSON-compatible values') from exc


@dataclass(frozen=True, slots=True)
class OperatorExample:
    name: str
    context: Mapping[str, object]
    expected: object

    def __post_init__(self) -> None:
        _nonempty(self.name, 'example name')
        if not isinstance(self.context, Mapping):
            raise TypeError('example context must be a mapping')
        _canonical_value(self.expected)


@dataclass(frozen=True, slots=True)
class OperatorInventionNeed:
    objective: str
    field_names: tuple[str, ...]
    output_field: str
    constants: tuple[object, ...] = (0, 1, -1, True, False, '')
    max_depth: int = 2
    max_candidates: int = 5000

    def __post_init__(self) -> None:
        _nonempty(self.objective, 'objective')
        output = _nonempty(self.output_field, 'output_field')
        fields = tuple(sorted({_nonempty(row, 'field name') for row in self.field_names}))
        if not fields:
            raise ValueError('field_names must be non-empty')
        if output in fields:
            raise ValueError('output_field must not shadow an input field')
        if int(self.max_depth) < 0:
            raise ValueError('max_depth must be non-negative')
        if int(self.max_candidates) < 1:
            raise ValueError('max_candidates must be positive')
        object.__setattr__(self, 'field_names', fields)
        object.__setattr__(self, 'output_field', output)
        object.__setattr__(self, 'constants', tuple(self.constants))
        object.__setattr__(self, 'max_depth', int(self.max_depth))
        object.__setattr__(self, 'max_candidates', int(self.max_candidates))


@dataclass(frozen=True, slots=True)
class InventedOperatorCandidate:
    expression: Expr
    expression_digest: str
    training_examples: int
    search_evaluations: int


@dataclass(frozen=True, slots=True)
class OperatorChallengeResult:
    example_name: str
    expected: object
    actual: object
    passed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class OperatorInventionReceipt:
    need: OperatorInventionNeed
    passed: bool
    candidate: InventedOperatorCandidate | None
    challenge_results: tuple[OperatorChallengeResult, ...]
    cegis_rounds: int
    training_examples_used: int
    search_evaluations: int
    reason: str


@dataclass(frozen=True, slots=True)
class PromotedInventedOperator:
    operator: CognitiveOperatorSpec
    registry: CognitiveOperatorRegistry
    expression_digest: str
    expression: Expr
    output_field: str


@dataclass(frozen=True, slots=True)
class LiveInventedOperatorReceipt:
    success: bool
    rolled_back: bool
    operator_id: str
    expression_digest: str
    reason: str
    output: object = None


def _candidate_rank(expr: Expr) -> tuple[int, int, str]:
    # Prefer simpler expressions. Constants deliberately precede fields at equal cost so
    # underspecified training sets can expose a real CEGIS refinement in tests/benchmarks.
    kind = 0 if isinstance(expr, Const) else 1 if isinstance(expr, Field) else 2 if isinstance(expr, Unary) else 3 if isinstance(expr, Binary) else 4
    return (expr.cost, kind, expr_digest(expr))


def _evaluate_vector(expr: Expr, examples: Sequence[OperatorExample]) -> tuple[tuple[object, ...] | None, int]:
    out: list[object] = []
    evaluations = 0
    for row in examples:
        try:
            value = evaluate_expr(expr, row.context)
            _canonical_value(value)
        except (KeyError, TypeError, ValueError, OverflowError):
            return None, evaluations + 1
        evaluations += 1
        out.append(value)
    return tuple(out), evaluations


class AutonomousOperatorInventionEngine:
    """Bounded zero-parameter invention of pure operators from public examples."""

    trainable_parameter_count = 0

    def __init__(self, parent_registry: CognitiveOperatorRegistry, lifecycle: ProcedureLifecycleLedger) -> None:
        self.parent_registry = parent_registry
        self.lifecycle = lifecycle
        self._promoted: dict[str, PromotedInventedOperator] = {}

    def _synthesize(self, need: OperatorInventionNeed, examples: Sequence[OperatorExample]) -> tuple[InventedOperatorCandidate | None, int]:
        if not examples:
            raise ValueError('training examples must be non-empty')
        expected = tuple(row.expected for row in examples)
        expressions = enumerate_expressions(
            need.field_names,
            constants=need.constants,
            max_depth=need.max_depth,
            max_candidates=need.max_candidates,
        )
        semantic_seen: set[str] = set()
        evaluations = 0
        for expr in sorted(expressions, key=_candidate_rank):
            vector, count = _evaluate_vector(expr, examples)
            evaluations += count
            if vector is None:
                continue
            key = _canonical_value(list(vector))
            if key in semantic_seen:
                continue
            semantic_seen.add(key)
            if vector == expected:
                return InventedOperatorCandidate(expr, expr_digest(expr), len(examples), evaluations), evaluations
        return None, evaluations

    @staticmethod
    def _challenge(candidate: InventedOperatorCandidate, examples: Sequence[OperatorExample]) -> tuple[OperatorChallengeResult, ...]:
        rows: list[OperatorChallengeResult] = []
        for row in examples:
            try:
                actual = evaluate_expr(candidate.expression, row.context)
                passed = actual == row.expected
                reason = 'passed' if passed else 'output_mismatch'
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                actual = None
                passed = False
                reason = f'evaluation_error:{type(exc).__name__}:{exc}'
            rows.append(OperatorChallengeResult(row.name, row.expected, actual, passed, reason))
        return tuple(rows)

    def synthesize_and_challenge(
        self,
        need: OperatorInventionNeed,
        training_examples: Sequence[OperatorExample],
        challenge_examples: Sequence[OperatorExample],
        *,
        max_cegis_rounds: int = 2,
    ) -> OperatorInventionReceipt:
        if not challenge_examples:
            raise ValueError('challenge suite must be non-empty')
        if int(max_cegis_rounds) < 0:
            raise ValueError('max_cegis_rounds must be non-negative')
        working = list(training_examples)
        if not working:
            raise ValueError('training examples must be non-empty')
        total_evaluations = 0
        rounds = 0

        while True:
            candidate, evaluations = self._synthesize(need, tuple(working))
            total_evaluations += evaluations
            if candidate is None:
                return OperatorInventionReceipt(
                    need, False, None, (), rounds, len(working), total_evaluations, 'no_candidate_within_budget',
                )
            fingerprint = candidate.expression_digest
            current = self.lifecycle.state(fingerprint)
            if current == 'unseen':
                self.lifecycle.transition(fingerprint, 'candidate', reason='expression_synthesized')
                current = 'candidate'
            if current != 'candidate':
                return OperatorInventionReceipt(
                    need, False, candidate, (), rounds, len(working), total_evaluations,
                    f'lifecycle_not_candidate:{current}',
                )
            self.lifecycle.transition(fingerprint, 'probation', reason='independent_challenge_required')
            results = self._challenge(candidate, challenge_examples)
            failure = next((row for row in results if not row.passed), None)
            if failure is None:
                return OperatorInventionReceipt(
                    need, True, candidate, results, rounds, len(working), total_evaluations, 'independent_challenges_passed',
                )

            self.lifecycle.transition(
                fingerprint,
                'quarantined',
                reason=f'challenge_failed:{failure.example_name}:{failure.reason}',
            )
            if rounds >= int(max_cegis_rounds):
                return OperatorInventionReceipt(
                    need, False, candidate, results, rounds, len(working), total_evaluations,
                    f'challenge_failed:{failure.example_name}:{failure.reason}',
                )
            working.append(OperatorExample(
                f'cegis:{failure.example_name}',
                dict(next(row.context for row in challenge_examples if row.name == failure.example_name)),
                failure.expected,
            ))
            rounds += 1

    def promote(self, receipt: OperatorInventionReceipt) -> PromotedInventedOperator:
        if not receipt.passed or receipt.candidate is None:
            raise ValueError('cannot promote failed invention')
        candidate = receipt.candidate
        if self.lifecycle.state(candidate.expression_digest) != 'probation':
            raise ValueError('invention must be in probation before promotion')
        operator_id = f'invented.{candidate.expression_digest[:20]}'
        expression = candidate.expression
        need = receipt.need

        def executor(state, _snapshot, _signal):
            value = evaluate_expr(expression, state.context)
            return {
                'success': True,
                'updates': {need.output_field: value},
                'provides': {need.output_field},
                'evidence': (f'invented-expression:{candidate.expression_digest}',),
            }

        operator = CognitiveOperatorSpec(
            operator_id=operator_id,
            family='invented',
            tags=frozenset({'invented', 'pure', 'r256'}),
            requires=frozenset(need.field_names),
            provides=frozenset({need.output_field}),
            cost=float(candidate.expression.cost),
            risk=0.0,
            side_effect_class='pure',
            version='r256-v1',
            source_uri=f'nolane://invented/{candidate.expression_digest}',
            executor=executor,
        )
        child = CognitiveOperatorRegistry(self.parent_registry.operators())
        child.register(operator)
        self.lifecycle.transition(candidate.expression_digest, 'promoted', reason='independent_challenges_passed')
        promoted = PromotedInventedOperator(operator, child, candidate.expression_digest, expression, need.output_field)
        self._promoted[operator_id] = promoted
        return promoted

    @staticmethod
    def _restore_state(target: ExternalWorkingState, source: ExternalWorkingState) -> None:
        target.context.clear(); target.context.update(copy.deepcopy(source.context))
        target.capabilities.clear(); target.capabilities.update(source.capabilities)
        target.evidence[:] = list(source.evidence)
        target.hypotheses[:] = list(source.hypotheses)
        target.subgoals[:] = list(source.subgoals)
        target.representation_id = source.representation_id
        target.notes[:] = list(source.notes)

    def execute_promoted(self, operator_id: str, state: ExternalWorkingState) -> LiveInventedOperatorReceipt:
        operator_id = str(operator_id)
        promoted = self._promoted.get(operator_id)
        if promoted is None or self.lifecycle.state(promoted.expression_digest) != 'promoted':
            return LiveInventedOperatorReceipt(False, False, operator_id, '', 'operator_not_promoted')
        before = copy.deepcopy(state)
        try:
            missing = set(promoted.operator.requires).difference(state.context)
            if missing:
                raise KeyError(f'missing input fields: {sorted(missing)}')
            raw = dict(promoted.operator.executor(state, None, None))
            if not bool(raw.get('success', False)):
                raise ValueError(str(raw.get('reason', 'invented_operator_failed')))
            updates = raw.get('updates', {})
            if not isinstance(updates, Mapping):
                raise TypeError('operator updates must be a mapping')
            if set(updates) != {promoted.output_field}:
                raise ValueError('invented operator violated single-output contract')
            state.context.update(updates)
            state.capabilities.update(promoted.operator.provides)
            state.capabilities.update(map(str, raw.get('provides', ())))
            state.evidence.extend(map(str, raw.get('evidence', ())))
            return LiveInventedOperatorReceipt(
                True, False, operator_id, promoted.expression_digest, 'executed', updates[promoted.output_field],
            )
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            self._restore_state(state, before)
            self.lifecycle.transition(promoted.expression_digest, 'rolled_back', reason=f'live_failure:{type(exc).__name__}:{exc}')
            return LiveInventedOperatorReceipt(
                False, True, operator_id, promoted.expression_digest,
                f'live_failure:{type(exc).__name__}:{exc}',
            )


__all__ = [
    'OperatorExample', 'OperatorInventionNeed', 'InventedOperatorCandidate',
    'OperatorChallengeResult', 'OperatorInventionReceipt', 'PromotedInventedOperator',
    'LiveInventedOperatorReceipt', 'AutonomousOperatorInventionEngine',
]
