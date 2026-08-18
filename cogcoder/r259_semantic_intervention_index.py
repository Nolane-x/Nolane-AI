from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r256_operator_invention import OperatorExample, OperatorInventionNeed
from .r257_vocabulary import CognitiveVocabulary, evaluate_with_vocabulary
from .r257_vocabulary_synthesis import VocabularySynthesisReceipt, synthesize_with_vocabulary
from .r258_intervention_discovery import InterventionSpec, PositionalSchema, enumerate_interventions
from .r259_semantic_index_core import (
    BudgetedInterventionCandidateReceipt,
    BudgetedInterventionDiscoveryReceipt,
    SemanticProbeHit,
    SemanticProbeIndex,
    _SemanticProbeSearchState,
    _equivalent,
    _oracle_value,
    _project_canonical_context,
    _used_fields,
    derive_anchor_values,
    semantic_vector_key,
)


def _bounded_need(need: OperatorInventionNeed, fields: tuple[str, ...], max_candidates: int) -> OperatorInventionNeed:
    return OperatorInventionNeed(
        need.objective,
        fields,
        need.output_field,
        constants=need.constants,
        max_depth=need.max_depth,
        max_candidates=max(1, int(max_candidates)),
    )


@dataclass(frozen=True, slots=True)
class _ProbeWork:
    ordinal: int
    intervention: InterventionSpec
    free_positions: tuple[int, ...]
    target_key: str
    distinct_outputs: int


