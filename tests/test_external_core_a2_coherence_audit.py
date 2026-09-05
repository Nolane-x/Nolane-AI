from __future__ import annotations

import copy

import pytest

from nolane.external_core.authority_graph import AuthorityEdge, AuthorityRelation, ExternalAuthorityGraph
from nolane.external_core.capability_discovery import CapabilityDiscoveryIndex
from nolane.external_core.coherence_audit import (
    ExternalCoreRestoreSnapshot,
    audit_external_core,
    preflight_restore,
)
from nolane.external_core.component_contracts import ExternalComponentManifest, ExternalCoreFamily
from nolane.external_core.handoff import ExternalHandoffEnvelope, HandoffAuthorityClass
from nolane.external_core.work_trace import CognitiveWorkTrace


def _manifest(
    component_id: str,
    family: ExternalCoreFamily,
    *,
    consumes: tuple[str, ...] = (),
    produces: tuple[str, ...] = (),
    authorities: tuple[str, ...] = (),
    resources: tuple[str, ...] = (),
    restore_protocol: str = "exact-revalidation",
) -> ExternalComponentManifest:
    return ExternalComponentManifest.create(
        component_id=component_id,
        component_version="1.0.0",
        family=family,
        protocol_versions={"fabric": "1"},
        consumes_contracts=consumes,
        produces_contracts=produces,
        authority_capabilities=authorities,
        forbidden_authorities=(),
        mutable_resources=resources,
        evidence_inputs=("evidence",),
        evidence_outputs=("receipt",),
        restore_protocol=restore_protocol,
        compatibility_floor="1.0.0",
        compatibility_ceiling="1.0.0",
    )


def _research_to_planning() -> tuple[ExternalComponentManifest, ExternalComponentManifest, ExternalAuthorityGraph]:
    research = _manifest(
        "external.research",
        ExternalCoreFamily.G,
        produces=("research-input",),
    )
    planning = _manifest(
        "external.planning",
        ExternalCoreFamily.D,
        consumes=("research-input",),
    )
    edge = AuthorityEdge.create(
        source_component_id=research.component_id,
        target_component_id=planning.component_id,
        relation=AuthorityRelation.PUBLISHES_ARTIFACT_TO,
        contract_kind="research-input",
    )
    graph = ExternalAuthorityGraph((research, planning), (edge,))
    assert graph.validate().clean
    return research, planning, graph


def _handoff(*, predecessors: tuple[str, ...] = ()) -> ExternalHandoffEnvelope:
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
        authority_class=HandoffAuthorityClass.INFORMATIVE,
        source_state_digest="s" * 64,
        predecessor_handoff_ids=predecessors,
        evidence_bindings=(("evidence-1", "e" * 64),),
        artifact_bindings=(("artifact-1", "a" * 64),),
        freshness_fence="epoch:10",
        limitations=("bounded",),
        known_unknowns=("replication",),
        payload={"finding": "x"},
    )


def test_discovery_is_read_only_and_finds_contract_producers_consumers():
    research, planning, graph = _research_to_planning()
    index = CapabilityDiscoveryIndex((research, planning), graph)

    result = index.by_contract("research-input")
    assert tuple(row.component_id for row in result.producers) == ("external.research",)
    assert tuple(row.component_id for row in result.consumers) == ("external.planning",)
    assert result.producers[0].restore_protocol == "exact-revalidation"
    assert not hasattr(index, "invoke")
    assert not hasattr(index, "execute")
    assert index.describe("external.research").family is ExternalCoreFamily.G


def test_discovery_restore_rejects_graph_or_manifest_drift():
    research, planning, graph = _research_to_planning()
    index = CapabilityDiscoveryIndex((research, planning), graph)
    state = index.to_state()
    assert CapabilityDiscoveryIndex.from_state(state).digest == index.digest

    forged = copy.deepcopy(state)
    forged["authority_graph_digest"] = "f" * 64
    with pytest.raises(ValueError, match="authority graph"):
        CapabilityDiscoveryIndex.from_state(forged)


