from types import SimpleNamespace

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.context import ContextCapsule
from nolane.external_core.execution_types import ExecutionCounters
from nolane.neural.core_contract import (
    AdaptationBoundary,
    CognitiveState,
    EvidenceRef,
    ExpertRoute,
    ExpertRouter,
    NeuralInvariantError,
)
from nolane.neural.inference_bridge import CognitiveStateEncoder


def _evidence(*, receipt_id: str, digest_char: str = "a") -> EvidenceRef:
    return EvidenceRef.create(
        source_core="memory",
        receipt_id=receipt_id,
        digest=digest_char * 64,
        authority="observation",
    )


def _capsule() -> ContextCapsule:
    return ContextCapsule(
        agent_id="agent-1",
        task_id="task-1",
        plan_version=3,
        since_event_id=None,
        memories=(),
        event_delta=(),
        authoritative_artifacts=(("master-plan", 3),),
        tools=("filesystem",),
        external_cores=("memory",),
        authority_boundary=("workspace",),
    )


def _build_request(encoder: CognitiveStateEncoder, capsule: ContextCapsule, cognitive_state=None):
    kwargs = {
        "identity": SimpleNamespace(agent_id="agent-1", neural_version="Neural-R2.3-Ultra-Recursive-DAgger-Gated"),
        "capsule": capsule,
        "task_id": "task-1",
        "action_schema": ("inspect", "complete"),
        "counters": ExecutionCounters(),
        "step_index": 0,
        "checkpoint_digest": "checkpoint-digest",
    }
    if cognitive_state is not None:
        kwargs["cognitive_state"] = cognitive_state
    return encoder.build_request(**kwargs)


def test_from_state_rejects_non_mapping_provenance_instead_of_silently_dropping_it():
    state = CognitiveState.create(payload={"goal": "x"}, provenance=[_evidence(receipt_id="r1")]).to_state()
    state["provenance"].append("malformed-entry")

    with pytest.raises(NeuralInvariantError, match="provenance entry"):
        CognitiveState.from_state(state)


def test_from_state_requires_explicit_authority_in_serialized_provenance():
    state = CognitiveState.create(payload={"goal": "x"}, provenance=[_evidence(receipt_id="r1")]).to_state()
    del state["provenance"][0]["authority"]

    with pytest.raises(NeuralInvariantError, match="missing fields"):
        CognitiveState.from_state(state)


def test_neural_authority_aliases_cannot_mint_authoritative_evidence():
    for source_core in ("neural", "neural.router", "neural-core", "nolane.neural"):
        with pytest.raises(NeuralInvariantError, match="cannot mint"):
            EvidenceRef.create(
                source_core=source_core,
                receipt_id="self-issued",
                digest="c" * 64,
                authority="verification",
            )


def test_non_explicit_identity_fields_do_not_stringify_none_into_valid_state():
    with pytest.raises(NeuralInvariantError, match="source_core"):
        EvidenceRef.create(
            source_core=None,
            receipt_id="r1",
            digest="d" * 64,
            authority="observation",
        )
    with pytest.raises(NeuralInvariantError, match="receipt_id"):
        EvidenceRef.create(
            source_core="memory",
            receipt_id=None,
            digest="d" * 64,
            authority="observation",
        )


def test_adaptation_boundary_is_case_insensitive_for_protected_authority_domains():
    evidence = (_evidence(receipt_id="r1"),)
    with pytest.raises(NeuralInvariantError, match="protected authority"):
        AdaptationBoundary.create(
            policy_revision="adapt-v1",
            allowed_parameters=["Truth.status"],
            evidence=evidence,
        )

    boundary = AdaptationBoundary.create(
        policy_revision="adapt-v1",
        allowed_parameters=["router.temperature"],
        evidence=evidence,
    )
    with pytest.raises(NeuralInvariantError, match="authority boundary"):
        boundary.validate_update({"VERIFICATION.status": "verified"})


def test_expert_router_is_input_order_independent_and_has_canonical_tie_break():
    evidence = (_evidence(receipt_id="r1"),)
    a = ExpertRoute.create(expert_id="expert-a", path_id="path-1", confidence=0.8, evidence=evidence)
    b = ExpertRoute.create(expert_id="expert-b", path_id="path-1", confidence=0.8, evidence=evidence)

    assert [row.expert_id for row in ExpertRouter.rank([b, a])] == ["expert-a", "expert-b"]
    assert [row.expert_id for row in ExpertRouter.rank([a, b])] == ["expert-a", "expert-b"]


def test_expert_router_rejects_duplicate_route_identity():
    evidence = (_evidence(receipt_id="r1"),)
    one = ExpertRoute.create(expert_id="expert-a", path_id="path-1", confidence=0.9, evidence=evidence)
    two = ExpertRoute.create(expert_id="expert-a", path_id="path-1", confidence=0.8, evidence=evidence)

    with pytest.raises(NeuralInvariantError, match="route identities"):
        ExpertRouter.rank([one, two])


def test_expert_router_abstains_on_no_route_low_confidence_and_ambiguous_margin():
    empty = ExpertRouter.select([], min_confidence=0.5, min_margin=0.1)
    assert empty.selected is None
    assert empty.abstain is True
    assert empty.reason == "no-routes"

    evidence = (_evidence(receipt_id="r1"),)
    low = ExpertRoute.create(expert_id="expert-low", path_id="path-1", confidence=0.49, evidence=evidence)
    low_decision = ExpertRouter.select([low], min_confidence=0.5, min_margin=0.0)
    assert low_decision.selected is None
    assert low_decision.reason == "below-confidence-threshold"

    first = ExpertRoute.create(expert_id="expert-a", path_id="path-1", confidence=0.80, evidence=evidence)
    second = ExpertRoute.create(expert_id="expert-b", path_id="path-1", confidence=0.79, evidence=evidence)
    ambiguous = ExpertRouter.select([first, second], min_confidence=0.5, min_margin=0.02)
    assert ambiguous.selected is None
    assert ambiguous.reason == "insufficient-confidence-margin"


def test_r24_cognitive_state_digest_is_bound_into_inference_request_identity():
    encoder = CognitiveStateEncoder()
    capsule = _capsule()
    legacy_context_digest = canonical_digest(encoder.capsule_payload(capsule))
    state_a = CognitiveState.create(payload={"goal": "same"}, provenance=[_evidence(receipt_id="r-a", digest_char="a")])
    state_b = CognitiveState.create(payload={"goal": "same"}, provenance=[_evidence(receipt_id="r-b", digest_char="b")])

    legacy = _build_request(encoder, capsule)
    request_a = _build_request(encoder, capsule, state_a)
    request_b = _build_request(encoder, capsule, state_b)

    assert legacy.context_digest == legacy_context_digest
    assert request_a.context_digest == canonical_digest(
        {
            "capsule_digest": legacy_context_digest,
            "cognitive_state_digest": state_a.digest,
            "neural_core_revision": "R2.4",
        }
    )
    assert request_b.context_digest != request_a.context_digest
