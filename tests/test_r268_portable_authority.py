from __future__ import annotations

import pytest

from cogcoder.r256_operator_dsl import Binary, Field, expr_digest
from cogcoder.r268_cross_task_causal_transfer import PortableCausalProgram


def _valid_expression():
    return Binary('sub', Binary('add', Field('__p0'), Field('__p1')), Field('__p2'))


def test_direct_portable_construction_rejects_source_identity_leakage():
    expression = Binary('add', Binary('add', Field('__p0'), Field('__p1')), Field('source_secret'))
    with pytest.raises(ValueError, match='exactly three abstract probe roles'):
        PortableCausalProgram(expression=expression, expression_digest=expr_digest(expression))


def test_direct_portable_construction_rejects_digest_mismatch():
    expression = _valid_expression()
    with pytest.raises(ValueError, match='expression_digest'):
        PortableCausalProgram(expression=expression, expression_digest='forged')


def test_direct_portable_construction_rejects_probe_role_or_parameter_boundary_mutation():
    expression = _valid_expression()
    digest = expr_digest(expression)

    with pytest.raises(ValueError, match='probe_roles'):
        PortableCausalProgram(
            expression=expression,
            expression_digest=digest,
            probe_roles=('source_a', '__p1', '__p2'),
        )

    with pytest.raises(ValueError, match='trainable_parameter_count'):
        PortableCausalProgram(
            expression=expression,
            expression_digest=digest,
            trainable_parameter_count=1,
        )
