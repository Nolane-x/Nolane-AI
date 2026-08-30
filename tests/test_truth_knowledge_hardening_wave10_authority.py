from __future__ import annotations

import copy

import pytest

import nolane.external_core.assurance_truth as assurance_truth
import nolane.external_core.epistemic_truth as epistemic_truth
import nolane.external_core.knowledge_truth as knowledge_truth
import nolane.external_core.verification_truth as verification_truth
from nolane.external_core.assurance_truth import TruthAssuranceGate, TruthClosureCertificate
from nolane.external_core.epistemic_truth import EpistemicJudge
from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.verification_truth import (
    RELATION_AWARE_BINDING_MODE,
    TruthVerificationLedger,
    TruthVerificationReceipt,
)
from nolane.memory import knowledge as canonical_knowledge
from nolane.memory.knowledge import (
    EvidenceChunk,
    EvidenceLedger as CanonicalKnowledgeEvidenceLedger,
    RelationCardinality,
    RelationSemanticsRegistry,
    RelationSemanticsRevision,
)
from nolane.metadata.implementation_status import ImplementationStatus, build_component_implementation_ledger


def _policy(registry: RelationSemanticsRegistry, relation: str, cardinality: RelationCardinality):
    return registry.record(RelationSemanticsRevision.create(
        relation=relation, revision=1, cardinality=cardinality,
    ))


def _truth_evidence(evidence_id: str, claim_id: str, source_id: str, family: str, channel: EvidenceChannel):
    return TruthEvidence.create(
        evidence_id=evidence_id,
        subject_id=claim_id,
        source_id=source_id,
        source_family=family,
        channel=channel,
        polarity=EvidencePolarity.SUPPORT,
        payload_digest=f"payload:{evidence_id}",
    )


def test_a10_external_knowledge_manifest_revision_matches_parent_implementation():
    ledger = build_component_implementation_ledger()
    row = ledger["external.knowledge"]
    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.memory.knowledge"
    assert row.component_version == canonical_knowledge.COMPONENT_VERSION == "0.0.2"


def test_a10_truth_helpers_do_not_create_new_component_authority():
    assert not hasattr(knowledge_truth, "COMPONENT_ID")
    assert not hasattr(epistemic_truth, "COMPONENT_ID")
    assert not hasattr(verification_truth, "COMPONENT_ID")
    assert not hasattr(assurance_truth, "COMPONENT_ID")
    assert canonical_knowledge.RelationSemanticsRegistry.__module__ == "nolane.memory.knowledge"


def test_a10_claim_cannot_self_author_relation_cardinality():
    with pytest.raises(TypeError):
        KnowledgeClaim.create(
            claim_id="claim.a",
            subject="alice",
            relation="speaks",
            object="English",
            cardinality=RelationCardinality.MULTI_VALUED,
        )


def test_a10_parent_knowledge_exposes_additive_relation_aware_conflicts_without_changing_legacy_conflicts():
    ledger = CanonicalKnowledgeEvidenceLedger()
    ledger._claims[("alice", "speaks")].extend((
        ("English", "chunk-en"),
        ("French", "chunk-fr"),
    ))
    ledger._claims[("server", "status")].extend((
        ("online", "chunk-online"),
        ("offline", "chunk-offline"),
    ))

    # Historical compatibility API preserves its original same-key behavior.
    assert len(ledger.conflicts()) == 2

    semantics = RelationSemanticsRegistry()
    _policy(semantics, "speaks", RelationCardinality.MULTI_VALUED)
    _policy(semantics, "status", RelationCardinality.EXCLUSIVE)

    conflicts = ledger.semantic_conflicts(semantics)
    assert [(row.subject, row.relation, row.objects) for row in conflicts] == [
        ("server", "status", ("online", "offline")),
    ]


def test_a10_unspecified_ancestor_ambiguity_blocks_descendant_v3_closure():
    evidence = EvidenceLedger()
    evidence.record(_truth_evidence("parent-e1", "claim.parent", "parent-a", "parent-family-a", EvidenceChannel.TEST))
    evidence.record(_truth_evidence("parent-e2", "claim.parent.alt", "parent-b", "parent-family-b", EvidenceChannel.AUDIT))
    evidence.record(_truth_evidence("child-e", "claim.child", "child-source", "child-family", EvidenceChannel.REPRODUCTION))

    knowledge = KnowledgeLedger()
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.parent", subject="parent", relation="state", object="valid",
        evidence_ids=("parent-e1",),
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.parent.alt", subject="parent", relation="state", object="invalid",
        evidence_ids=("parent-e2",),
    ))
    knowledge.add(KnowledgeClaim.create(
        claim_id="claim.child", subject="child", relation="depends", object="parent",
        evidence_ids=("child-e",), parent_claim_ids=("claim.parent",),
    ))

    semantics = RelationSemanticsRegistry()
    _policy(semantics, "depends", RelationCardinality.EXCLUSIVE)
    scope = EpistemicJudge().relation_aware_scope(
        "claim.child", knowledge=knowledge, evidence=evidence, relation_semantics=semantics,
    )
    verification = TruthVerificationLedger()
    verification.record(TruthVerificationReceipt.create(
        receipt_id="child-v3",
        claim_id="claim.child",
        verifier_id="child-source",
        source_family="child-family",
        channel=EvidenceChannel.REPRODUCTION,
        passed=True,
        binding_mode=RELATION_AWARE_BINDING_MODE,
        scope_digest=scope.digest,
        evidence_ids=("child-e",),
    ))

    certificate = TruthAssuranceGate().close_live(
        claim_id="claim.child", knowledge=knowledge, evidence=evidence,
        verification=verification, relation_semantics=semantics,
    )
    assert not certificate.closed
    assert "relation_semantics_lineage_unspecified" in certificate.reasons


def test_a10_v3_serialization_rejects_global_binding_smuggling():
    receipt = TruthVerificationReceipt.create(
        receipt_id="v3",
        claim_id="claim.a",
        verifier_id="runner",
        source_family="family",
        channel=EvidenceChannel.TEST,
        passed=True,
        binding_mode=RELATION_AWARE_BINDING_MODE,
        scope_digest="scope-v3",
        evidence_ids=("e1",),
    )
    receipt_state = copy.deepcopy(receipt.to_state())
    receipt_state["knowledge_digest"] = "smuggled-global"
    with pytest.raises(ValueError, match="cannot contain global bindings"):
        TruthVerificationReceipt.from_state(receipt_state)

    certificate = TruthClosureCertificate.create(
        claim_id="claim.a",
        risk=KnowledgeRisk.LOW,
        binding_mode=RELATION_AWARE_BINDING_MODE,
        scope_digest="scope-v3",
        verification_scope_digest="verification-v3",
        verification_receipt_ids=("v3",),
        epistemic_debt_ids=(),
        closed=True,
        reasons=(),
    )
    certificate_state = copy.deepcopy(certificate.to_state())
    certificate_state["epistemic_digest"] = "smuggled-global"
    with pytest.raises(ValueError, match="cannot contain global bindings"):
        TruthClosureCertificate.from_state(certificate_state)
