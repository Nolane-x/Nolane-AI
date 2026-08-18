from __future__ import annotations

import math
from typing import Callable

from benchmarks.kfigg.r257_verified_vocabulary_growth import build_promoted_vocabulary
from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r257_vocabulary import evaluate_with_vocabulary
from cogcoder.r258_intervention_discovery import enumerate_interventions
from cogcoder.r259_semantic_intervention_index import discover_budgeted_intervention


_FIELDS = ('v0', 'v1', 'v2', 'v3', 'v4')
_R258_EXTERNAL_FROZEN_SYNTHESIS_CANDIDATES = 136_969
_GLOBAL_SYNTHESIS_BUDGET = 15_000

_PROBE_TRAIN = (
    (-4.0, 0.0, 8.0, 2.0, 10.0),
    (0.0, 0.0, 8.0, -3.0, 5.0),
    (2.0, 0.0, 8.0, 7.0, 15.0),
    (4.0, 0.0, 8.0, -8.0, 4.0),
    (6.0, 0.0, 8.0, 9.0, 17.0),
    (8.0, 0.0, 8.0, -1.0, 3.0),
    (12.0, 0.0, 8.0, 11.0, 19.0),
    (-6.0, -4.0, 4.0, -2.0, 6.0),
    (0.0, -4.0, 4.0, 3.0, 11.0),
    (6.0, -4.0, 4.0, -5.0, 7.0),
)

_PROBE_VALID = (
    (-6.0, -4.0, 4.0, 3.0, 9.0),
    (-2.0, -4.0, 4.0, -7.0, 13.0),
    (2.0, -4.0, 4.0, 5.0, 21.0),
    (8.0, -4.0, 4.0, 2.0, 12.0),
)

_TRAIN = (
    (-4.0, 0.0, 8.0, 2.0, 10.0), (0.0, 0.0, 8.0, 2.0, 10.0),
    (2.0, 0.0, 8.0, 2.0, 10.0), (4.0, 0.0, 8.0, 2.0, 10.0),
    (6.0, 0.0, 8.0, 2.0, 10.0), (8.0, 0.0, 8.0, 2.0, 10.0),
    (12.0, 0.0, 8.0, 2.0, 10.0), (0.0, -4.0, 4.0, -2.0, 6.0),
)

_CHALLENGE = (
    (-6.0, -4.0, 4.0, -2.0, 6.0), (-4.0, -4.0, 4.0, -2.0, 6.0),
    (-2.0, -4.0, 4.0, -2.0, 6.0), (2.0, -4.0, 4.0, -2.0, 6.0),
    (4.0, -4.0, 4.0, -2.0, 6.0), (8.0, -4.0, 4.0, -2.0, 6.0),
    (4.0, 2.0, 10.0, -4.0, 4.0), (8.0, 2.0, 10.0, -4.0, 4.0),
)


def _heldout() -> tuple[tuple[float, float, float, float, float], ...]:
    rows = []
    for a, b, fa, fb in ((0.0, 8.0, 1.0, 5.0), (-4.0, 4.0, -2.0, 6.0), (2.0, 10.0, -4.0, 4.0)):
        width = b - a
        for t in (-0.5, 0.0, 0.125, 0.375, 0.625, 0.875, 1.0, 1.5):
            rows.append((a + t * width, a, b, fa, fb))
    return tuple(rows)


def _context(case: tuple[float, float, float, float, float]) -> dict[str, float]:
    return {field: float(value) for field, value in zip(_FIELDS, case, strict=True)}


def _call_oracle(oracle: Callable[..., object], context: dict[str, object]) -> float:
    values = tuple(float(context[field]) for field in _FIELDS)
    value = float(oracle(*values))
    if not math.isfinite(value):
        raise ValueError('external oracle returned non-finite value')
    return value


def _examples(oracle: Callable[..., object], cases, prefix: str) -> tuple[OperatorExample, ...]:
    return tuple(
        OperatorExample(f'{prefix}:{index}', _context(case), _call_oracle(oracle, _context(case)))
        for index, case in enumerate(cases)
    )


