from __future__ import annotations

import inspect
import math

import pytest

from benchmarks.kfigg.r257_verified_vocabulary_growth import build_promoted_vocabulary
from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r259_semantic_intervention_index import (
    derive_anchor_values,
    discover_budgeted_intervention,
    semantic_vector_key,
)


FIELDS = ('v0', 'v1', 'v2', 'v3', 'v4')
TRAIN_CASES = (
    (-4.0, 0.0, 8.0, 2.0, 10.0),
    (0.0, 0.0, 8.0, 2.0, 10.0),
    (2.0, 0.0, 8.0, 2.0, 10.0),
    (4.0, 0.0, 8.0, 2.0, 10.0),
    (6.0, 0.0, 8.0, 2.0, 10.0),
    (8.0, 0.0, 8.0, 2.0, 10.0),
    (12.0, 0.0, 8.0, 2.0, 10.0),
    (0.0, -4.0, 4.0, -2.0, 6.0),
)
PROBE_TRAIN = (
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
PROBE_VALID = (
    (-6.0, -4.0, 4.0, 3.0, 9.0),
    (-2.0, -4.0, 4.0, -7.0, 13.0),
    (2.0, -4.0, 4.0, 5.0, 21.0),
    (8.0, -4.0, 4.0, 2.0, 12.0),
)


def context(case, fields=FIELDS):
    return {field: float(value) for field, value in zip(fields, case, strict=True)}


def linearstep_context(row):
    x, a, b, fa, fb = (float(row[field]) for field in FIELDS)
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return fa + t * (fb - fa)


def make_need(fields=FIELDS, *, max_candidates=1000):
    return OperatorInventionNeed(
        'r259:test-full', fields, 'out', constants=(0, 1), max_depth=3, max_candidates=max_candidates,
    )


def examples(cases=TRAIN_CASES, fields=FIELDS):
    rows = []
    for index, case in enumerate(cases):
        c = context(case, fields)
        values = {FIELDS[i]: case[i] for i in range(5)}
        rows.append(OperatorExample(
            f't{index}', c,
            linearstep_context({field: values[FIELDS[i]] for i, field in enumerate(FIELDS)}),
        ))
    return tuple(rows)


def test_primary_api_has_no_separate_anchor_values_parameter():
    assert 'anchor_values' not in inspect.signature(discover_budgeted_intervention).parameters


def test_anchor_basis_is_derived_from_numeric_downstream_constants():
    need = OperatorInventionNeed(
        'anchors', FIELDS, 'out', constants=(1, 0, 1, -1, 'ignored'), max_depth=2, max_candidates=10,
    )
    assert derive_anchor_values(need) == (-1.0, 0.0, 1.0)


def test_anchor_basis_requires_enough_distinct_finite_numeric_values():
    need = OperatorInventionNeed(
        'anchors', FIELDS, 'out', constants=('x', 0), max_depth=2, max_candidates=10,
    )
    with pytest.raises(ValueError, match='at least 2'):
        derive_anchor_values(need, min_count=2)


def test_semantic_vector_key_normalizes_negative_zero_and_tiny_float_noise():
    assert semantic_vector_key((0.0, 1.0000000000001, -0.0)) == semantic_vector_key((0, 1.0, 0.0))
    with pytest.raises(ValueError):
        semantic_vector_key((math.inf,))


def test_budgeted_discovery_reuses_semantic_indexes_and_solves_under_global_budget():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    receipt = discover_budgeted_intervention(
        oracle=linearstep_context,
        ordered_field_names=FIELDS,
        probe_training_contexts=tuple(context(case) for case in PROBE_TRAIN),
        probe_validation_contexts=tuple(context(case) for case in PROBE_VALID),
        vocabulary=vocabulary,
        downstream_need=make_need(),
        downstream_examples=examples(),
        max_total_synthesis_candidates=15000,
        probe_index_max_candidates_per_projection=1200,
    )
    assert receipt.passed is True
    assert receipt.selected is not None
    assert sorted(position for position, _ in receipt.selected.intervention.bindings) == [3, 4]
    assert receipt.no_seed_passed is False
    assert receipt.selected.seeded_downstream_passed is True
    assert receipt.selected.probe_validation_exact == receipt.selected.probe_validation_cases == len(PROBE_VALID)
    assert receipt.total_synthesis_candidates <= 15000
    assert receipt.total_synthesis_candidates < 136969 // 8
    assert receipt.projection_index_builds <= 10
    assert receipt.trainable_parameter_count == 0


def test_rename_replay_preserves_positional_intervention_identity():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    renamed = ('q4', 'm2', 'z9', 'a7', 'h1')

    def renamed_oracle(row):
        vals = [float(row[name]) for name in renamed]
        x, a, b, fa, fb = vals
        t = min(max((x - a) / (b - a), 0.0), 1.0)
        return fa + t * (fb - fa)

    renamed_examples = []
    for index, case in enumerate(TRAIN_CASES):
        c = context(case, renamed)
        renamed_examples.append(OperatorExample(f'r{index}', c, renamed_oracle(c)))

    receipt = discover_budgeted_intervention(
        oracle=renamed_oracle,
        ordered_field_names=renamed,
        probe_training_contexts=tuple(context(case, renamed) for case in PROBE_TRAIN),
        probe_validation_contexts=tuple(context(case, renamed) for case in PROBE_VALID),
        vocabulary=vocabulary,
        downstream_need=make_need(renamed),
        downstream_examples=tuple(renamed_examples),
        max_total_synthesis_candidates=15000,
        probe_index_max_candidates_per_projection=1200,
    )
    assert receipt.passed is True
    assert receipt.selected is not None
    assert sorted(position for position, _ in receipt.selected.intervention.bindings) == [3, 4]


def test_global_budget_exhaustion_abstains_without_overrun():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    receipt = discover_budgeted_intervention(
        oracle=linearstep_context,
        ordered_field_names=FIELDS,
        probe_training_contexts=tuple(context(case) for case in PROBE_TRAIN),
        probe_validation_contexts=tuple(context(case) for case in PROBE_VALID),
        vocabulary=vocabulary,
        downstream_need=make_need(),
        downstream_examples=examples(),
        max_total_synthesis_candidates=1000,
        probe_index_max_candidates_per_projection=1200,
    )
    assert receipt.passed is False
    assert receipt.selected is None
    assert receipt.reason == 'global_synthesis_budget_exhausted'
    assert receipt.total_synthesis_candidates <= 1000


def test_invalid_oracle_fails_closed_instead_of_promoting_candidate():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()

    def invalid_oracle(_row):
        return math.inf

    receipt = discover_budgeted_intervention(
        oracle=invalid_oracle,
        ordered_field_names=FIELDS,
        probe_training_contexts=tuple(context(case) for case in PROBE_TRAIN[:3]),
        probe_validation_contexts=tuple(context(case) for case in PROBE_VALID[:2]),
        vocabulary=vocabulary,
        downstream_need=make_need(max_candidates=100),
        downstream_examples=examples(TRAIN_CASES[:3]),
        max_total_synthesis_candidates=2000,
        probe_index_max_candidates_per_projection=100,
    )
    assert receipt.passed is False
    assert receipt.selected is None
    assert all(not candidate.passed for candidate in receipt.candidates)
