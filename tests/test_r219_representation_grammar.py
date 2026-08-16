from cogcoder.r219_representation_grammar import (
    apply_representation,
    enumerate_hypotheses,
    invert_representation,
)
from cogcoder.r219_representation_types import RepresentationHypothesis


def test_width_two_grammar_is_complete_unique_and_deterministic():
    a = enumerate_hypotheses(2)
    b = enumerate_hypotheses(2)
    assert a == b
    assert len(a) == 16  # 2! permutations * 2^2 complements * 2 directions
    assert len({row.representation_id for row in a}) == 16


def test_apply_then_inverse_recovers_state():
    h = RepresentationHypothesis(3, (2, 0, 1), (1, 0, 1), True)
    raw = (1, 0, 1)
    latent = apply_representation(h, raw)
    assert invert_representation(h, latent) == raw


def test_grammar_identity_contains_no_external_domain_or_seed_fields():
    rows = enumerate_hypotheses(2)
    joined = ' '.join(row.representation_id for row in rows)
    assert 'seed' not in joined
    assert 'domain' not in joined
