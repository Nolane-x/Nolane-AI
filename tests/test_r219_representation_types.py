from dataclasses import FrozenInstanceError

import pytest

from cogcoder.r219_representation_types import DiscoveryDecision, HypothesisSupport, LibraryAction, RawTransition, RepresentationHypothesis, VerifierObservation


def test_representation_identity_is_content_derived_and_domain_independent():
    a = RepresentationHypothesis(width=3, permutation=(2, 0, 1), complement=(1, 0, 1), reverse_direction=False)
    b = RepresentationHypothesis(width=3, permutation=(2, 0, 1), complement=(1, 0, 1), reverse_direction=False)
    assert a.representation_id == b.representation_id
    assert a.representation_id.startswith('repr:')
    assert len(a.representation_id) == len('repr:') + 16


def test_representation_validation_rejects_non_bijection_and_bad_complement():
    with pytest.raises(ValueError):
        RepresentationHypothesis(width=3, permutation=(0, 0, 1), complement=(0, 0, 0), reverse_direction=False)
    with pytest.raises(ValueError):
        RepresentationHypothesis(width=3, permutation=(0, 1, 2), complement=(0, 2, 0), reverse_direction=False)


def test_raw_transition_is_binary_and_immutable():
    row = RawTransition('q1', (0, 1, 0), (1, 0, 1))
    with pytest.raises(FrozenInstanceError):
        row.query_id = 'changed'
    with pytest.raises(ValueError):
        RawTransition('q2', (0, 1), (1, 2))


def test_verifier_reliability_must_be_more_than_coinflip():
    ok = VerifierObservation('q1', observed_label=True, reliability=0.75)
    assert ok.reliability == 0.75
    with pytest.raises(ValueError):
        VerifierObservation('q2', observed_label=False, reliability=0.5)
    with pytest.raises(ValueError):
        VerifierObservation('q3', observed_label=False, reliability=1.01)


def test_support_probability_and_log_likelihood_are_bounded_and_frozen():
    s = HypothesisSupport('repr:0123456789abcdef', log_likelihood=-1.25, posterior=0.4)
    assert s.posterior == 0.4
    with pytest.raises(ValueError):
        HypothesisSupport('repr:0123456789abcdef', log_likelihood=0.0, posterior=1.2)


def test_discovery_decision_states_and_accepted_require_representation():
    accepted = DiscoveryDecision('accept', 'repr:0123456789abcdef', 0.95, 0.3, ('q1', 'q2'), 'unique_verified_representation')
    assert accepted.status == 'accept'
    with pytest.raises(ValueError):
        DiscoveryDecision('accept', None, 0.9, 0.2, (), 'missing')
    abstain = DiscoveryDecision('abstain', None, 0.5, 0.0, ('q1',), 'ambiguous')
    assert abstain.status == 'abstain'


def test_library_action_is_strictly_typed():
    row = LibraryAction('reuse', 'repr:0123456789abcdef', 'skill:1234', 'verified_alignment')
    assert row.action == 'reuse'
    with pytest.raises(ValueError):
        LibraryAction('promote_everything', None, None, 'bad')
