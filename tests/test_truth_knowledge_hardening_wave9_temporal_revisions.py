from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.external_core.assurance_temporal_truth import TemporalTruthAssuranceGate
from nolane.external_core.epistemic_temporal_truth import TemporalEpistemicJudge
from nolane.external_core.evidence_temporal_truth import EvidenceTemporalBinding, TemporalEvidenceView
from nolane.external_core.evidence_truth import EvidenceChannel, EvidenceLedger, EvidencePolarity, TruthEvidence
from nolane.external_core.knowledge_temporal_truth import KnowledgeTemporalBinding, TemporalKnowledgeView
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_temporal_truth import (
    TemporalTruthVerificationLedger,
    TemporalTruthVerificationReceipt,
)
from nolane.memory.knowledge import RelationCardinality, RelationSemanticsRegistry, RelationSemanticsRevision


T0 = "2020-01-01T00:00:00Z"
T1 = "2025-01-01T00:00:00Z"
T2 = "2030-01-01T00:00:00Z"


def evidence(evidence_id: str, claim_id: str, *, source: str = "runner", family: str = "family") -> TruthEvidence:
    return TruthEvidence.create(
        evidence_id=evidence_id,
        subject_id=claim_id,
        source_id=source,
        source_family=family,
        channel=EvidenceChannel.TEST,
        polarity=EvidencePolarity.SUPPORT,
        payload_digest=f"payload:{evidence_id}",
    )


def claim(claim_id: str, evidence_id: str) -> KnowledgeClaim:
    return KnowledgeClaim.create(
        claim_id=claim_id,
        subject=claim_id,
        relation="state",
        object="valid",
        evidence_ids=(evidence_id,),
    )


def relations() -> RelationSemanticsRegistry:
    registry = RelationSemanticsRegistry()
    registry.record(RelationSemanticsRevision.create(
        relation="state",
        revision=1,
        cardinality=RelationCardinality.EXCLUSIVE,
    ))
    return registry


def test_a9_evidence_temporal_revisions_are_append_only_and_predecessor_bound():
    row = evidence("e1", "claim.alpha")
    view = TemporalEvidenceView()
    first = view.bind(row, valid_from=T0, valid_until=None)
    assert first.revision == 1
    assert first.previous_digest == ""

    second = view.revise(row, valid_from=T0, valid_until=T2)
    assert second.revision == 2
    assert second.previous_digest == first.digest
    assert view.binding("e1") == second
    assert view.revisions("e1") == (first, second)

    skipped = EvidenceTemporalBinding.create(
        row,
        revision=4,
        previous_digest=second.digest,
        valid_from=T0,
        valid_until=T1,
    )
    with pytest.raises(ValueError, match="sequence|revision"):
        view.record(skipped)

    wrong_parent = EvidenceTemporalBinding.create(
        row,
        revision=3,
        previous_digest="forged-predecessor",
        valid_from=T0,
        valid_until=T1,
    )
    with pytest.raises(ValueError, match="predecessor"):
        view.record(wrong_parent)


def test_a9_knowledge_temporal_revisions_are_append_only_and_predecessor_bound():
    row = claim("claim.alpha", "e1")
    view = TemporalKnowledgeView()
    first = view.bind(row, valid_from=T0, valid_until=None)
    second = view.revise(row, valid_from=T0, valid_until=T2)
    assert first.revision == 1
    assert second.revision == 2
    assert second.previous_digest == first.digest
    assert view.binding(row.claim_id) == second
    assert view.revisions(row.claim_id) == (first, second)

    collision = KnowledgeTemporalBinding.create(
        row,
        revision=2,
        previous_digest=first.digest,
        valid_from=T0,
        valid_until=T1,
    )
    with pytest.raises(ValueError, match="collision|rebind"):
        view.record(collision)


