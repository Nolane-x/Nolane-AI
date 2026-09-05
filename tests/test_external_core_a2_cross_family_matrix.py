from __future__ import annotations

import copy
import math

import pytest

from nolane.external_core import (
    AuthorityEdge,
    AuthorityRelation,
    CapabilityDiscoveryIndex,
    CognitiveWorkTrace,
    ExternalAuthorityGraph,
    ExternalComponentManifest,
    ExternalCoreFamily,
    ExternalCoreRestoreSnapshot,
    ExternalHandoffEnvelope,
    HandoffAuthorityClass,
    HandoffValidationDisposition,
    audit_external_core,
    preflight_restore,
    validate_handoff_for_consumer,
)
from nolane.external_core.artifacts import ArtifactEnvelope
from nolane.external_core.audit import build_canonical_fabric_profile, run_canonical_audit
from nolane.external_core.operations_journal import OperationsJournal
from nolane.external_core.operations_recovery import OperationsSnapshot, RecoveryMode, recover_operations


PATHS = (
    ("A", "C", "a-c"),
    ("C", "D", "c-d"),
    ("D", "E", "d-e"),
    ("E", "F", "e-f"),
    ("F", "A", "f-a"),
    ("A", "B", "a-b"),
    ("B", "C", "b-c"),
    ("C", "G", "c-g"),
)


def _component(family: str, *, consumes: tuple[str, ...], produces: tuple[str, ...]) -> ExternalComponentManifest:
    return ExternalComponentManifest.create(
        component_id=f"external.matrix.{family.lower()}",
        component_version="1.0.0",
        family=family,
        protocol_versions={"fabric": "1"},
        consumes_contracts=consumes,
        produces_contracts=produces,
        authority_capabilities=("observe",),
        forbidden_authorities=(),
        mutable_resources=(f"matrix.resource.{family.lower()}",),
        evidence_inputs=("basis",),
        evidence_outputs=("receipt",),
        restore_protocol="exact-revalidation",
        compatibility_floor="1.0.0",
        compatibility_ceiling="1.0.0",
    )


def _matrix() -> tuple[dict[str, ExternalComponentManifest], ExternalAuthorityGraph]:
    manifests = {
        "A": _component("A", consumes=("f-a",), produces=("a-c", "a-b")),
        "B": _component("B", consumes=("a-b",), produces=("b-c",)),
        "C": _component("C", consumes=("a-c", "b-c"), produces=("c-d", "c-g")),
        "D": _component("D", consumes=("c-d",), produces=("d-e",)),
        "E": _component("E", consumes=("d-e",), produces=("e-f",)),
        "F": _component("F", consumes=("e-f",), produces=("f-a",)),
        "G": _component("G", consumes=("c-g",), produces=()),
    }
    edges = tuple(
        AuthorityEdge.create(
            source_component_id=manifests[source].component_id,
            target_component_id=manifests[target].component_id,
            relation=AuthorityRelation.PUBLISHES_ARTIFACT_TO,
            contract_kind=contract,
        )
        for source, target, contract in PATHS
    )
    graph = ExternalAuthorityGraph(tuple(manifests.values()), edges)
    assert graph.validate().clean
    return manifests, graph


def _handoff(
    producer: ExternalComponentManifest,
    consumer: ExternalComponentManifest,
    contract: str,
    *,
    source_state_digest: str = "s" * 64,
    contract_version: str = "1",
) -> ExternalHandoffEnvelope:
    return ExternalHandoffEnvelope.create(
        producer_component_id=producer.component_id,
        producer_component_version=producer.component_version,
        producer_agent_id=f"{producer.family.value.lower()}.chief",
        consumer_component_id=consumer.component_id,
        consumer_contract_range="1",
        subject_id=f"subject:{contract}",
        subject_digest="d" * 64,
        contract_kind=contract,
        contract_version=contract_version,
        authority_class=HandoffAuthorityClass.INFORMATIVE,
        source_state_digest=source_state_digest,
        predecessor_handoff_ids=(),
        evidence_bindings=((f"e:{contract}", "e" * 64),),
        artifact_bindings=((f"artifact:{contract}", "a" * 64),),
        freshness_fence="epoch:10",
        limitations=("bounded-matrix",),
        known_unknowns=("external-generalization",),
        payload={"contract": contract, "producer": producer.component_id},
    )


def _validate_current(
    envelope: ExternalHandoffEnvelope,
    producer: ExternalComponentManifest,
    consumer: ExternalComponentManifest,
):
    contract = envelope.contract_kind
    return validate_handoff_for_consumer(
        envelope,
        producer_manifest=producer,
        consumer_manifest=consumer,
        current_source_state_digest=envelope.source_state_digest,
        current_evidence_digests={f"e:{contract}": "e" * 64},
        current_artifact_digests={f"artifact:{contract}": "a" * 64},
        known_predecessor_handoff_ids=(),
        current_freshness_fence="epoch:10",
    )