def discover_budgeted_intervention(
    *,
    oracle: Callable[[Mapping[str, object]], object],
    ordered_field_names: Sequence[str],
    probe_training_contexts: Sequence[Mapping[str, object]],
    probe_validation_contexts: Sequence[Mapping[str, object]],
    vocabulary: CognitiveVocabulary,
    downstream_need: OperatorInventionNeed,
    downstream_examples: Sequence[OperatorExample],
    intervention_arity: int = 2,
    probe_max_depth: int = 2,
    probe_index_max_candidates_per_projection: int = 1200,
    probe_lookup_slice_candidates: int = 400,
    max_interventions: int = 256,
    max_oracle_calls: int = 4096,
    max_total_synthesis_candidates: int = 15000,
    min_distinct_outputs: int = 2,
    min_seed_cost: int = 3,
    min_seed_fields: int = 2,
) -> BudgetedInterventionDiscoveryReceipt:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    if not isinstance(vocabulary, CognitiveVocabulary):
        raise TypeError('vocabulary must be CognitiveVocabulary')
    if not isinstance(downstream_need, OperatorInventionNeed):
        raise TypeError('downstream_need must be OperatorInventionNeed')
    max_total_synthesis_candidates = int(max_total_synthesis_candidates)
    max_interventions = int(max_interventions)
    max_oracle_calls = int(max_oracle_calls)
    probe_lookup_slice_candidates = int(probe_lookup_slice_candidates)
    if max_total_synthesis_candidates < 1 or max_interventions < 1 or max_oracle_calls < 1:
        raise ValueError('global budgets must be positive')
    if int(probe_index_max_candidates_per_projection) < 1 or int(probe_max_depth) < 1 or probe_lookup_slice_candidates < 1:
        raise ValueError('probe index budgets must be positive')
    if int(min_distinct_outputs) < 2 or int(min_seed_cost) < 1 or int(min_seed_fields) < 1:
        raise ValueError('probe admissibility thresholds are invalid')

    schema = PositionalSchema(tuple(map(str, ordered_field_names)))
    fields = schema.field_names
    canonical_fields = schema.canonical_fields
    if set(fields) != set(downstream_need.field_names):
        raise ValueError('ordered_field_names must match downstream need fields')
    probe_train = tuple(dict(row) for row in probe_training_contexts)
    probe_valid = tuple(dict(row) for row in probe_validation_contexts)
    downstream_examples = tuple(downstream_examples)
    if not probe_train or not probe_valid or not downstream_examples:
        raise ValueError('probe training, probe validation and downstream examples must be non-empty')
    for row in (*probe_train, *probe_valid):
        schema.to_canonical_context(row)
    if not all(isinstance(row, OperatorExample) for row in downstream_examples):
        raise TypeError('downstream_examples must contain OperatorExample values')

    anchors = derive_anchor_values(downstream_need, min_count=int(intervention_arity))
    canonical_examples = tuple(
        OperatorExample(row.name, schema.to_canonical_context(row.context), row.expected)
        for row in downstream_examples
    )

    no_seed_cap = min(downstream_need.max_candidates, max_total_synthesis_candidates)
    no_seed_need = _bounded_need(downstream_need, canonical_fields, no_seed_cap)
    no_seed = synthesize_with_vocabulary(no_seed_need, canonical_examples, vocabulary)
    total_candidates = no_seed.candidates_considered
    if no_seed.passed:
        return BudgetedInterventionDiscoveryReceipt(
            False, None, (), anchors, True, no_seed.candidates_considered,
            0, 0, total_candidates, max_total_synthesis_candidates, 0, 0, 0, 0,
            'downstream_baseline_already_passed', 0,
        )
    if total_candidates >= max_total_synthesis_candidates:
        return BudgetedInterventionDiscoveryReceipt(
            False, None, (), anchors, False, no_seed.candidates_considered,
            0, 0, total_candidates, max_total_synthesis_candidates, 0, 0, 0, 0,
            'global_synthesis_budget_exhausted', 0,
        )

    specs = enumerate_interventions(fields, anchors, arity=int(intervention_arity))[:max_interventions]
    receipt_slots: list[BudgetedInterventionCandidateReceipt | None] = [None] * len(specs)
    work: list[_ProbeWork] = []
    oracle_calls = 0

    # Gather target semantics first. Search scheduling comes later so no intervention
    # can monopolize the synthesis budget merely because its positional digest is early.
    for ordinal, spec in enumerate(specs):
        fixed = {position for position, _value in spec.bindings}
        free_positions = tuple(position for position in range(len(fields)) if position not in fixed)
        if not free_positions:
            receipt_slots[ordinal] = BudgetedInterventionCandidateReceipt(spec, False, 'no_free_probe_fields')
            continue
        if oracle_calls + len(probe_train) > max_oracle_calls:
            break
        outputs: list[object] = []
        invalid = False
        for context in probe_train:
            applied = spec.apply(context, fields)
            try:
                outputs.append(_oracle_value(oracle, applied))
            except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                invalid = True
                oracle_calls += 1
                break
            oracle_calls += 1
        if invalid:
            receipt_slots[ordinal] = BudgetedInterventionCandidateReceipt(spec, False, 'oracle_intervention_invalid')
            continue
        distinct_outputs = len({semantic_vector_key((value,)) for value in outputs})
        if distinct_outputs < int(min_distinct_outputs):
            receipt_slots[ordinal] = BudgetedInterventionCandidateReceipt(
                spec, False, 'degenerate_probe_outputs', target_distinct_outputs=distinct_outputs,
            )
            continue
        work.append(_ProbeWork(ordinal, spec, free_positions, semantic_vector_key(outputs), distinct_outputs))

    states: dict[tuple[int, ...], _SemanticProbeSearchState] = {}
    downstream_cache: dict[str, VocabularySynthesisReceipt] = {}
    probe_index_candidates = 0
    seeded_candidates = 0
    projection_builds = 0
    projection_reuses = 0
    downstream_cache_hits = 0
    budget_exhausted = False
    pending = list(work)

    while pending and not budget_exhausted:
        next_pending: list[_ProbeWork] = []
        round_progress = False
        for item in pending:
            if receipt_slots[item.ordinal] is not None:
                continue
            remaining = max_total_synthesis_candidates - total_candidates
            if remaining <= 0:
                budget_exhausted = True
                break
            state = states.get(item.free_positions)
            if state is None:
                projected = tuple(_project_canonical_context(schema, row, item.free_positions) for row in probe_train)
                state = _SemanticProbeSearchState(
                    free_positions=item.free_positions,
                    canonical_fields=canonical_fields,
                    projected_contexts=projected,
                    vocabulary=vocabulary,
                    max_depth=int(probe_max_depth),
                    max_candidates=int(probe_index_max_candidates_per_projection),
                )
                states[item.free_positions] = state
                projection_builds += 1
            else:
                projection_reuses += 1

            before = state.candidates_considered
            hit = state.advance_until(
                item.target_key,
                max_new_candidates=min(probe_lookup_slice_candidates, remaining),
            )
            delta = state.candidates_considered - before
            if delta:
                round_progress = True
                total_candidates += delta
                probe_index_candidates += delta
            if hit is None:
                if state.exhausted:
                    receipt_slots[item.ordinal] = BudgetedInterventionCandidateReceipt(
                        item.intervention, False, 'probe_semantics_not_indexed',
                        target_distinct_outputs=item.distinct_outputs,
                    )
                else:
                    next_pending.append(item)
                continue

            if not hit.used_abstraction_ids or hit.expression.cost < int(min_seed_cost) or len(_used_fields(hit.expression)) < int(min_seed_fields):
                receipt_slots[item.ordinal] = BudgetedInterventionCandidateReceipt(
                    item.intervention, False, 'probe_seed_not_admissible',
                    target_distinct_outputs=item.distinct_outputs,
                    probe_expression=schema.externalize_expr(hit.expression),
                    used_abstraction_ids=hit.used_abstraction_ids,
                )
                continue

            if oracle_calls + len(probe_valid) > max_oracle_calls:
                receipt_slots[item.ordinal] = BudgetedInterventionCandidateReceipt(
                    item.intervention, False, 'oracle_budget_exhausted_before_validation',
                    target_distinct_outputs=item.distinct_outputs,
                    probe_expression=schema.externalize_expr(hit.expression),
                    used_abstraction_ids=hit.used_abstraction_ids,
                )
                continue
            exact = 0
            invalid_validation = False
            for context in probe_valid:
                applied = item.intervention.apply(context, fields)
                try:
                    expected = _oracle_value(oracle, applied)
                    actual = evaluate_with_vocabulary(
                        hit.expression,
                        _project_canonical_context(schema, applied, item.free_positions),
                        vocabulary,
                    )
                except (ArithmeticError, KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
                    invalid_validation = True
                    oracle_calls += 1
                    break
                oracle_calls += 1
                exact += int(_equivalent(actual, expected))
            if invalid_validation or exact != len(probe_valid):
                receipt_slots[item.ordinal] = BudgetedInterventionCandidateReceipt(
                    item.intervention, False, 'probe_validation_failed',
                    target_distinct_outputs=item.distinct_outputs,
                    probe_expression=schema.externalize_expr(hit.expression),
                    used_abstraction_ids=hit.used_abstraction_ids,
                    probe_validation_cases=len(probe_valid), probe_validation_exact=exact,
                )
                continue

            seed_digest = hit.expression_digest
            seeded = downstream_cache.get(seed_digest)
            if seeded is None:
                remaining = max_total_synthesis_candidates - total_candidates
                if remaining <= 0:
                    budget_exhausted = True
                    break
                seeded_need = _bounded_need(
                    downstream_need,
                    canonical_fields,
                    min(downstream_need.max_candidates, remaining),
                )
                seeded = synthesize_with_vocabulary(
                    seeded_need,
                    canonical_examples,
                    vocabulary,
                    seed_expressions=(hit.expression,),
                )
                downstream_cache[seed_digest] = seeded
                total_candidates += seeded.candidates_considered
                seeded_candidates += seeded.candidates_considered
            else:
                downstream_cache_hits += 1

            external_probe = schema.externalize_expr(hit.expression)
            external_full = schema.externalize_expr(seeded.expression) if seeded.expression is not None else None
            if not seeded.passed or seeded.expression is None:
                receipt_slots[item.ordinal] = BudgetedInterventionCandidateReceipt(
                    item.intervention, False, 'no_causal_downstream_gain',
                    target_distinct_outputs=item.distinct_outputs,
                    probe_expression=external_probe, used_abstraction_ids=hit.used_abstraction_ids,
                    probe_validation_cases=len(probe_valid), probe_validation_exact=exact,
                    seeded_downstream_passed=False,
                    seeded_downstream_candidates_considered=seeded.candidates_considered,
                    seeded_downstream_expression=external_full,
                )
                continue

            selected = BudgetedInterventionCandidateReceipt(
                item.intervention, True, 'causal_probe_verified_under_global_budget',
                target_distinct_outputs=item.distinct_outputs,
                probe_expression=external_probe, used_abstraction_ids=hit.used_abstraction_ids,
                probe_validation_cases=len(probe_valid), probe_validation_exact=exact,
                seeded_downstream_passed=True,
                seeded_downstream_candidates_considered=seeded.candidates_considered,
                seeded_downstream_expression=external_full,
            )
            receipt_slots[item.ordinal] = selected
            visible = tuple(row for row in receipt_slots if row is not None)
            return BudgetedInterventionDiscoveryReceipt(
                True, selected, visible, anchors, False, no_seed.candidates_considered,
                probe_index_candidates, seeded_candidates, total_candidates, max_total_synthesis_candidates,
                oracle_calls, projection_builds, projection_reuses, downstream_cache_hits,
                'causal_intervention_discovered_under_global_budget', 0,
            )

        if total_candidates >= max_total_synthesis_candidates:
            budget_exhausted = True
            break
        if not round_progress and next_pending:
            # No index advanced in a whole round: continuing cannot change evidence.
            for item in next_pending:
                receipt_slots[item.ordinal] = BudgetedInterventionCandidateReceipt(
                    item.intervention, False, 'probe_search_stalled', target_distinct_outputs=item.distinct_outputs,
                )
            next_pending = []
        pending = next_pending

    if total_candidates >= max_total_synthesis_candidates:
        budget_exhausted = True
    reason = 'global_synthesis_budget_exhausted' if budget_exhausted else 'no_causal_intervention_within_budget'
    visible = tuple(row for row in receipt_slots if row is not None)
    return BudgetedInterventionDiscoveryReceipt(
        False, None, visible, anchors, False, no_seed.candidates_considered,
        probe_index_candidates, seeded_candidates, total_candidates, max_total_synthesis_candidates,
        oracle_calls, projection_builds, projection_reuses, downstream_cache_hits, reason, 0,
    )


__all__ = [
    'SemanticProbeHit', 'SemanticProbeIndex',
    'BudgetedInterventionCandidateReceipt', 'BudgetedInterventionDiscoveryReceipt',
    'derive_anchor_values', 'semantic_vector_key', 'discover_budgeted_intervention',
]
