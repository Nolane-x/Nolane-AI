from __future__ import annotations

from nolane.external_core.assurance_defeasible_truth import DefeasibleTruthAssuranceGate
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
from nolane.external_core.knowledge_undercutter_truth import (
    JustificationUndercutterRegistry,
    JustificationUndercutterRevision,
)
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_defeasible_truth import (
    DefeasibleTruthVerificationLedger,
    DefeasibleTruthVerificationReceipt,
)
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


def _prov(source_id: str, controller_id: str) -> SourceProvenanceRevision:
    return SourceProvenanceRevision.create(
        source_id=source_id,
        revision=1,
        predecessor_digest="",
        controller_id=controller_id,
        parent_source_ids=(),
    )


def _evidence(
    ledger: EvidenceLedger,
    *,
    evidence_id: str,
    subject_id: str,
    source_id: str,
    channel: EvidenceChannel = EvidenceChannel.OBSERVATION,
    polarity: EvidencePolarity = EvidencePolarity.SUPPORT,
) -> None:
    ledger.record(
        TruthEvidence.create(
            evidence_id=evidence_id,
            subject_id=subject_id,
            source_id=source_id,
            source_family=f"family:{source_id}",
            channel=channel,
            polarity=polarity,
            payload_digest=f"payload:{evidence_id}",
        )
    )


def _base(*, risk: KnowledgeRisk = KnowledgeRisk.STANDARD):
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    semantics = RelationSemanticsRegistry()
    knowledge_temporal = TemporalKnowledgeView()
    evidence_temporal = TemporalEvidenceView()
    provenance = SourceProvenanceRegistry()
    justifications = KnowledgeJustificationRegistry()
    undercutters = JustificationUndercutterRegistry()
    context = TemporalContext.create(as_of=AS_OF)

    _evidence(
        evidence,
        evidence_id="support",
        subject_id="target",
        source_id="support-source",
    )
    provenance.register(_prov("support-source", "support-controller"))
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="target",
            subject="system",
            relation="works",
            object="yes",
            risk=risk,
            evidence_ids=("support",),
        )
    )

    channel_rows = (
        ("v1", "vc1", EvidenceChannel.TEST),
        ("v2", "vc2", EvidenceChannel.REPRODUCTION),
        ("v3", "vc3", EvidenceChannel.ADVERSARIAL),
    )
    for verifier, controller, channel in channel_rows:
        provenance.register(_prov(verifier, controller))
        _evidence(
            evidence,
            evidence_id=f"verify:{verifier}",
            subject_id=claim.claim_id,
            source_id=verifier,
            channel=channel,
        )
    return {
        "knowledge": knowledge,
        "evidence": evidence,
        "semantics": semantics,
        "knowledge_temporal": knowledge_temporal,
        "evidence_temporal": evidence_temporal,
        "provenance": provenance,
        "justifications": justifications,
        "undercutters": undercutters,
        "context": context,
        "claim": claim,
        "channel_rows": channel_rows,
    }


def _scope(state):
    from nolane.external_core.epistemic_defeasible_truth import DefeasibleEpistemicJudge

    return DefeasibleEpistemicJudge().relation_aware_temporal_scope(
        state["claim"].claim_id,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
    )


def _verification(state, scope):
    ledger = DefeasibleTruthVerificationLedger()
    required = 3 if state["claim"].risk is KnowledgeRisk.CRITICAL else 1
    for verifier, _, channel in state["channel_rows"][:required]:
        ledger.record(
            DefeasibleTruthVerificationReceipt.create(
                receipt_id=f"receipt:{verifier}",
                claim_id=state["claim"].claim_id,
                verifier_id=verifier,
                channel=channel,
                passed=True,
                scope_digest=scope.digest,
                temporal_context_digest=state["context"].digest,
                as_of=state["context"].as_of,
                evidence_ids=(f"verify:{verifier}",),
                source_provenance_digest=state["provenance"].projection_digest((verifier,)),
            )
        )
    return ledger


