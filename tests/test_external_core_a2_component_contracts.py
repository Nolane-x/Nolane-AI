from __future__ import annotations

import copy

import pytest

from nolane.external_core.authority_graph import (
    AuthorityEdge,
    AuthorityRelation,
    ExternalAuthorityGraph,
)
from nolane.external_core.component_contracts import (
    ExternalComponentManifest,
    ExternalCoreFamily,
)


def _manifest(
    component_id: str,
    family: ExternalCoreFamily,
    *,
    authorities: tuple[str, ...] = (),
    forbidden: tuple[str, ...] = (),
    resources: tuple[str, ...] = (),
    produces: tuple[str, ...] = (),
    consumes: tuple[str, ...] = (),
):
    return ExternalComponentManifest.create(
        component_id=component_id,
        component_version="1.0.0",
        family=family,
        protocol_versions={"core": "1"},
        consumes_contracts=consumes,
        produces_contracts=produces,
        authority_capabilities=authorities,
        forbidden_authorities=forbidden,
        mutable_resources=resources,
        evidence_inputs=("evidence",),
        evidence_outputs=("receipt",),
        restore_protocol="exact-revalidation",
        compatibility_floor="1.0.0",
        compatibility_ceiling="1.9.9",
    )


def test_manifest_is_content_addressed_and_restore_recomputes_identity():
    row = _manifest(
        "external.research",
        ExternalCoreFamily.G,
        authorities=("research_synthesis",),
        forbidden=("assure", "execute"),
        resources=("research:ledger",),
        produces=("research-input",),
    )
    assert row.manifest_digest
    assert ExternalComponentManifest.from_state(row.to_state()) == row

    forged = copy.deepcopy(row.to_state())
    forged["manifest_digest"] = "forged"
    with pytest.raises(ValueError, match="manifest digest"):
        ExternalComponentManifest.from_state(forged)


def test_manifest_rejects_authority_that_is_also_forbidden():
    with pytest.raises(ValueError, match="forbidden"):
        _manifest(
            "external.candidate_synthesis",
            ExternalCoreFamily.C,
            authorities=("promote",),
            forbidden=("promote", "assure"),
        )


def test_duplicate_canonical_mutable_writer_fails_closed():
    a = _manifest(
        "external.a",
        ExternalCoreFamily.A,
        authorities=("write",),
        resources=("canonical:artifact-x",),
    )
    b = _manifest(
        "external.b",
        ExternalCoreFamily.B,
        authorities=("write",),
        resources=("canonical:artifact-x",),
    )
    graph = ExternalAuthorityGraph((a, b), ())
    with pytest.raises(ValueError, match="duplicate canonical writer"):
        graph.validate()


def test_descriptive_component_cannot_gain_authority_through_edge():
    trace = _manifest(
        "external.work_trace",
        ExternalCoreFamily.G,
        forbidden=("authorize", "assure", "execute", "promote"),
        produces=("work-trace",),
    )
    acting = _manifest(
        "external.execution.control",
        ExternalCoreFamily.E,
        authorities=("execute",),
        consumes=("authorized-action",),
    )
    graph = ExternalAuthorityGraph(
        (trace, acting),
        (
            AuthorityEdge.create(
                source_component_id=trace.component_id,
                target_component_id=acting.component_id,
                relation=AuthorityRelation.AUTHORIZES_INPUT_TO,
                contract_kind="authorized-action",
            ),
        ),
    )
    findings = graph.findings()
    assert "FORBIDDEN_AUTHORITY_COMPOSITION" in {row.code for row in findings}
    with pytest.raises(ValueError, match="authority graph"):
        graph.validate()


def test_relation_cannot_launder_authority_not_declared_by_source_manifest():
    reporter = _manifest(
        "external.reporter",
        ExternalCoreFamily.G,
        authorities=("observe",),
        produces=("verification-result",),
    )
    consumer = _manifest(
        "external.consumer",
        ExternalCoreFamily.D,
        consumes=("verification-result",),
    )
    graph = ExternalAuthorityGraph(
        (reporter, consumer),
        (
            AuthorityEdge.create(
                source_component_id=reporter.component_id,
                target_component_id=consumer.component_id,
                relation=AuthorityRelation.VERIFIES,
                contract_kind="verification-result",
            ),
        ),
    )
    assert "UNDECLARED_SOURCE_AUTHORITY" in {row.code for row in graph.findings()}
    with pytest.raises(ValueError, match="UNDECLARED_SOURCE_AUTHORITY"):
        graph.validate()


def test_self_verification_and_authority_cycles_are_rejected():
    verifier = _manifest(
        "external.verification",
        ExternalCoreFamily.A,
        authorities=("verify",),
    )
    self_graph = ExternalAuthorityGraph(
        (verifier,),
        (
            AuthorityEdge.create(
                source_component_id=verifier.component_id,
                target_component_id=verifier.component_id,
                relation=AuthorityRelation.VERIFIES,
                contract_kind="verification",
            ),
        ),
    )
    assert "SELF_VERIFICATION_LOOP" in {row.code for row in self_graph.findings()}

    a = _manifest("external.a", ExternalCoreFamily.A, authorities=("authorize",))
    b = _manifest("external.b", ExternalCoreFamily.B, authorities=("authorize",))
    cyclic = ExternalAuthorityGraph(
        (a, b),
        (
            AuthorityEdge.create(
                source_component_id=a.component_id,
                target_component_id=b.component_id,
                relation=AuthorityRelation.AUTHORIZES_INPUT_TO,
                contract_kind="x",
            ),
            AuthorityEdge.create(
                source_component_id=b.component_id,
                target_component_id=a.component_id,
                relation=AuthorityRelation.AUTHORIZES_INPUT_TO,
                contract_kind="x",
            ),
        ),
    )
    assert "AUTHORITY_ESCALATION_CYCLE" in {row.code for row in cyclic.findings()}


def test_valid_graph_digest_is_deterministic_and_contract_edges_must_be_declared():
    research = _manifest(
        "external.research",
        ExternalCoreFamily.G,
        authorities=("research_synthesis",),
        forbidden=("authorize",),
        produces=("research-input",),
    )
    planning = _manifest(
        "external.planning",
        ExternalCoreFamily.D,
        authorities=("plan",),
        consumes=("research-input",),
    )
    edge = AuthorityEdge.create(
        source_component_id=research.component_id,
        target_component_id=planning.component_id,
        relation=AuthorityRelation.EVIDENCE_FOR,
        contract_kind="research-input",
    )
    graph = ExternalAuthorityGraph((research, planning), (edge,))
    assert graph.validate().clean
    assert ExternalAuthorityGraph.from_state(graph.to_state()).digest == graph.digest

    undeclared = AuthorityEdge.create(
        source_component_id=research.component_id,
        target_component_id=planning.component_id,
        relation=AuthorityRelation.EVIDENCE_FOR,
        contract_kind="unknown-contract",
    )
    bad = ExternalAuthorityGraph((research, planning), (undeclared,))
    assert "UNDECLARED_CONTRACT_EDGE" in {row.code for row in bad.findings()}