def test_restore_preflight_accepts_exact_snapshot_and_rejects_registry_graph_and_component_drift():
    snapshot = ExternalCoreRestoreSnapshot.create(
        registry_digest="r" * 64,
        authority_graph_digest="g" * 64,
        artifact_graph_digest="a" * 64,
        handoff_frontier_digest="h" * 64,
        component_versions={"external.operations": "1.0.0", "external.research": "1.0.0"},
    )
    exact = preflight_restore(
        snapshot=snapshot,
        current_registry_digest="r" * 64,
        current_authority_graph_digest="g" * 64,
        current_artifact_graph_digest="a" * 64,
        current_handoff_frontier_digest="h" * 64,
        current_component_versions={"external.operations": "1.0.0", "external.research": "1.0.0"},
    )
    assert exact.accepted
    assert not exact.reason_codes

    drifted = preflight_restore(
        snapshot=snapshot,
        current_registry_digest="x" * 64,
        current_authority_graph_digest="y" * 64,
        current_artifact_graph_digest="a" * 64,
        current_handoff_frontier_digest="h" * 64,
        current_component_versions={"external.operations": "1.0.1", "external.research": "1.0.0"},
    )
    assert not drifted.accepted
    assert "REGISTRY_DIGEST_DRIFT" in drifted.reason_codes
    assert "AUTHORITY_GRAPH_DIGEST_DRIFT" in drifted.reason_codes
    assert "COMPONENT_VERSION_DRIFT" in drifted.reason_codes


def test_restore_snapshot_recomputes_identity_and_rejects_bool_or_tampering():
    snapshot = ExternalCoreRestoreSnapshot.create(
        registry_digest="r" * 64,
        authority_graph_digest="g" * 64,
        artifact_graph_digest="a" * 64,
        handoff_frontier_digest="h" * 64,
        component_versions={"external.research": "1.0.0"},
    )
    assert ExternalCoreRestoreSnapshot.from_state(snapshot.to_state()) == snapshot
    forged = copy.deepcopy(snapshot.to_state())
    forged["snapshot_id"] = "restore-snapshot-forged"
    with pytest.raises(ValueError, match="snapshot identity"):
        ExternalCoreRestoreSnapshot.from_state(forged)


def test_audit_detects_orphan_handoff_and_negative_lineage_without_evidence():
    research, planning, graph = _research_to_planning()
    orphan = _handoff(predecessors=("external-handoff-missing",))
    trace = CognitiveWorkTrace("trace-audit")
    trace.append_node(
        component_id="external.research",
        subject_id="failed-research",
        subject_digest="f" * 64,
        status="negative",
        predecessor_node_ids=(),
        handoff_id=None,
        evidence_refs=(),
        limitations=("failed challenge",),
    )
    report = audit_external_core(
        manifests=(research, planning),
        authority_graph=graph,
        handoffs=(orphan,),
        traces=(trace,),
        current_source_state_digests={orphan.producer_component_id: orphan.source_state_digest},
        current_evidence_digests={"evidence-1": "e" * 64},
        current_artifact_digests={"artifact-1": "a" * 64},
        current_freshness_fences={orphan.producer_component_id: "epoch:10"},
    )
    codes = {finding.code for finding in report.findings}
    assert "ORPHAN_HANDOFF" in codes
    assert "NEGATIVE_LINEAGE_WITHOUT_EVIDENCE" in codes
    assert not report.clean


def test_audit_surfaces_duplicate_writer_and_stale_handoff_without_mutating_inputs():
    a = _manifest("external.a", ExternalCoreFamily.A, resources=("resource:x",))
    b = _manifest("external.b", ExternalCoreFamily.B, resources=("resource:x",))
    graph = ExternalAuthorityGraph((a, b), ())
    digest_before = graph.digest

    report = audit_external_core(
        manifests=(a, b),
        authority_graph=graph,
        handoffs=(),
        traces=(),
        current_source_state_digests={},
        current_evidence_digests={},
        current_artifact_digests={},
        current_freshness_fences={},
    )
    assert "DUPLICATE_CANONICAL_WRITER" in {finding.code for finding in report.findings}
    assert graph.digest == digest_before

    research, planning, clean_graph = _research_to_planning()
    handoff = _handoff()
    stale = audit_external_core(
        manifests=(research, planning),
        authority_graph=clean_graph,
        handoffs=(handoff,),
        traces=(),
        current_source_state_digests={"external.research": "x" * 64},
        current_evidence_digests={"evidence-1": "e" * 64},
        current_artifact_digests={"artifact-1": "a" * 64},
        current_freshness_fences={"external.research": "epoch:10"},
    )
    stale_codes = {finding.code for finding in stale.findings}
    assert "STALE_HANDOFF" in stale_codes


def test_audit_report_is_deterministic_under_input_ordering():
    research, planning, graph = _research_to_planning()
    handoff = _handoff()
    kwargs = dict(
        authority_graph=graph,
        handoffs=(handoff,),
        traces=(),
        current_source_state_digests={"external.research": handoff.source_state_digest},
        current_evidence_digests={"evidence-1": "e" * 64},
        current_artifact_digests={"artifact-1": "a" * 64},
        current_freshness_fences={"external.research": "epoch:10"},
    )
    first = audit_external_core(manifests=(research, planning), **kwargs)
    second = audit_external_core(manifests=(planning, research), **kwargs)
    assert first.digest == second.digest
    assert first.findings == second.findings