def _certificate(state):
    scope = _scope(state)
    verification = _verification(state, scope)
    gate = DefeasibleTruthAssuranceGate()
    certificate = gate.close(
        claim_id=state["claim"].claim_id,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
        verification=verification,
    )
    return gate, scope, verification, certificate


def _valid(gate, certificate, state, verification):
    return gate.validate_certificate(
        certificate,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
        verification=verification,
    )


def test_a13_unrelated_undercutter_revision_does_not_stale_target_certificate():
    state = _base()
    gate, scope, verification, certificate = _certificate(state)
    assert certificate.closed
    assert _valid(gate, certificate, state, verification)

    unrelated = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="unrelated",
            subject="other",
            relation="state",
            object="ok",
        )
    )
    unrelated_basis = state["justifications"].legacy_basis(unrelated)
    first = state["undercutters"].register(
        JustificationUndercutterRevision.create(
            undercutter_id="u-unrelated",
            claim=unrelated,
            target_basis=unrelated_basis,
            parent_claim_ids=(state["claim"].claim_id,),
        ),
        knowledge=state["knowledge"],
        justifications=state["justifications"],
    )
    state["undercutters"].register(
        JustificationUndercutterRevision.create(
            undercutter_id="u-unrelated",
            claim=unrelated,
            target_basis=unrelated_basis,
            revision=2,
            predecessor_digest=first.digest,
            parent_claim_ids=(state["claim"].claim_id,),
            enabled=False,
        ),
        knowledge=state["knowledge"],
        justifications=state["justifications"],
    )

    assert _scope(state).digest == scope.digest
    assert _valid(gate, certificate, state, verification)


def test_a13_relevant_enable_revision_stales_certificate_and_truth_scope():
    state = _base()
    undercutter_id = "u-relevant"
    _evidence(
        state["evidence"],
        evidence_id="attack-support",
        subject_id=undercutter_id,
        source_id="attack-source",
    )
    state["provenance"].register(_prov("attack-source", "attack-controller"))
    basis = state["justifications"].legacy_basis(state["claim"])
    disabled = state["undercutters"].register(
        JustificationUndercutterRevision.create(
            undercutter_id=undercutter_id,
            claim=state["claim"],
            target_basis=basis,
            evidence_ids=("attack-support",),
            enabled=False,
        ),
        knowledge=state["knowledge"],
        justifications=state["justifications"],
    )
    gate, scope, verification, certificate = _certificate(state)
    assert certificate.closed

    state["undercutters"].register(
        JustificationUndercutterRevision.create(
            undercutter_id=undercutter_id,
            claim=state["claim"],
            target_basis=basis,
            revision=2,
            predecessor_digest=disabled.digest,
            evidence_ids=("attack-support",),
            enabled=True,
        ),
        knowledge=state["knowledge"],
        justifications=state["justifications"],
    )
    changed = _scope(state)

    assert changed.digest != scope.digest
    assert changed.assessment(state["claim"].claim_id).disposition.value == "unknown"
    assert _valid(gate, certificate, state, verification) is False


def test_a13_critical_parent_on_dead_alternative_does_not_veto_clean_live_branch():
    state = _base(risk=KnowledgeRisk.CRITICAL)
    parent = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="dead-parent",
            subject="dependency",
            relation="valid",
            object="yes",
            risk=KnowledgeRisk.CRITICAL,
        )
    )
    state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-dead-parent-branch",
            claim=state["claim"],
            parent_claim_ids=(parent.claim_id,),
        ),
        knowledge=state["knowledge"],
    )

    _, scope, _, certificate = _certificate(state)

    assert scope.justification_status("j-dead-parent-branch").status == "dead"
    assert scope.assessment(parent.claim_id).disposition.value == "unknown"
    assert any(row.claim_id == parent.claim_id and row.critical for row in scope.debts)
    assert scope.assessment(state["claim"].claim_id).disposition.value == "supported"
    assert certificate.closed is True
    assert "critical_epistemic_debt" not in certificate.reasons
