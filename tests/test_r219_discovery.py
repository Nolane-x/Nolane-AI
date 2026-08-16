from cogcoder.r219_discovery import choose_query, discover_representation, initial_supports, update_supports
from cogcoder.r219_representation_types import RepresentationHypothesis, VerifierObservation


def _h0():
    return RepresentationHypothesis(2, (0, 1), (0, 0), False)


def _h1():
    return RepresentationHypothesis(2, (1, 0), (0, 0), False)


def test_calibrated_likelihood_can_recover_after_one_noisy_contradiction():
    hypotheses = (_h0(), _h1())
    supports = initial_supports(hypotheses)
    prediction_rows = {
        'q1': {hypotheses[0].representation_id: True, hypotheses[1].representation_id: False},
        'q2': {hypotheses[0].representation_id: True, hypotheses[1].representation_id: False},
        'q3': {hypotheses[0].representation_id: False, hypotheses[1].representation_id: True},
    }
    observations = (
        VerifierObservation('q1', False, 0.55),
        VerifierObservation('q2', True, 0.90),
        VerifierObservation('q3', False, 0.90),
    )
    for obs in observations:
        supports = update_supports(hypotheses, supports, obs, prediction_rows[obs.query_id])
    by_id = {s.representation_id: s for s in supports}
    assert by_id[hypotheses[0].representation_id].posterior > 0.95
    assert by_id[hypotheses[0].representation_id].posterior > by_id[hypotheses[1].representation_id].posterior


def test_choose_query_uses_weighted_hypothesis_disagreement():
    hypotheses = (_h0(), _h1())
    supports = initial_supports(hypotheses)
    predictions = {
        'same': {hypotheses[0].representation_id: True, hypotheses[1].representation_id: True},
        'split': {hypotheses[0].representation_id: True, hypotheses[1].representation_id: False},
        'split-z': {hypotheses[0].representation_id: False, hypotheses[1].representation_id: True},
    }
    assert choose_query(hypotheses, supports, ('same', 'split', 'split-z'), predictions) == 'split'


def test_discovery_accepts_unique_supported_representation_after_counterexample():
    hypotheses = (_h0(), _h1())
    predictions = {
        'q1': {hypotheses[0].representation_id: True, hypotheses[1].representation_id: False},
        'q2': {hypotheses[0].representation_id: False, hypotheses[1].representation_id: True},
    }
    answers = {
        'q1': VerifierObservation('q1', True, 0.95),
        'q2': VerifierObservation('q2', False, 0.95),
    }
    decision = discover_representation(
        hypotheses, ('q1', 'q2'), predictions,
        verifier=lambda q: answers[q],
        counterexample_check=lambda h: h.representation_id == hypotheses[0].representation_id,
        query_budget=2, accept_probability=0.90, accept_margin=0.80,
    )
    assert decision.status == 'accept'
    assert decision.representation_id == hypotheses[0].representation_id


def test_discovery_abstains_when_hypotheses_are_observationally_equivalent():
    hypotheses = (_h0(), _h1())
    predictions = {
        'q1': {hypotheses[0].representation_id: True, hypotheses[1].representation_id: True},
        'q2': {hypotheses[0].representation_id: False, hypotheses[1].representation_id: False},
    }
    answers = {'q1': VerifierObservation('q1', True, 1.0), 'q2': VerifierObservation('q2', False, 1.0)}
    decision = discover_representation(
        hypotheses, ('q1', 'q2'), predictions,
        verifier=lambda q: answers[q], counterexample_check=lambda h: True,
        query_budget=2, accept_probability=0.90, accept_margin=0.25,
    )
    assert decision.status == 'abstain'
    assert decision.representation_id is None
