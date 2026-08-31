from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.external_core.assurance_provenance_truth import ProvenanceTruthAssuranceGate
from nolane.external_core.epistemic_provenance_truth import ProvenanceEpistemicJudge
from nolane.external_core.evidence_provenance_truth import (
    SourceProvenanceRegistry,
    SourceProvenanceRevision,
)
from nolane.external_core.evidence_temporal_truth import TemporalEvidenceView
from nolane.external_core.evidence_truth import (
    EvidenceChannel,
    EvidenceLedger,
    EvidencePolarity,
    TruthEvidence,
)
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_provenance_truth import (
    PROVENANCE_BINDING_MODE,
    ProvenanceTruthVerificationLedger,
    ProvenanceTruthVerificationReceipt,
)
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


def _revision(
    source_id: str,
    controller_id: str,
    *,
    revision: int = 1,
    predecessor_digest: str = "",
    parents: tuple[str, ...] = (),
) -> SourceProvenanceRevision:
    return SourceProvenanceRevision.create(
        source_id=source_id,
        revision=revision,
        predecessor_digest=predecessor_digest,
        controller_id=controller_id,
        parent_source_ids=parents,
    )


def _base_state(*, verifier_controllers: tuple[str, str, str]):
    evidence = EvidenceLedger()
    knowledge = KnowledgeLedger()
    relation_semantics = RelationSemanticsRegistry()
    evidence_temporal = TemporalEvidenceView()
    knowledge_temporal = TemporalKnowledgeView()
    provenance = SourceProvenanceRegistry()
    context = TemporalContext.create(as_of=AS_OF)

    evidence.record(
        TruthEvidence.create(
            evidence_id="claim-support",
            subject_id="claim-critical",
            source_id="claim-source",
            source_family="claim-family",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="claim-support-payload",
        )
    )
    provenance.register(_revision("claim-source", "claim-controller"))
    knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-critical",
            subject="system",
            relation="is_safe",
            object="yes",
            risk=KnowledgeRisk.CRITICAL,
            evidence_ids=("claim-support",),
        )
    )

    channels = (
        EvidenceChannel.TEST,
        EvidenceChannel.REPRODUCTION,
        EvidenceChannel.ADVERSARIAL,
    )
    for index, (controller_id, channel) in enumerate(zip(verifier_controllers, channels), start=1):
        verifier_id = f"verifier-{index}"
        evidence_id = f"verification-evidence-{index}"
        provenance.register(_revision(verifier_id, controller_id))
        evidence.record(
            TruthEvidence.create(
                evidence_id=evidence_id,
                subject_id="claim-critical",
                source_id=verifier_id,
                source_family=f"legacy-family-{index}",
                channel=channel,
                polarity=EvidencePolarity.SUPPORT,
                payload_digest=f"verification-payload-{index}",
            )
        )

    scope = ProvenanceEpistemicJudge().relation_aware_temporal_scope(
        "claim-critical",
        temporal_context=context,
        knowledge=knowledge,
        evidence=evidence,
        relation_semantics=relation_semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        source_provenance=provenance,
    )
    verification = ProvenanceTruthVerificationLedger()
    for index, channel in enumerate(channels, start=1):
        verifier_id = f"verifier-{index}"
        verification.record(
            ProvenanceTruthVerificationReceipt.create(
                receipt_id=f"receipt-{index}",
                claim_id="claim-critical",
                verifier_id=verifier_id,
                channel=channel,
                passed=True,
                scope_digest=scope.digest,
                temporal_context_digest=context.digest,
                as_of=context.as_of,
                evidence_ids=(f"verification-evidence-{index}",),
                source_provenance_digest=provenance.projection_digest((verifier_id,)),
            )
        )

    return {
        "context": context,
        "knowledge": knowledge,
        "evidence": evidence,
        "relation_semantics": relation_semantics,
        "knowledge_temporal": knowledge_temporal,
        "evidence_temporal": evidence_temporal,
        "provenance": provenance,
        "scope": scope,
        "verification": verification,
    }


def _close(state):
    return ProvenanceTruthAssuranceGate().close(
        claim_id="claim-critical",
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        verification=state["verification"],
    )


def test_a11_same_controller_aliases_collapse_to_one_independent_source():
    registry = SourceProvenanceRegistry()
    registry.register(_revision("source-a", "controller-root"))
    registry.register(_revision("source-b", "controller-root"))
    registry.register(_revision("source-c", "controller-root"))

    assert registry.root_controllers("source-a") == ("controller-root",)
    assert registry.independence_key("source-a") == "controller-root"
    assert registry.independence_key("source-b") == "controller-root"
    assert registry.independence_key("source-c") == "controller-root"


