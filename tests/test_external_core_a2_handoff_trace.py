from __future__ import annotations

import copy

import pytest

from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.handoff import (
    ExternalHandoffEnvelope,
    HandoffAuthorityClass,
    HandoffValidationDisposition,
    validate_handoff_for_consumer,
)
from nolane.external_core.work_trace import CognitiveWorkTrace, TraceNodeStatus


def _manifest(
    component_id: str,
    family: ExternalCoreFamily,
    *,
    consumes: tuple[str, ...] = (),
    produces: tuple[str, ...] = (),
    authorities: tuple[str, ...] = (),
) -> ExternalComponentManifest:
    return ExternalComponentManifest.create(
        component_id=component_id,
        component_version="1.0.0",
        family=family,
        protocol_versions={"handoff-v1": "1"},
        consumes_contracts=consumes,
        produces_contracts=produces,
        authority_capabilities=authorities,
        forbidden_authorities=(),
        mutable_resources=(),
        evidence_inputs=(),
        evidence_outputs=(),
        restore_protocol="exact-revalidation",
        compatibility_floor="1.0.0",
        compatibility_ceiling="1.0.0",
    )


def _envelope(*, authority_class: HandoffAuthorityClass = HandoffAuthorityClass.INFORMATIVE) -> ExternalHandoffEnvelope:
    return ExternalHandoffEnvelope.create(
        producer_component_id="external.research",
        producer_component_version="1.0.0",
        producer_agent_id="research.chief",
        consumer_component_id="external.planning",
        consumer_contract_range="1",
        subject_id="research-synthesis-1",
        subject_digest="d" * 64,
        contract_kind="research-input",
        contract_version="1",
        authority_class=authority_class,
        source_state_digest="s" * 64,
        predecessor_handoff_ids=(),
        evidence_bindings=(("evidence-1", "e" * 64),),
        artifact_bindings=(("artifact-1", "a" * 64),),
        freshness_fence="epoch:10",
        limitations=("single platform",),
        known_unknowns=("cross-platform replication",),
        payload={"finding": "candidate improves recovery under matched conditions"},
    )


def test_handoff_restore_recomputes_identity_and_rejects_payload_tampering():
    envelope = _envelope()
    assert ExternalHandoffEnvelope.from_state(envelope.to_state()) == envelope

    forged_id = copy.deepcopy(envelope.to_state())
    forged_id["handoff_id"] = "handoff-forged"
    with pytest.raises(ValueError, match="handoff identity"):
        ExternalHandoffEnvelope.from_state(forged_id)

    forged_payload = copy.deepcopy(envelope.to_state())
    forged_payload["payload_json"] = '{"finding":"different"}'
    with pytest.raises(ValueError):
        ExternalHandoffEnvelope.from_state(forged_payload)


def test_handoff_normalizes_bindings_and_rejects_duplicate_evidence_refs():
    with pytest.raises(ValueError, match="duplicate evidence"):
        ExternalHandoffEnvelope.create(
            producer_component_id="external.research",
            producer_component_version="1.0.0",
            producer_agent_id="research.chief",
            consumer_component_id="external.planning",
            consumer_contract_range="1",
            subject_id="s1",
            subject_digest="d" * 64,
            contract_kind="research-input",
            contract_version="1",
            authority_class="informative",
            source_state_digest="s" * 64,
            predecessor_handoff_ids=(),
            evidence_bindings=(("e1", "a" * 64), ("e1", "b" * 64)),
            artifact_bindings=(),
            freshness_fence=None,
            limitations=("bounded",),
            known_unknowns=("replication",),
            payload={"x": 1},
        )


def test_consumer_validation_rechecks_contract_versions_state_and_bindings():
    envelope = _envelope()
    producer = _manifest(
        "external.research",
        ExternalCoreFamily.G,
        produces=("research-input",),
    )
    consumer = _manifest(
        "external.planning",
        ExternalCoreFamily.D,
        consumes=("research-input",),
    )
    result = validate_handoff_for_consumer(
        envelope,
        producer_manifest=producer,
        consumer_manifest=consumer,
        current_source_state_digest="s" * 64,
        current_evidence_digests={"evidence-1": "e" * 64},
        current_artifact_digests={"artifact-1": "a" * 64},
        known_predecessor_handoff_ids=(),
        current_freshness_fence="epoch:10",
    )
    assert result.disposition is HandoffValidationDisposition.ACCEPTED
    assert result.accepted

    stale = validate_handoff_for_consumer(
        envelope,
        producer_manifest=producer,
        consumer_manifest=consumer,
        current_source_state_digest="x" * 64,
        current_evidence_digests={"evidence-1": "e" * 64},
        current_artifact_digests={"artifact-1": "a" * 64},
        known_predecessor_handoff_ids=(),
        current_freshness_fence="epoch:10",
    )
    assert stale.disposition is HandoffValidationDisposition.BLOCKED
    assert "SOURCE_STATE_DRIFT" in stale.reason_codes