def test_a9_temporal_revision_serialization_preserves_history_and_rejects_duplicate_identity():
    ev = evidence("e1", "claim.alpha")
    view = TemporalEvidenceView()
    view.bind(ev, valid_from=T0, valid_until=None)
    view.revise(ev, valid_from=T0, valid_until=T2)
    restored = TemporalEvidenceView.from_state(deepcopy(view.to_state()))
    assert restored.revisions("e1") == view.revisions("e1")

    duplicated = deepcopy(view.to_state())
    duplicated["bindings"].append(deepcopy(duplicated["bindings"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        TemporalEvidenceView.from_state(duplicated)


def test_a9_revising_relevant_validity_invalidates_old_certificate_without_mutating_base_evidence():
    ev = EvidenceLedger()
    e1 = evidence("e1", "claim.alpha")
    ev.record(e1)
    evidence_temporal = TemporalEvidenceView()
    evidence_temporal.bind(e1, valid_from=T0, valid_until=None)

    knowledge = KnowledgeLedger()
    c1 = claim("claim.alpha", "e1")
    knowledge.add(c1)
    knowledge_temporal = TemporalKnowledgeView()
    knowledge_temporal.bind(c1, valid_from=T0, valid_until=None)

    context = TemporalContext.create(as_of=T1)
    relation_semantics = relations()
    scope = TemporalEpistemicJudge().relation_aware_dependency_scope(
        c1.claim_id,
        temporal_context=context,
        knowledge=knowledge,
        evidence=ev,
        relation_semantics=relation_semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
    )
    verification = TemporalTruthVerificationLedger()
    verification.record(TemporalTruthVerificationReceipt.create(
        receipt_id="v4",
        claim_id=c1.claim_id,
        verifier_id=e1.source_id,
        source_family=e1.source_family,
        channel=e1.channel,
        passed=True,
        scope_digest=scope.digest,
        temporal_context_digest=context.digest,
        as_of=context.as_of,
        evidence_ids=(e1.evidence_id,),
    ))
    gate = TemporalTruthAssuranceGate()
    certificate = gate.close(
        claim_id=c1.claim_id,
        temporal_context=context,
        knowledge=knowledge,
        evidence=ev,
        relation_semantics=relation_semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        verification=verification,
    )
    assert certificate.closed
    original_evidence_digest = ev.digest

    evidence_temporal.revise(e1, valid_from=T0, valid_until=T1)
    assert ev.digest == original_evidence_digest
    assert evidence_temporal.state_at(
        e1.evidence_id,
        evidence=ev,
        temporal_context=context,
    ) == "expired"
    assert not gate.validate_certificate(
        certificate,
        temporal_context=context,
        knowledge=knowledge,
        evidence=ev,
        relation_semantics=relation_semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        verification=verification,
    )


def test_a9_unrelated_temporal_revision_does_not_stale_scoped_certificate():
    ev = EvidenceLedger()
    target_e = evidence("target-e", "claim.target", source="target", family="target-family")
    other_e = evidence("other-e", "claim.other", source="other", family="other-family")
    ev.record(target_e)
    ev.record(other_e)
    evidence_temporal = TemporalEvidenceView()
    evidence_temporal.bind(other_e, valid_from=T0, valid_until=None)

    knowledge = KnowledgeLedger()
    target = claim("claim.target", "target-e")
    other = claim("claim.other", "other-e")
    knowledge.add(target)
    knowledge.add(other)
    knowledge_temporal = TemporalKnowledgeView()
    context = TemporalContext.create(as_of=T1)
    relation_semantics = relations()
    scope = TemporalEpistemicJudge().relation_aware_dependency_scope(
        target.claim_id,
        temporal_context=context,
        knowledge=knowledge,
        evidence=ev,
        relation_semantics=relation_semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
    )
    verification = TemporalTruthVerificationLedger()
    verification.record(TemporalTruthVerificationReceipt.create(
        receipt_id="target-v4",
        claim_id=target.claim_id,
        verifier_id=target_e.source_id,
        source_family=target_e.source_family,
        channel=target_e.channel,
        passed=True,
        scope_digest=scope.digest,
        temporal_context_digest=context.digest,
        as_of=context.as_of,
        evidence_ids=(target_e.evidence_id,),
    ))
    gate = TemporalTruthAssuranceGate()
    certificate = gate.close(
        claim_id=target.claim_id,
        temporal_context=context,
        knowledge=knowledge,
        evidence=ev,
        relation_semantics=relation_semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        verification=verification,
    )
    assert certificate.closed

    evidence_temporal.revise(other_e, valid_from=T0, valid_until=T2)
    assert gate.validate_certificate(
        certificate,
        temporal_context=context,
        knowledge=knowledge,
        evidence=ev,
        relation_semantics=relation_semantics,
        knowledge_temporal=knowledge_temporal,
        evidence_temporal=evidence_temporal,
        verification=verification,
    )
