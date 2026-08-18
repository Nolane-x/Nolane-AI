from __future__ import annotations

from dataclasses import replace
from typing import Callable, Mapping, Sequence

from .r256_operator_dsl import evaluate_expr
from .r256_operator_invention import OperatorInventionNeed
from .r258_intervention_discovery import PositionalSchema
from .r259_semantic_index_core import semantic_vector_key
from ._r266_contextual_composition_core import (
    ContextualCompositionCandidate,
    ContextualCompositionProgram,
    ContextualCompositionStructureReceipt,
    ContextualCompositionSynthesisReceipt,
    ContextualExpressionReceipt,
    ContextualInterventionProfile,
    _equivalent,
    discover_contextual_composition_structure,
    synthesize_contextual_expression,
    synthesize_contextual_composition_program as _core_synthesize_contextual_composition_program,
)


def _context_key(schema: PositionalSchema, context: Mapping[str, object]) -> str:
    canonical = schema.to_canonical_context(context)
    return semantic_vector_key(tuple(canonical[field] for field in schema.canonical_fields))


def synthesize_contextual_composition_program(
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    program_need: OperatorInventionNeed,
    discovery_contexts: Sequence[Mapping[str, object]],
    validation_contexts: Sequence[Mapping[str, object]],
    *,
    terminal_contexts: Sequence[Mapping[str, object]],
    context_validator: Callable[[Mapping[str, object]], bool] | None = None,
    intervention_arity: int = 1,
    composition_constants: Sequence[object] = (0.0,),
    composition_max_depth: int = 2,
    composition_max_candidates_per_pair: int = 12000,
    max_composition_candidates_total: int = 120000,
    probe_constants: Sequence[object] = (0.0,),
    probe_max_depth: int = 3,
    probe_max_candidates: int = 20000,
) -> ContextualCompositionSynthesisReceipt:
    """Synthesize then require a disjoint terminal verification set.

    The inherited contextual core uses discovery plus validation evidence to
    choose a structure and uses validation evidence to validate synthesized
    probe expressions. R2.66 therefore does not grant terminal authority to
    that internal success receipt. A separate, non-empty, exact-context-disjoint
    ``terminal_contexts`` set is mandatory before this public API can return
    ``passed=True``.
    """
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    if not isinstance(program_need, OperatorInventionNeed):
        raise TypeError('program_need must be OperatorInventionNeed')
    if context_validator is not None and not callable(context_validator):
        raise TypeError('context_validator must be callable or None')

    schema = PositionalSchema(tuple(map(str, ordered_field_names)))
    discovery = tuple(dict(row) for row in discovery_contexts)
    validation = tuple(dict(row) for row in validation_contexts)
    terminal = tuple(dict(row) for row in terminal_contexts)
    if not terminal:
        raise ValueError('terminal_contexts must be non-empty')

    learning_keys: set[str] = set()
    for row in (*discovery, *validation):
        learning_keys.add(_context_key(schema, row))
    terminal_keys: set[str] = set()
    for row in terminal:
        key = _context_key(schema, row)
        if key in learning_keys:
            raise ValueError('terminal_contexts must be disjoint from discovery and validation contexts')
        if key in terminal_keys:
            raise ValueError('terminal_contexts must be unique')
        terminal_keys.add(key)
        if context_validator is not None and not bool(context_validator(row)):
            raise ValueError('terminal contexts must satisfy context_validator')

    oracle_calls_total = 0
    queried_keys: set[str] = set()

    def tracked_oracle(context: Mapping[str, object]) -> object:
        nonlocal oracle_calls_total
        queried_keys.add(_context_key(schema, context))
        oracle_calls_total += 1
        return oracle(dict(context))

    internal = _core_synthesize_contextual_composition_program(
        tracked_oracle,
        schema.field_names,
        program_need,
        discovery,
        validation,
        context_validator=context_validator,
        intervention_arity=int(intervention_arity),
        composition_constants=tuple(composition_constants),
        composition_max_depth=int(composition_max_depth),
        composition_max_candidates_per_pair=int(composition_max_candidates_per_pair),
        max_composition_candidates_total=int(max_composition_candidates_total),
        probe_constants=tuple(probe_constants),
        probe_max_depth=int(probe_max_depth),
        probe_max_candidates=int(probe_max_candidates),
    )
    learning_query_keys = frozenset(queried_keys)
    if terminal_keys & learning_query_keys:
        raise ValueError('terminal_contexts must be disjoint from all oracle query inputs used for learning')
    if not internal.passed or internal.expression is None:
        return replace(internal, oracle_calls_total=oracle_calls_total)
    if internal.structure.selected is None or len(internal.probe_expressions) != 2:
        return replace(
            internal,
            passed=False,
            reason='independent_terminal_probe_verification_unavailable',
            oracle_calls_total=oracle_calls_total,
        )

    terminal_probe_exact = 0
    try:
        selected = internal.structure.selected
        for context in terminal:
            for index, spec in enumerate(selected.program.interventions):
                intervened = spec.apply(context, schema.field_names)
                if _context_key(schema, intervened) in learning_query_keys:
                    raise ValueError('terminal_contexts must be disjoint from all oracle query inputs used for learning')
                if context_validator is not None and not bool(context_validator(intervened)):
                    raise ValueError('terminal intervention contexts must satisfy context_validator')
                expected_probe = tracked_oracle(intervened)
                semantic_vector_key((expected_probe,))
                actual_probe = evaluate_expr(internal.probe_expressions[index], context)
                semantic_vector_key((actual_probe,))
                terminal_probe_exact += int(_equivalent(actual_probe, expected_probe))
    except ValueError as exc:
        if 'disjoint' in str(exc):
            raise
        return replace(
            internal,
            passed=False,
            final_validation_cases=len(terminal),
            final_validation_exact=0,
            reason='independent_terminal_probe_verification_error',
            oracle_calls_total=oracle_calls_total,
            terminal_probe_validation_cases=len(terminal),
            terminal_probe_validation_exact=terminal_probe_exact,
        )
    except Exception:
        return replace(
            internal,
            passed=False,
            final_validation_cases=len(terminal),
            final_validation_exact=0,
            reason='independent_terminal_probe_verification_error',
            oracle_calls_total=oracle_calls_total,
            terminal_probe_validation_cases=len(terminal),
            terminal_probe_validation_exact=terminal_probe_exact,
        )

    if terminal_probe_exact != len(terminal) * 2:
        return replace(
            internal,
            passed=False,
            final_validation_cases=len(terminal),
            final_validation_exact=0,
            reason='independent_terminal_probe_verification_failed',
            oracle_calls_total=oracle_calls_total,
            terminal_probe_validation_cases=len(terminal),
            terminal_probe_validation_exact=terminal_probe_exact,
        )

    exact = 0
    try:
        for context in terminal:
            expected = tracked_oracle(context)
            semantic_vector_key((expected,))
            actual = evaluate_expr(internal.expression, context)
            semantic_vector_key((actual,))
            exact += int(_equivalent(actual, expected))
    except Exception:
        return replace(
            internal,
            passed=False,
            final_validation_cases=len(terminal),
            final_validation_exact=exact,
            reason='independent_terminal_verification_error',
            oracle_calls_total=oracle_calls_total,
            terminal_probe_validation_cases=len(terminal),
            terminal_probe_validation_exact=terminal_probe_exact,
        )

    if exact != len(terminal):
        return replace(
            internal,
            passed=False,
            final_validation_cases=len(terminal),
            final_validation_exact=exact,
            reason='independent_terminal_verification_failed',
            oracle_calls_total=oracle_calls_total,
            terminal_probe_validation_cases=len(terminal),
            terminal_probe_validation_exact=terminal_probe_exact,
        )

    return replace(
        internal,
        passed=True,
        final_validation_cases=len(terminal),
        final_validation_exact=exact,
        reason='contextual_program_synthesized_terminally_verified',
        oracle_calls_total=oracle_calls_total,
        terminal_probe_validation_cases=len(terminal),
        terminal_probe_validation_exact=terminal_probe_exact,
    )


__all__ = [
    'ContextualExpressionReceipt',
    'ContextualInterventionProfile',
    'ContextualCompositionProgram',
    'ContextualCompositionCandidate',
    'ContextualCompositionStructureReceipt',
    'ContextualCompositionSynthesisReceipt',
    'synthesize_contextual_expression',
    'discover_contextual_composition_structure',
    'synthesize_contextual_composition_program',
]
