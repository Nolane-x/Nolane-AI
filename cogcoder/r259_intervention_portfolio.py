from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r256_operator_dsl import Expr, expr_digest
from .r256_operator_invention import OperatorExample, OperatorInventionNeed
from .r257_vocabulary import CognitiveVocabulary, evaluate_with_vocabulary
from .r258_intervention_discovery import PositionalSchema, discover_causal_intervention
from .r259_exposure_probe import ProbeBudget, discover_verified_subgoal


class PortfolioOracleBudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PortfolioBudget:
    max_shared_oracle_calls: int = 1400
    exposure_max_oracle_calls: int = 900
    exposure_max_interventions: int = 40
    exposure_subgoal_max_depth: int = 2
    exposure_subgoal_max_candidates: int = 12000
    exposure_max_cegis_rounds: int = 2
    positional_intervention_arity: int = 2
    positional_probe_max_depth: int = 2
    positional_probe_max_candidates: int = 12000

    def __post_init__(self) -> None:
        positive = (
            'max_shared_oracle_calls', 'exposure_max_oracle_calls', 'exposure_max_interventions',
            'exposure_subgoal_max_candidates', 'positional_intervention_arity',
            'positional_probe_max_candidates',
        )
        for name in positive:
            if int(getattr(self, name)) < 1:
                raise ValueError(f'{name} must be positive')
        nonnegative = ('exposure_subgoal_max_depth', 'exposure_max_cegis_rounds', 'positional_probe_max_depth')
        for name in nonnegative:
            if int(getattr(self, name)) < 0:
                raise ValueError(f'{name} must be non-negative')
        for name in positive + nonnegative:
            object.__setattr__(self, name, int(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class PortfolioReceipt:
    passed: bool
    expression: Expr | None
    selected_method: str
    exposure_passed: bool
    positional_passed: bool
    methods_agree: bool
    challenge_exact: int
    challenge_cases: int
    oracle_calls: int
    exposure_synthesis_candidates: int
    positional_synthesis_candidates: int
    total_synthesis_candidates: int
    exposure_schema_id: str
    reason: str
    trainable_parameter_count: int = 0


class _SharedOracle:
    def __init__(self, oracle: Callable[[Mapping[str, object]], object], max_calls: int) -> None:
        if not callable(oracle):
            raise TypeError('oracle must be callable')
        self.oracle = oracle
        self.max_calls = int(max_calls)
        self.calls = 0
        self.budget_exhausted = False
        self._cache: dict[str, object] = {}

    @staticmethod
    def _key(context: Mapping[str, object]) -> str:
        try:
            return json.dumps(dict(context), sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise TypeError('oracle contexts must be finite JSON-compatible mappings') from exc

    @staticmethod
    def _validate(value: object) -> object:
        try:
            json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise TypeError('oracle outputs must be finite JSON-compatible values') from exc
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('oracle outputs must be finite')
        return value

    def __call__(self, context: Mapping[str, object]) -> object:
        key = self._key(context)
        if key in self._cache:
            return self._cache[key]
        if self.calls >= self.max_calls:
            self.budget_exhausted = True
            raise PortfolioOracleBudgetExceeded('shared oracle budget exhausted')
        self.calls += 1
        value = self._validate(self.oracle(dict(context)))
        self._cache[key] = value
        return value


def _equivalent(left: object, right: object) -> bool:
    if (
        isinstance(left, (int, float)) and not isinstance(left, bool)
        and isinstance(right, (int, float)) and not isinstance(right, bool)
    ):
        try:
            return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
        except (TypeError, ValueError, OverflowError):
            return False
    return left == right


def _canonical_need(need: OperatorInventionNeed, schema: PositionalSchema) -> OperatorInventionNeed:
    return OperatorInventionNeed(
        need.objective,
        schema.canonical_fields,
        need.output_field,
        constants=need.constants,
        max_depth=need.max_depth,
        max_candidates=need.max_candidates,
    )


def _canonical_examples(rows: Sequence[OperatorExample], schema: PositionalSchema) -> tuple[OperatorExample, ...]:
    return tuple(OperatorExample(row.name, schema.to_canonical_context(row.context), row.expected) for row in rows)


def _canonical_contexts(rows: Sequence[Mapping[str, object]], schema: PositionalSchema) -> tuple[dict[str, object], ...]:
    return tuple(schema.to_canonical_context(row) for row in rows)


def _external_context(context: Mapping[str, object], schema: PositionalSchema) -> dict[str, object]:
    missing = [field for field in schema.canonical_fields if field not in context]
    if missing:
        raise KeyError(f'missing canonical fields: {missing}')
    return {
        external: context[canonical]
        for external, canonical in zip(schema.field_names, schema.canonical_fields, strict=True)
    }


def _exposure_candidates(receipt: object) -> int:
    attempts = tuple(getattr(receipt, 'attempts', ()))
    return sum(
        int(getattr(row, 'subgoal_candidates_considered', 0))
        + int(getattr(row, 'full_candidates_considered', 0))
        for row in attempts
    )


def _exposure_schema_id(receipt: object) -> str:
    abstraction_id = str(getattr(receipt, 'abstraction_id', ''))
    target = int(getattr(receipt, 'target_param_index', -1))
    fixed = tuple((str(field), value) for field, value in getattr(receipt, 'fixed_field_values', ()))
    payload = json.dumps(
        {'abstraction_id': abstraction_id, 'target_param_index': target, 'fixed': fixed},
        sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False,
    )
    return f'exposure.{hashlib.sha256(payload.encode("utf-8")).hexdigest()}' if abstraction_id else ''


def _common_challenge(
    expression: Expr | None,
    challenge_contexts: Sequence[Mapping[str, object]],
    vocabulary: CognitiveVocabulary,
    oracle: _SharedOracle,
) -> tuple[bool, int]:
    if expression is None:
        return False, 0
    exact = 0
    try:
        for context in challenge_contexts:
            expected = oracle(context)
            try:
                actual = evaluate_with_vocabulary(expression, context, vocabulary)
            except (KeyError, TypeError, ValueError, OverflowError):
                return False, exact
            if not _equivalent(actual, expected):
                return False, exact
            exact += 1
    except PortfolioOracleBudgetExceeded:
        return False, exact
    return exact == len(challenge_contexts), exact


def discover_intervention_portfolio(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    anchor_values: Sequence[float],
    training_examples: Sequence[OperatorExample],
    challenge_contexts: Sequence[Mapping[str, object]],
    vocabulary: CognitiveVocabulary,
    downstream_need: OperatorInventionNeed,
    *,
    strategy: str = 'robust',
    enable_exposure: bool = True,
    enable_positional: bool = True,
    budget: PortfolioBudget = PortfolioBudget(),
) -> PortfolioReceipt:
    if strategy not in {'fallback', 'robust'}:
        raise ValueError("strategy must be 'fallback' or 'robust'")
    if not isinstance(vocabulary, CognitiveVocabulary):
        raise TypeError('vocabulary must be CognitiveVocabulary')
    if not isinstance(downstream_need, OperatorInventionNeed):
        raise TypeError('downstream_need must be OperatorInventionNeed')
    if not training_examples:
        raise ValueError('training_examples must be non-empty')
    if not challenge_contexts:
        raise ValueError('challenge_contexts must be non-empty')
    if not all(isinstance(row, OperatorExample) for row in training_examples):
        raise TypeError('training_examples must contain OperatorExample values')
    if not all(isinstance(row, Mapping) for row in challenge_contexts):
        raise TypeError('challenge_contexts must contain mappings')
    if not isinstance(budget, PortfolioBudget):
        raise TypeError('budget must be PortfolioBudget')
    if not enable_exposure and not enable_positional:
        return PortfolioReceipt(
            False, None, '', False, False, False, 0, len(challenge_contexts), 0,
            0, 0, 0, '', 'no_enabled_discovery_engine', 0,
        )

    schema = PositionalSchema(tuple(map(str, ordered_field_names)))
    if set(schema.field_names) != set(downstream_need.field_names):
        raise ValueError('ordered_field_names must match downstream need fields')
    shared = _SharedOracle(oracle, budget.max_shared_oracle_calls)

    exposure_expression: Expr | None = None
    exposure_common_passed = False
    exposure_exact = 0
    exposure_candidates = 0
    exposure_schema_id = ''

    if enable_exposure:
        canonical_need = _canonical_need(downstream_need, schema)
        canonical_train = _canonical_examples(training_examples, schema)
        canonical_challenge = _canonical_contexts(challenge_contexts, schema)

        def canonical_oracle(context: Mapping[str, object]) -> object:
            return shared(_external_context(context, schema))

        exposure_receipt = discover_verified_subgoal(
            canonical_need,
            canonical_train,
            canonical_challenge,
            vocabulary,
            canonical_oracle,
            budget=ProbeBudget(
                max_oracle_calls=min(budget.exposure_max_oracle_calls, budget.max_shared_oracle_calls),
                max_interventions=budget.exposure_max_interventions,
                subgoal_max_depth=budget.exposure_subgoal_max_depth,
                subgoal_max_candidates=budget.exposure_subgoal_max_candidates,
                max_cegis_rounds=budget.exposure_max_cegis_rounds,
            ),
        )
        exposure_candidates = _exposure_candidates(exposure_receipt)
        exposure_schema_id = _exposure_schema_id(exposure_receipt)
        if exposure_receipt.passed and exposure_receipt.full_expression is not None:
            exposure_expression = schema.externalize_expr(exposure_receipt.full_expression)
            exposure_common_passed, exposure_exact = _common_challenge(
                exposure_expression, challenge_contexts, vocabulary, shared,
            )

        if strategy == 'fallback' and exposure_common_passed:
            return PortfolioReceipt(
                True, exposure_expression, 'exposure', True, False, False,
                exposure_exact, len(challenge_contexts), shared.calls,
                exposure_candidates, 0, exposure_candidates, exposure_schema_id,
                'canonicalized_exposure_verified', 0,
            )
        if shared.budget_exhausted:
            return PortfolioReceipt(
                False, None, '', exposure_common_passed, False, False,
                exposure_exact, len(challenge_contexts), shared.calls,
                exposure_candidates, 0, exposure_candidates, exposure_schema_id,
                'shared_oracle_budget_exhausted', 0,
            )

    positional_expression: Expr | None = None
    positional_common_passed = False
    positional_exact = 0
    positional_candidates = 0

    if enable_positional:
        try:
            positional_receipt = discover_causal_intervention(
                shared,
                schema.field_names,
                anchor_values,
                tuple(row.context for row in training_examples),
                challenge_contexts,
                vocabulary,
                downstream_need,
                training_examples,
                intervention_arity=budget.positional_intervention_arity,
                probe_max_depth=budget.positional_probe_max_depth,
                probe_max_candidates=budget.positional_probe_max_candidates,
            )
            positional_candidates = int(positional_receipt.synthesis_candidates_considered)
            selected = positional_receipt.selected
            if positional_receipt.passed and selected is not None and selected.seeded_downstream_expression is not None:
                positional_expression = selected.seeded_downstream_expression
                positional_common_passed, positional_exact = _common_challenge(
                    positional_expression, challenge_contexts, vocabulary, shared,
                )
        except PortfolioOracleBudgetExceeded:
            positional_common_passed = False
        if shared.budget_exhausted and not positional_common_passed and not exposure_common_passed:
            return PortfolioReceipt(
                False, None, '', exposure_common_passed, positional_common_passed, False,
                max(exposure_exact, positional_exact), len(challenge_contexts), shared.calls,
                exposure_candidates, positional_candidates, exposure_candidates + positional_candidates,
                exposure_schema_id, 'shared_oracle_budget_exhausted', 0,
            )

    total_candidates = exposure_candidates + positional_candidates

    if strategy == 'fallback':
        if positional_common_passed:
            return PortfolioReceipt(
                True, positional_expression, 'positional', exposure_common_passed, True, False,
                positional_exact, len(challenge_contexts), shared.calls,
                exposure_candidates, positional_candidates, total_candidates, exposure_schema_id,
                'positional_fallback_verified', 0,
            )
        return PortfolioReceipt(
            False, None, '', exposure_common_passed, positional_common_passed, False,
            max(exposure_exact, positional_exact), len(challenge_contexts), shared.calls,
            exposure_candidates, positional_candidates, total_candidates, exposure_schema_id,
            'no_portfolio_candidate_passed_common_challenge', 0,
        )

    methods_agree = False
    if exposure_common_passed and positional_common_passed and exposure_expression is not None and positional_expression is not None:
        methods_agree = True
        for context in challenge_contexts:
            try:
                left = evaluate_with_vocabulary(exposure_expression, context, vocabulary)
                right = evaluate_with_vocabulary(positional_expression, context, vocabulary)
            except (KeyError, TypeError, ValueError, OverflowError):
                methods_agree = False
                break
            if not _equivalent(left, right):
                methods_agree = False
                break
        if methods_agree:
            ranked = sorted(
                (exposure_expression, positional_expression),
                key=lambda expr: (expr.cost, expr.depth, expr_digest(expr)),
            )
            return PortfolioReceipt(
                True, ranked[0], 'consensus', True, True, True,
                len(challenge_contexts), len(challenge_contexts), shared.calls,
                exposure_candidates, positional_candidates, total_candidates, exposure_schema_id,
                'cross_mechanism_consensus', 0,
            )

    if exposure_common_passed:
        return PortfolioReceipt(
            True, exposure_expression, 'exposure', True, positional_common_passed, False,
            exposure_exact, len(challenge_contexts), shared.calls,
            exposure_candidates, positional_candidates, total_candidates, exposure_schema_id,
            'single_verified_exposure', 0,
        )
    if positional_common_passed:
        return PortfolioReceipt(
            True, positional_expression, 'positional', False, True, False,
            positional_exact, len(challenge_contexts), shared.calls,
            exposure_candidates, positional_candidates, total_candidates, exposure_schema_id,
            'single_verified_positional', 0,
        )
    return PortfolioReceipt(
        False, None, '', False, False, False,
        max(exposure_exact, positional_exact), len(challenge_contexts), shared.calls,
        exposure_candidates, positional_candidates, total_candidates, exposure_schema_id,
        'no_portfolio_candidate_passed_common_challenge', 0,
    )


__all__ = [
    'PortfolioBudget', 'PortfolioReceipt', 'PortfolioOracleBudgetExceeded',
    'discover_intervention_portfolio',
]