def run_external_transfer(
    oracle: Callable[..., object],
    *,
    source_id: str,
    source_commit: str,
) -> dict[str, object]:
    if not callable(oracle):
        raise TypeError('oracle must be callable')
    oracle_calls_total = 0

    def counted_oracle(*args):
        nonlocal oracle_calls_total
        oracle_calls_total += 1
        return oracle(*args)

    vocabulary, _lifecycle, selected_abstractions = build_promoted_vocabulary()
    learned_digests = tuple(row.abstraction.abstraction_id for row in selected_abstractions)

    def context_oracle(context):
        return _call_oracle(counted_oracle, dict(context))

    need = OperatorInventionNeed(
        'external:opaque-full-task-r259',
        _FIELDS,
        'out',
        constants=(0, 1),
        max_depth=3,
        max_candidates=1000,
    )
    downstream_train = _examples(counted_oracle, _TRAIN, 'train')
    receipt = discover_budgeted_intervention(
        oracle=context_oracle,
        ordered_field_names=_FIELDS,
        probe_training_contexts=tuple(_context(case) for case in _PROBE_TRAIN),
        probe_validation_contexts=tuple(_context(case) for case in _PROBE_VALID),
        vocabulary=vocabulary,
        downstream_need=need,
        downstream_examples=downstream_train,
        probe_max_depth=2,
        probe_index_max_candidates_per_projection=1200,
        probe_lookup_slice_candidates=400,
        max_total_synthesis_candidates=_GLOBAL_SYNTHESIS_BUDGET,
    )
    selected = receipt.selected
    expression = selected.seeded_downstream_expression if selected is not None else None

    challenge = _examples(counted_oracle, _CHALLENGE, 'challenge')
    heldout = _examples(counted_oracle, _heldout(), 'heldout')
    challenge_exact = 0
    heldout_exact = 0
    if expression is not None:
        for row in challenge:
            actual = float(evaluate_with_vocabulary(expression, row.context, vocabulary))
            challenge_exact += int(math.isclose(actual, float(row.expected), rel_tol=1e-12, abs_tol=1e-12))
        for row in heldout:
            actual = float(evaluate_with_vocabulary(expression, row.context, vocabulary))
            heldout_exact += int(math.isclose(actual, float(row.expected), rel_tol=1e-12, abs_tol=1e-12))

    selected_positions = sorted(position for position, _value in selected.intervention.bindings) if selected is not None else []
    legal_interventions = len(enumerate_interventions(_FIELDS, receipt.derived_anchor_values, arity=2))
    reduction = _R258_EXTERNAL_FROZEN_SYNTHESIS_CANDIDATES / max(1, receipt.total_synthesis_candidates)
    passed = bool(
        receipt.passed
        and not receipt.no_seed_passed
        and selected is not None
        and selected.seeded_downstream_passed
        and selected.probe_validation_exact == selected.probe_validation_cases == len(_PROBE_VALID)
        and challenge_exact == len(challenge)
        and heldout_exact == len(heldout)
        and receipt.total_synthesis_candidates <= _GLOBAL_SYNTHESIS_BUDGET
        and reduction >= 8.0
    )
    return {
        'passed': passed,
        'source_id': str(source_id),
        'source_commit': str(source_commit),
        'source_exposure': 'io_only',
        'host_selected_intervention': False,
        'ordered_input_schema': 'opaque-positional-five-field',
        'intervention_anchor_source': 'downstream_need.constants',
        'derived_anchor_values': list(receipt.derived_anchor_values),
        'legal_interventions_enumerated': legal_interventions,
        'selected_intervention_id': selected.intervention.intervention_id if selected is not None else None,
        'selected_position_set': selected_positions,
        'selected_bindings': [list(row) for row in selected.intervention.bindings] if selected is not None else [],
        'no_seed_passed': receipt.no_seed_passed,
        'no_seed_candidates_considered': receipt.no_seed_candidates_considered,
        'seeded_passed': bool(selected is not None and selected.seeded_downstream_passed),
        'seeded_candidates_considered': selected.seeded_downstream_candidates_considered if selected is not None else 0,
        'probe_validation_cases': selected.probe_validation_cases if selected is not None else len(_PROBE_VALID),
        'probe_validation_exact': selected.probe_validation_exact if selected is not None else 0,
        'oracle_calls_during_discovery': receipt.oracle_calls,
        'oracle_calls_total': oracle_calls_total,
        'projection_index_builds': receipt.projection_index_builds,
        'projection_index_reuses': receipt.projection_index_reuses,
        'probe_index_candidates_considered': receipt.probe_index_candidates_considered,
        'seeded_downstream_candidates_considered_total': receipt.seeded_downstream_candidates_considered,
        'max_total_synthesis_candidates': _GLOBAL_SYNTHESIS_BUDGET,
        'total_synthesis_candidates': receipt.total_synthesis_candidates,
        'r258_external_frozen_synthesis_candidates': _R258_EXTERNAL_FROZEN_SYNTHESIS_CANDIDATES,
        'synthesis_reduction_ratio': round(reduction, 6),
        'challenge_cases': len(challenge),
        'challenge_exact': challenge_exact,
        'heldout_cases': len(heldout),
        'heldout_exact': heldout_exact,
        'learned_abstraction_digests': learned_digests,
        'used_abstraction_ids': list(selected.used_abstraction_ids) if selected is not None else [],
        'learned_expression': expression.to_data() if expression is not None else None,
        'trainable_parameter_count': 0,
        'claim_boundary': 'Matched-distribution efficiency evidence for budgeted semantic-index intervention reuse; not new external breadth, open-ended anchor invention, source induction, or general program synthesis.',
    }


if __name__ == '__main__':
    raise SystemExit('Pass an external oracle callable from a hosted verification harness.')
