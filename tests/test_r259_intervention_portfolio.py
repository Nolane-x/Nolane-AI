from __future__ import annotations

import math

from benchmarks.kfigg.r257_verified_vocabulary_growth import build_promoted_vocabulary
from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r257_vocabulary import evaluate_with_vocabulary
from cogcoder.r259_intervention_portfolio import PortfolioBudget, discover_intervention_portfolio


def _fixture(prefix: str = 'x'):
    fields = (f'{prefix}7', f'{prefix}2', f'{prefix}9', f'{prefix}4', f'{prefix}1')
    x, a, b, fa, fb = fields

    def oracle(context):
        xv = float(context[x]); av = float(context[a]); bv = float(context[b])
        fav = float(context[fa]); fbv = float(context[fb])
        t = min(max((xv - av) / (bv - av), 0.0), 1.0)
        return fav + t * (fbv - fav)

    raw_train = (
        (-4.0, 0.0, 8.0, 2.0, 10.0), (0.0, 0.0, 8.0, 2.0, 10.0),
        (2.0, 0.0, 8.0, 2.0, 10.0), (4.0, 0.0, 8.0, 2.0, 10.0),
        (6.0, 0.0, 8.0, 2.0, 10.0), (8.0, 0.0, 8.0, 2.0, 10.0),
        (12.0, 0.0, 8.0, 2.0, 10.0), (0.0, -4.0, 4.0, -2.0, 6.0),
    )
    raw_challenge = (
        (-6.0, -4.0, 4.0, -2.0, 6.0), (-4.0, -4.0, 4.0, -2.0, 6.0),
        (-2.0, -4.0, 4.0, -2.0, 6.0), (2.0, -4.0, 4.0, -2.0, 6.0),
        (4.0, -4.0, 4.0, -2.0, 6.0), (8.0, -4.0, 4.0, -2.0, 6.0),
        (4.0, 2.0, 10.0, -4.0, 4.0), (8.0, 2.0, 10.0, -4.0, 4.0),
    )

    def ctx(row):
        return dict(zip(fields, row))

    train = tuple(OperatorExample(f'train:{i}', ctx(row), oracle(ctx(row))) for i, row in enumerate(raw_train))
    challenge = tuple(ctx(row) for row in raw_challenge)
    need = OperatorInventionNeed(
        'r259:opaque-linearstep', fields, f'{prefix}:out', constants=(0, 1), max_depth=3, max_candidates=1000,
    )
    return fields, oracle, train, challenge, need


def test_fallback_uses_canonicalized_exposure_and_passes_common_challenge():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    fields, oracle, train, challenge, need = _fixture('alpha')
    receipt = discover_intervention_portfolio(
        oracle, fields, (0, 1), train, challenge, vocabulary, need,
        strategy='fallback',
        budget=PortfolioBudget(max_shared_oracle_calls=900),
    )
    assert receipt.passed
    assert receipt.selected_method == 'exposure'
    assert receipt.exposure_passed is True
    assert receipt.challenge_exact == len(challenge)
    assert receipt.trainable_parameter_count == 0
    for context in challenge:
        assert math.isclose(
            float(evaluate_with_vocabulary(receipt.expression, context, vocabulary)),
            float(oracle(context)), rel_tol=1e-12, abs_tol=1e-12,
        )


def test_positional_fallback_remains_available_when_exposure_is_disabled():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    fields, oracle, train, challenge, need = _fixture('beta')
    receipt = discover_intervention_portfolio(
        oracle, fields, (0, 1), train, challenge, vocabulary, need,
        strategy='fallback', enable_exposure=False, enable_positional=True,
        budget=PortfolioBudget(max_shared_oracle_calls=1200),
    )
    assert receipt.passed
    assert receipt.selected_method == 'positional'
    assert receipt.exposure_passed is False
    assert receipt.positional_passed is True
    assert receipt.challenge_exact == len(challenge)


def test_robust_mode_records_cross_mechanism_agreement():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    fields, oracle, train, challenge, need = _fixture('gamma')
    receipt = discover_intervention_portfolio(
        oracle, fields, (0, 1), train, challenge, vocabulary, need,
        strategy='robust',
        budget=PortfolioBudget(max_shared_oracle_calls=1400),
    )
    assert receipt.passed
    assert receipt.exposure_passed is True
    assert receipt.positional_passed is True
    assert receipt.methods_agree is True
    assert receipt.selected_method == 'consensus'
    assert receipt.challenge_exact == len(challenge)
    assert receipt.oracle_calls <= 1400
    assert receipt.total_synthesis_candidates > 0


def test_external_field_renaming_preserves_portfolio_decision_and_accounting_shape():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    f1, o1, t1, c1, n1 = _fixture('left')
    f2, o2, t2, c2, n2 = _fixture('right')
    budget = PortfolioBudget(max_shared_oracle_calls=900)
    first = discover_intervention_portfolio(o1, f1, (0, 1), t1, c1, vocabulary, n1, strategy='fallback', budget=budget)
    second = discover_intervention_portfolio(o2, f2, (0, 1), t2, c2, vocabulary, n2, strategy='fallback', budget=budget)
    assert first.passed and second.passed
    assert first.selected_method == second.selected_method == 'exposure'
    assert first.challenge_exact == second.challenge_exact == len(c1) == len(c2)
    assert first.exposure_schema_id == second.exposure_schema_id
    assert first.oracle_calls == second.oracle_calls
    assert first.exposure_synthesis_candidates == second.exposure_synthesis_candidates


def test_disabled_portfolio_fails_closed():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    fields, oracle, train, challenge, need = _fixture('off')
    receipt = discover_intervention_portfolio(
        oracle, fields, (0, 1), train, challenge, vocabulary, need,
        enable_exposure=False, enable_positional=False,
    )
    assert not receipt.passed
    assert receipt.expression is None
    assert receipt.reason == 'no_enabled_discovery_engine'