def test_missing_current_proof_is_unknown_not_silently_accepted():
    envelope = _envelope()
    producer = _manifest("external.research", ExternalCoreFamily.G, produces=("research-input",))
    consumer = _manifest("external.planning", ExternalCoreFamily.D, consumes=("research-input",))
    result = validate_handoff_for_consumer(
        envelope,
        producer_manifest=producer,
        consumer_manifest=consumer,
        current_source_state_digest=None,
        current_evidence_digests={},
        current_artifact_digests={},
        known_predecessor_handoff_ids=(),
        current_freshness_fence=None,
    )
    assert result.disposition is HandoffValidationDisposition.UNKNOWN
    assert "MISSING_CURRENT_SOURCE_STATE" in result.reason_codes
    assert "MISSING_CURRENT_EVIDENCE" in result.reason_codes
    assert "MISSING_CURRENT_ARTIFACT" in result.reason_codes


def test_authoritative_handoff_cannot_outgrow_producer_manifest_authority():
    envelope = _envelope(authority_class=HandoffAuthorityClass.AUTHORIZED)
    producer = _manifest("external.research", ExternalCoreFamily.G, produces=("research-input",))
    consumer = _manifest("external.planning", ExternalCoreFamily.D, consumes=("research-input",))
    result = validate_handoff_for_consumer(
        envelope,
        producer_manifest=producer,
        consumer_manifest=consumer,
        current_source_state_digest="s" * 64,
        current_evidence_digests={"evidence-1": "e" * 64},
        current_artifact_digests={"artifact-1": "a" * 64},
        known_predecessor_handoff_ids=(),
        current_freshness_fence="epoch:10",
    )
    assert result.disposition is HandoffValidationDisposition.BLOCKED
    assert "PRODUCER_LACKS_AUTHORITY" in result.reason_codes


def test_trace_is_content_addressed_append_only_and_has_no_authority_upgrade_api():
    trace = CognitiveWorkTrace(trace_id="trace-a2")
    root = trace.append_node(
        component_id="external.research",
        subject_id="s1",
        subject_digest="d" * 64,
        status="informative",
        predecessor_node_ids=(),
        handoff_id=None,
        evidence_refs=("e1",),
        limitations=("bounded",),
    )
    child = trace.append_node(
        component_id="external.planning",
        subject_id="plan-1",
        subject_digest="p" * 64,
        status=TraceNodeStatus.PROPOSED,
        predecessor_node_ids=(root.node_id,),
        handoff_id="handoff-1",
        evidence_refs=("e2",),
        limitations=(),
    )
    sibling = trace.append_node(
        component_id="external.verification",
        subject_id="verification-1",
        subject_digest="v" * 64,
        status=TraceNodeStatus.NEGATIVE,
        predecessor_node_ids=(root.node_id,),
        handoff_id="handoff-2",
        evidence_refs=("e3",),
        limitations=("counterexample retained",),
    )
    assert child.predecessor_node_ids == (root.node_id,)
    assert sibling.status is TraceNodeStatus.NEGATIVE
    assert not hasattr(trace, "authorize")
    assert not hasattr(trace, "promote")
    assert not hasattr(trace, "execute")

    restored = CognitiveWorkTrace.from_state(trace.to_state())
    assert restored.digest == trace.digest


def test_trace_rejects_missing_predecessor_and_restore_tampering():
    trace = CognitiveWorkTrace(trace_id="trace-a2")
    with pytest.raises(KeyError, match="predecessor"):
        trace.append_node(
            component_id="external.research",
            subject_id="s1",
            subject_digest="d" * 64,
            status="aborted",
            predecessor_node_ids=("trace-node-missing",),
            handoff_id=None,
            evidence_refs=("e1",),
            limitations=("missing basis",),
        )

    root = trace.append_node(
        component_id="external.research",
        subject_id="s1",
        subject_digest="d" * 64,
        status="aborted",
        predecessor_node_ids=(),
        handoff_id=None,
        evidence_refs=("e1",),
        limitations=("negative result retained",),
    )
    state = trace.to_state()
    state["nodes"][0]["node_id"] = "trace-node-forged"
    with pytest.raises(ValueError, match="trace node identity"):
        CognitiveWorkTrace.from_state(state)
    assert trace.node(root.node_id) == root


def test_trace_supersession_is_separate_append_only_receipt():
    trace = CognitiveWorkTrace(trace_id="trace-a2")
    first = trace.append_node(
        component_id="external.research",
        subject_id="s1",
        subject_digest="d" * 64,
        status="informative",
        predecessor_node_ids=(),
        handoff_id=None,
        evidence_refs=("e1",),
        limitations=(),
    )
    second = trace.append_node(
        component_id="external.research",
        subject_id="s2",
        subject_digest="e" * 64,
        status="informative",
        predecessor_node_ids=(first.node_id,),
        handoff_id=None,
        evidence_refs=("e2",),
        limitations=(),
    )
    receipt = trace.supersede(
        first.node_id,
        successor_node_id=second.node_id,
        reason="new evidence",
        evidence_refs=("e3",),
    )
    assert receipt.predecessor_node_id == first.node_id
    assert receipt.successor_node_id == second.node_id
    assert trace.node(first.node_id) == first
    assert CognitiveWorkTrace.from_state(trace.to_state()).supersession(first.node_id) == receipt
