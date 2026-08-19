from __future__ import annotations

import json

import pytest

from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r268_cross_task_causal_transfer import export_expression_prior


def _source_expression():
    return Binary('add', Binary('add', Field('__p0'), Field('__p1')), Field('__p2'))


def test_expression_prior_serialization_is_identity_free_and_zero_parameter():
    portable = export_expression_prior(_source_expression())
    data = portable.to_data()

    assert data['probe_roles'] == ['__p0', '__p1', '__p2']
    assert data['expression'] == _source_expression().to_data()
    assert data['trainable_parameter_count'] == 0
    assert portable.trainable_parameter_count == 0

    serialized = json.dumps(data, sort_keys=True)
    for forbidden in (
        'source_a',
        'source_b',
        'intervention-',
        'semantic-profile',
        'target_task',
    ):
        assert forbidden not in serialized


def test_expression_prior_requires_exactly_three_abstract_probe_roles():
    with pytest.raises(ValueError, match='exactly three abstract probe roles'):
        export_expression_prior(Binary('add', Field('__p0'), Field('__p1')))


def test_expression_prior_rejects_non_abstract_field_dependency():
    expression = Binary(
        'add',
        Binary('add', Field('__p0'), Field('__p1')),
        Field('source_secret'),
    )
    with pytest.raises(ValueError, match='exactly three abstract probe roles'):
        export_expression_prior(expression)
