from __future__ import annotations

from nolane.external_core.assurance_justification_truth import JustificationTruthAssuranceGate
from nolane.external_core.epistemic_justification_truth import JustificationEpistemicJudge
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
from nolane.external_core.knowledge_justification_truth import (
    KnowledgeJustificationRegistry,
    KnowledgeJustificationRevision,
)
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger, KnowledgeRisk
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_justification_truth import (
    JustificationTruthVerificationLedger,
    JustificationTruthVerificationReceipt,
)
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


def _source(registry: SourceProvenanceRegistry, source_id: str, controller_id: str) -> None:
    registry.register(
        SourceProvenanceRevision.create(
            source_id=source_id,
            revision=1,
            predecessor_digest="",
            controller_id=controller_id,
            parent_source_ids=(),
        )
    )


def _evidence(
    ledger: EvidenceLedger,
    *,
    evidence_id: str,
    claim_id: str,
    source_id: str,
    channel: EvidenceChannel = EvidenceChannel.OBSERVATION,
) -> None:
    ledger.record(
        TruthEvidence.create(
            evidence_id=evidence_id,
            subject_id=claim_id,
            source_id=source_id,
            source_family=f"legacy:{source_id}",
            channel=channel,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest=f"payload:{evidence_id}",
        )
    )


def _base():
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    provenance = SourceProvenanceRegistry()
    justifications = KnowledgeJustificationRegistry()
    relation_semantics = RelationSemanticsRegistry()
    knowledge_temporal = TemporalKnowledgeView()
    evidence_temporal = TemporalEvidenceView()
    context = TemporalContext.create(as_of=AS_OF)
    return {
        "knowledge": knowledge,
        "evidence": evidence,
        "provenance": provenance,
        "justifications": justifications,
        "relation_semantics": relation_semantics,
        "knowledge_temporal": knowledge_temporal,
        "evidence_temporal": evidence_temporal,
        "context": context,
    }


def _scope(state, claim_id: str):
    return JustificationEpistemicJudge().relation_aware_temporal_scope(
        claim_id,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
    )


def _one_verifier(state, *, claim_id: str, scope):
    verifier_id = "external-verifier"
    verification_evidence_id = "verification-evidence"
    _source(state["provenance"], verifier_id, "external-verifier-controller")
    _evidence(
        state["evidence"],
        evidence_id=verification_evidence_id,
        claim_id=claim_id,
        source_id=verifier_id,
        channel=EvidenceChannel.TEST,
    )
    ledger = JustificationTruthVerificationLedger()
    ledger.record(
        JustificationTruthVerificationReceipt.create(
            receipt_id="receipt",
            claim_id=claim_id,
            verifier_id=verifier_id,
            channel=EvidenceChannel.TEST,
            passed=True,
            scope_digest=scope.digest,
            temporal_context_digest=state["context"].digest,
            as_of=state["context"].as_of,
            evidence_ids=(verification_evidence_id,),
            source_provenance_digest=state["provenance"].projection_digest((verifier_id,)),
        )
    )
    return ledger


def _close(state, *, claim_id: str, verification):
    return JustificationTruthAssuranceGate().close(
        claim_id=claim_id,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        verification=verification,
    )


def test_a12_parent_on_live_supported_path_remains_mandatory():
    state = _base()
    parent = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="live-parent",
            subject="parent",
            relation="state",
            object="ok",
            evidence_ids=("parent-support",),
        )
    )
    target = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="target",
            subject="system",
            relation="ready",
            object="yes",
            risk=KnowledgeRisk.LOW,
            evidence_ids=("dead-legacy-target",),
        )
    )

    for evidence_id, claim_id, source_id, controller_id in (
        ("parent-support", parent.claim_id, "parent-source", "parent-controller"),
        ("dead-legacy-target", target.claim_id, "legacy-source", "legacy-controller"),
        ("explicit-target-support", target.claim_id, "target-source", "target-controller"),
    ):
        _source(state["provenance"], source_id, controller_id)
        _evidence(
            state["evidence"],
            evidence_id=evidence_id,
            claim_id=claim_id,
            source_id=source_id,
        )

    state["evidence"].revoke("dead-legacy-target", reason="force explicit live path")
    state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-live-parent",
            claim=target,
            evidence_ids=("explicit-target-support",),
            parent_claim_ids=(parent.claim_id,),
        ),
        knowledge=state["knowledge"],
    )

    scope = _scope(state, target.claim_id)
    assert scope.justification_status("j-live-parent").status == "supported"
    verification = _one_verifier(state, claim_id=target.claim_id, scope=scope)
    certificate = _close(state, claim_id=target.claim_id, verification=verification)
    assert certificate.closed is True

    state["evidence"].revoke("parent-support", reason="live parent withdrawn")
    fresh_scope = _scope(state, target.claim_id)
    fresh = _close(state, claim_id=target.claim_id, verification=verification)

    assert fresh_scope.justification_status("j-live-parent").status == "dead"
    assert fresh_scope.assessment(target.claim_id).disposition.value == "unknown"
    assert fresh.closed is False
    assert "epistemic_claim_not_supported" in fresh.reasons
    assert JustificationTruthAssuranceGate().validate_certificate(
        certificate,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        verification=verification,
    ) is False


def test_a12_scope_and_certificate_ignore_unrelated_justification_revision_but_stale_on_relevant_revision():
    state = _base()
    target = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="target",
            subject="system",
            relation="state",
            object="ok",
            risk=KnowledgeRisk.LOW,
            evidence_ids=("target-legacy-support",),
        )
    )
    for evidence_id, source_id, controller_id in (
        ("target-legacy-support", "target-legacy-source", "target-legacy-controller"),
        ("target-alt-support", "target-alt-source", "target-alt-controller"),
    ):
        _source(state["provenance"], source_id, controller_id)
        _evidence(
            state["evidence"],
            evidence_id=evidence_id,
            claim_id=target.claim_id,
            source_id=source_id,
        )

    first = state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-target-alt",
            claim=target,
            evidence_ids=("target-alt-support",),
        ),
        knowledge=state["knowledge"],
    )
    scope = _scope(state, target.claim_id)
    verification = _one_verifier(state, claim_id=target.claim_id, scope=scope)
    certificate = _close(state, claim_id=target.claim_id, verification=verification)
    assert certificate.closed is True

    unrelated = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="unrelated",
            subject="other",
            relation="state",
            object="ok",
            evidence_ids=("unrelated-legacy-basis",),
        )
    )
    state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-unrelated",
            claim=unrelated,
            evidence_ids=(),
        ),
        knowledge=state["knowledge"],
    )

    judge = JustificationEpistemicJudge()
    gate = JustificationTruthAssuranceGate()
    assert judge.validate_scope(
        scope,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
    ) is True
    assert gate.validate_certificate(
        certificate,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        verification=verification,
    ) is True

    state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-target-alt",
            claim=target,
            revision=2,
            predecessor_digest=first.digest,
            evidence_ids=("target-alt-support",),
            enabled=False,
        ),
        knowledge=state["knowledge"],
    )

    assert judge.validate_scope(
        scope,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
    ) is False
    assert gate.validate_certificate(
        certificate,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        verification=verification,
    ) is False
