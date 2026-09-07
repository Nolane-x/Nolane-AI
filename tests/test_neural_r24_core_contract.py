import pytest

from nolane.neural.core_contract import (
    AdaptationBoundary,
    Candidate,
    CandidateRanker,
    CognitiveState,
    ConfidenceAssessment,
    EvidenceRef,
    ExpertRoute,
    NeuralInvariantError,
    NEURAL_CORE_REVISION,
)


def _evidence(*, source_core: str = "memory", receipt_id: str = "receipt-1", authority: str = "observation") -> EvidenceRef:
    return EvidenceRef.create(
        source_core=source_core,
        receipt_id=receipt_id,
        digest="a" * 64,
        authority=authority,
    )


def test_r24_revision_is_explicit_and_external_authority_is_not_extended():
    assert NEURAL_CORE_REVISION == "R2.4"
    assert "A11" not in NEURAL_CORE_REVISION


def test_cognitive_state_is_canonical_deterministic_and_provenance_bound():
    p = _evidence()
    left = CognitiveState.create(payload={"b": [2, 3], "a": 1}, provenance=[p])
    right = CognitiveState.create(payload={"a": 1, "b": [2, 3]}, provenance=[p])
    assert left.digest == right.digest
    assert left.to_state() == right.to_state()
    assert left.provenance == (p,)


def test_missing_or_empty_provenance_cannot_be_laundered_into_valid_state():
    with pytest.raises(NeuralInvariantError, match="provenance"):
        CognitiveState.create(payload={"task": "x"}, provenance=[])
    with pytest.raises(NeuralInvariantError, match="payload"):
        CognitiveState.create(payload={}, provenance=[_evidence()])


def test_authoritative_claims_cannot_be_minted_by_neural_core():
    for authority in ("truth", "verification", "assurance"):
        with pytest.raises(NeuralInvariantError, match="mint"):
            EvidenceRef.create(
                source_core="neural",
                receipt_id="neural-self-issued",
                digest="b" * 64,
                authority=authority,
            )


def test_confidence_is_normalized_and_abstention_is_explicit():
    with pytest.raises(NeuralInvariantError, match="confidence"):
        ConfidenceAssessment.create(1.01)
    accepted = ConfidenceAssessment.create(0.81, abstain_below=0.6)
    abstained = ConfidenceAssessment.create(0.59, abstain_below=0.6)
    assert accepted.abstain is False
    assert accepted.reason is None
    assert abstained.abstain is True
    assert abstained.reason == "below-confidence-threshold"


def test_candidate_ranking_is_deterministic_with_canonical_tie_break():
    evidence = (_evidence(),)
    route_a = ExpertRoute.create(expert_id="expert-a", path_id="path-1", confidence=0.8, evidence=evidence)
    route_b = ExpertRoute.create(expert_id="expert-b", path_id="path-1", confidence=0.8, evidence=evidence)
    a = Candidate.create(candidate_id="a", route=route_a, confidence=0.8, utility=0.7, evidence=evidence)
    b = Candidate.create(candidate_id="b", route=route_b, confidence=0.8, utility=0.7, evidence=evidence)
    assert [row.candidate_id for row in CandidateRanker.rank([b, a])] == ["a", "b"]
    assert [row.candidate_id for row in CandidateRanker.rank([a, b])] == ["a", "b"]


def test_candidate_selection_abstains_on_low_confidence_or_ambiguous_margin():
    evidence = (_evidence(),)
    route = ExpertRoute.create(expert_id="expert-a", path_id="path-1", confidence=0.9, evidence=evidence)
    low = Candidate.create(candidate_id="low", route=route, confidence=0.49, utility=1.0, evidence=evidence)
    decision = CandidateRanker.select([low], min_confidence=0.5, min_margin=0.0)
    assert decision.selected is None
    assert decision.abstain is True
    assert decision.reason == "below-confidence-threshold"

    one = Candidate.create(candidate_id="one", route=route, confidence=0.8, utility=0.8, evidence=evidence)
    two = Candidate.create(candidate_id="two", route=route, confidence=0.79, utility=0.8, evidence=evidence)
    ambiguous = CandidateRanker.select([one, two], min_confidence=0.5, min_margin=0.02)
    assert ambiguous.selected is None
    assert ambiguous.abstain is True
    assert ambiguous.reason == "insufficient-confidence-margin"


def test_adaptation_boundary_is_explicit_immutable_and_scope_limited():
    boundary = AdaptationBoundary.create(
        policy_revision="adapt-v1",
        allowed_parameters=["router.temperature", "ranker.min_margin"],
        evidence=[_evidence(source_core="verification")],
    )
    boundary.validate_update({"router.temperature": 0.5})
    with pytest.raises(NeuralInvariantError, match="authority boundary"):
        boundary.validate_update({"truth.status": "verified"})
    with pytest.raises(AttributeError):
        boundary.policy_revision = "mutated"