def test_a11_mirror_collapses_and_multi_controller_aggregate_mints_no_independence():
    registry = SourceProvenanceRegistry()
    registry.register(_revision("root-a", "controller-a"))
    registry.register(_revision("root-b", "controller-b"))
    registry.register(_revision("mirror-a", "controller-a", parents=("root-a",)))
    registry.register(
        _revision(
            "aggregate",
            "aggregate-controller",
            parents=("root-a", "root-b"),
        )
    )

    assert registry.root_controllers("mirror-a") == ("controller-a",)
    assert registry.independence_key("mirror-a") == "controller-a"
    assert registry.root_controllers("aggregate") == (
        "aggregate-controller",
        "controller-a",
        "controller-b",
    )
    assert registry.independence_key("aggregate") is None


def test_a11_provenance_revision_sequence_cycle_and_restore_fail_closed():
    registry = SourceProvenanceRegistry()
    first = registry.register(_revision("source-a", "controller-a"))
    registry.register(_revision("source-b", "controller-b", parents=("source-a",)))

    with pytest.raises(ValueError, match="predecessor"):
        registry.register(
            _revision(
                "source-a",
                "controller-a",
                revision=2,
                predecessor_digest="forged",
            )
        )

    with pytest.raises(ValueError, match="advance exactly once"):
        registry.register(
            _revision(
                "source-a",
                "controller-a",
                revision=3,
                predecessor_digest=first.digest,
            )
        )

    with pytest.raises(ValueError, match="cycle"):
        registry.register(
            _revision(
                "source-a",
                "controller-a",
                revision=2,
                predecessor_digest=first.digest,
                parents=("source-b",),
            )
        )

    state = registry.to_state()
    duplicated = deepcopy(state)
    duplicated["revisions"].append(deepcopy(duplicated["revisions"][0]))
    with pytest.raises(ValueError, match="duplicate serialized source provenance revision"):
        SourceProvenanceRegistry.from_state(duplicated)


def test_a11_relevant_projection_ignores_unrelated_revision_but_stales_on_relevant_revision():
    registry = SourceProvenanceRegistry()
    source = registry.register(_revision("source-a", "controller-a"))
    unrelated = registry.register(_revision("source-x", "controller-x"))
    before = registry.projection_digest(("source-a",))

    registry.register(
        _revision(
            "source-x",
            "controller-x",
            revision=2,
            predecessor_digest=unrelated.digest,
            parents=(),
        )
    )
    assert registry.projection_digest(("source-a",)) == before

    registry.register(
        _revision(
            "source-a",
            "controller-a",
            revision=2,
            predecessor_digest=source.digest,
            parents=(),
        )
    )
    assert registry.projection_digest(("source-a",)) != before


def test_a11_v5_receipt_has_no_legacy_source_family_escape_hatch():
    state = _base_state(verifier_controllers=("controller-1", "controller-2", "controller-3"))
    receipt = state["verification"].receipts("claim-critical")[0]
    assert receipt.binding_mode == PROVENANCE_BINDING_MODE
    assert "source_family" not in receipt.to_state()

    forged = receipt.to_state()
    forged["source_family"] = "forged-independent-family"
    with pytest.raises(ValueError, match="unexpected provenance verification binding field"):
        ProvenanceTruthVerificationReceipt.from_state(forged)


def test_a11_three_aliases_under_one_controller_cannot_close_critical_claim():
    state = _base_state(
        verifier_controllers=("shared-controller", "shared-controller", "shared-controller")
    )
    certificate = _close(state)

    assert certificate.closed is False
    assert "insufficient_independent_verification" in certificate.reasons
    coverage = state["verification"].coverage(
        "claim-critical",
        scope=state["scope"],
        temporal_context=state["context"],
        evidence=state["evidence"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
    )
    assert coverage.independent_source_count == 1
    assert coverage.channel_count == 3


def test_a11_three_distinct_controller_roots_and_channels_can_close_critical_claim():
    state = _base_state(
        verifier_controllers=("controller-1", "controller-2", "controller-3")
    )
    certificate = _close(state)

    assert certificate.closed is True
    assert certificate.reasons == ()
    assert ProvenanceTruthAssuranceGate().validate_certificate(
        certificate,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        verification=state["verification"],
    )


def test_a11_relevant_provenance_revision_invalidates_certificate_but_unrelated_revision_does_not():
    state = _base_state(
        verifier_controllers=("controller-1", "controller-2", "controller-3")
    )
    gate = ProvenanceTruthAssuranceGate()
    certificate = _close(state)
    assert certificate.closed

    state["provenance"].register(_revision("unrelated-source", "unrelated-controller"))
    assert gate.validate_certificate(
        certificate,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        verification=state["verification"],
    )

    current = state["provenance"].current("verifier-1")
    state["provenance"].register(
        _revision(
            "verifier-1",
            "controller-1",
            revision=2,
            predecessor_digest=current.digest,
        )
    )
    assert not gate.validate_certificate(
        certificate,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        verification=state["verification"],
    )