def test_all_required_cross_family_paths_are_declared_and_currently_validatable():
    manifests, graph = _matrix()
    discovery = CapabilityDiscoveryIndex(tuple(manifests.values()), graph)
    assert discovery.digest

    for source, target, contract in PATHS:
        result = discovery.by_contract(contract)
        assert tuple(row.component_id for row in result.producers) == (manifests[source].component_id,)
        assert tuple(row.component_id for row in result.consumers) == (manifests[target].component_id,)
        envelope = _handoff(manifests[source], manifests[target], contract)
        validation = _validate_current(envelope, manifests[source], manifests[target])
        assert validation.disposition is HandoffValidationDisposition.ACCEPTED


def test_full_loop_trace_retains_every_family_and_negative_branch_without_minting_authority():
    manifests, _ = _matrix()
    trace = CognitiveWorkTrace("trace-full-a2-loop")
    previous: tuple[str, ...] = ()
    visited = ("A", "C", "D", "E", "F", "A", "B", "C", "G")
    nodes = []
    for index, family in enumerate(visited):
        node = trace.append_node(
            component_id=manifests[family].component_id,
            subject_id=f"work:{index}:{family}",
            subject_digest=(family.lower() * 64)[:64],
            status="informative",
            predecessor_node_ids=previous,
            evidence_refs=(f"e:{index}",),
            limitations=(),
        )
        nodes.append(node)
        previous = (node.node_id,)
    negative = trace.append_node(
        component_id=manifests["A"].component_id,
        subject_id="counterexample",
        subject_digest="n" * 64,
        status="negative",
        predecessor_node_ids=(nodes[1].node_id,),
        evidence_refs=("e:counterexample",),
        limitations=("adversarial branch retained",),
    )
    assert negative.status.value == "negative"
    assert not trace.diagnostics()
    assert not hasattr(trace, "authorize")
    assert not hasattr(trace, "promote")


def test_tamper_stale_evidence_schema_downgrade_and_producer_upgrade_fail_closed():
    manifests, _ = _matrix()
    envelope = _handoff(manifests["A"], manifests["C"], "a-c")

    forged = copy.deepcopy(envelope.to_state())
    forged["subject_digest"] = "f" * 64
    with pytest.raises(ValueError):
        ExternalHandoffEnvelope.from_state(forged)

    stale_evidence = validate_handoff_for_consumer(
        envelope,
        producer_manifest=manifests["A"],
        consumer_manifest=manifests["C"],
        current_source_state_digest=envelope.source_state_digest,
        current_evidence_digests={"e:a-c": "x" * 64},
        current_artifact_digests={"artifact:a-c": "a" * 64},
        known_predecessor_handoff_ids=(),
        current_freshness_fence="epoch:10",
    )
    assert stale_evidence.disposition is HandoffValidationDisposition.BLOCKED
    assert "EVIDENCE_DIGEST_DRIFT" in stale_evidence.reason_codes

    downgraded = _handoff(manifests["A"], manifests["C"], "a-c", contract_version="0")
    downgraded_result = _validate_current(downgraded, manifests["A"], manifests["C"])
    assert downgraded_result.disposition is HandoffValidationDisposition.BLOCKED
    assert "CONTRACT_VERSION_OUT_OF_RANGE" in downgraded_result.reason_codes

    upgraded_producer = ExternalComponentManifest.create(
        component_id=manifests["A"].component_id,
        component_version="1.0.1",
        family="A",
        protocol_versions={"fabric": "1"},
        consumes_contracts=manifests["A"].consumes_contracts,
        produces_contracts=manifests["A"].produces_contracts,
        authority_capabilities=manifests["A"].authority_capabilities,
        forbidden_authorities=(),
        mutable_resources=manifests["A"].mutable_resources,
        evidence_inputs=manifests["A"].evidence_inputs,
        evidence_outputs=manifests["A"].evidence_outputs,
        restore_protocol="exact-revalidation",
        compatibility_floor="1.0.1",
        compatibility_ceiling="1.0.1",
    )
    upgraded_result = _validate_current(envelope, upgraded_producer, manifests["C"])
    assert upgraded_result.disposition is HandoffValidationDisposition.BLOCKED
    assert "PRODUCER_VERSION_DRIFT" in upgraded_result.reason_codes


def test_registry_source_state_and_partial_restore_drift_fail_closed():
    snapshot = ExternalCoreRestoreSnapshot.create(
        registry_digest="r" * 64,
        authority_graph_digest="g" * 64,
        artifact_graph_digest="a" * 64,
        handoff_frontier_digest="h" * 64,
        component_versions={"external.matrix.a": "1.0.0"},
    )
    drift = preflight_restore(
        snapshot=snapshot,
        current_registry_digest="x" * 64,
        current_authority_graph_digest="g" * 64,
        current_artifact_graph_digest="a" * 64,
        current_handoff_frontier_digest="h" * 64,
        current_component_versions={"external.matrix.a": "1.0.0"},
    )
    assert not drift.accepted
    assert "REGISTRY_DIGEST_DRIFT" in drift.reason_codes

    partial = snapshot.to_state()
    del partial["artifact_graph_digest"]
    with pytest.raises((KeyError, ValueError)):
        ExternalCoreRestoreSnapshot.from_state(partial)

    manifests, _ = _matrix()
    envelope = _handoff(manifests["C"], manifests["D"], "c-d")
    source_drift = validate_handoff_for_consumer(
        envelope,
        producer_manifest=manifests["C"],
        consumer_manifest=manifests["D"],
        current_source_state_digest="x" * 64,
        current_evidence_digests={"e:c-d": "e" * 64},
        current_artifact_digests={"artifact:c-d": "a" * 64},
        known_predecessor_handoff_ids=(),
        current_freshness_fence="epoch:10",
    )
    assert source_drift.disposition is HandoffValidationDisposition.BLOCKED
    assert "SOURCE_STATE_DRIFT" in source_drift.reason_codes


def test_bool_and_nan_cannot_cross_artifact_boundary():
    kwargs = dict(
        kind="matrix-artifact",
        schema_version="2",
        producer_component_id="external.matrix.g",
        producer_agent_id="g.chief",
        content="payload",
        source_state_digest="s" * 64,
        evidence_refs=("e1",),
        evidence_digests=("e" * 64,),
        dependency_artifact_ids=(),
        predecessor_artifact_ids=(),
        contract_id="matrix",
        contract_version="1",
        currentness_max_age_epochs=1,
    )
    with pytest.raises(TypeError):
        ArtifactEnvelope.create(created_epoch=True, metadata={}, **kwargs)
    with pytest.raises(ValueError, match="finite"):
        ArtifactEnvelope.create(created_epoch=1, metadata={"score": math.nan}, **kwargs)


def test_replay_fork_is_quarantined_not_merged():
    journal = OperationsJournal()
    event = journal.append(
        transition_id="matrix:1",
        kind="matrix_transition",
        subject_id="subject-1",
        payload={"digest": "a" * 64},
    )
    foreign = OperationsSnapshot.create(
        component_versions={"external.operations": "0.1.0"},
        journal_head_digest="foreign-head",
        journal_length=1,
        artifact_graph_digest="artifact-graph",
        authority_graph_digest="authority-graph",
        readiness_state_digest="readiness",
        registry_digest="registry",
        active_operation_ids=(),
    )
    assert event.digest != foreign.journal_head_digest
    result = recover_operations(
        snapshot=foreign,
        journal=journal,
        current_artifact_graph_digest="artifact-graph",
        current_authority_graph_digest="authority-graph",
        current_readiness_state_digest="readiness",
        current_registry_digest="registry",
    )
    assert result.mode is RecoveryMode.QUARANTINED
    assert not result.authoritative


def test_duplicate_writer_and_self_verification_laundering_are_rejected():
    a = _component("A", consumes=("self-proof",), produces=("self-proof",))
    b = ExternalComponentManifest.create(
        component_id="external.matrix.b2",
        component_version="1.0.0",
        family="B",
        protocol_versions={"fabric": "1"},
        consumes_contracts=(),
        produces_contracts=(),
        authority_capabilities=("observe",),
        forbidden_authorities=(),
        mutable_resources=a.mutable_resources,
        evidence_inputs=(),
        evidence_outputs=(),
        restore_protocol="exact-revalidation",
        compatibility_floor="1.0.0",
        compatibility_ceiling="1.0.0",
    )
    duplicate_graph = ExternalAuthorityGraph((a, b), ())
    with pytest.raises(ValueError, match="writer"):
        duplicate_graph.validate()

    verifier = ExternalComponentManifest.create(
        component_id="external.matrix.verifier",
        component_version="1.0.0",
        family="A",
        protocol_versions={"fabric": "1"},
        consumes_contracts=("self-proof",),
        produces_contracts=("self-proof",),
        authority_capabilities=("verify",),
        forbidden_authorities=(),
        mutable_resources=(),
        evidence_inputs=(),
        evidence_outputs=(),
        restore_protocol="exact-revalidation",
        compatibility_floor="1.0.0",
        compatibility_ceiling="1.0.0",
    )
    self_edge = AuthorityEdge.create(
        source_component_id=verifier.component_id,
        target_component_id=verifier.component_id,
        relation=AuthorityRelation.VERIFIES,
        contract_kind="self-proof",
    )
    laundering = ExternalAuthorityGraph((verifier,), (self_edge,))
    with pytest.raises(ValueError, match="SELF_VERIFICATION_LOOP"):
        laundering.validate()


def test_canonical_profile_and_cli_audit_are_clean_and_read_only():
    profile = build_canonical_fabric_profile()
    assert profile.authority_graph.validate().clean
    report = run_canonical_audit()
    assert report.clean
    assert not hasattr(profile, "invoke")
    assert not hasattr(profile, "execute")

    audit = audit_external_core(
        manifests=profile.manifests,
        authority_graph=profile.authority_graph,
        handoffs=(),
        traces=(),
        current_source_state_digests={},
        current_evidence_digests={},
        current_artifact_digests={},
        current_freshness_fences={},
    )
    assert audit.clean
