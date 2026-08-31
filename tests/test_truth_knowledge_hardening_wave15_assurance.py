from __future__ import annotations

import pytest

from nolane.external_core.assurance_context_truth import (
    ContextTruthAssuranceGate,
    ContextTruthClosureCertificate,
)
from nolane.external_core.assurance_dependence_truth import DependenceTruthClosureCertificate
from nolane.external_core.epistemic_context_truth import ContextEpistemicJudge
from nolane.external_core.evidence_context_truth import (
    EvidenceContextBindingRegistry,
    EvidenceContextBindingRevision,
)
from nolane.external_core.evidence_dependence_truth import (
    SourceDependenceRegistry,
    SourceDependenceRevision,
)
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
from nolane.external_core.knowledge_context_truth import (
    ClaimContextBindingRegistry,
    ClaimContextBindingRevision,
    TruthContext,
)
from nolane.external_core.knowledge_justification_truth import KnowledgeJustificationRegistry
from nolane.external_core.knowledge_temporal_truth import TemporalKnowledgeView
from nolane.external_core.knowledge_truth import (
    KnowledgeClaim,
    KnowledgeLedger,
    KnowledgeRisk,
)
from nolane.external_core.knowledge_undercutter_truth import JustificationUndercutterRegistry
from nolane.external_core.temporal_truth import TemporalContext
from nolane.external_core.verification_context_truth import (
    ContextTruthVerificationLedger,
    ContextTruthVerificationReceipt,
)
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"
US = TruthContext.create(qualifiers=(("jurisdiction", "us"),))
EU = TruthContext.create(qualifiers=(("jurisdiction", "eu"),))


def _prov(source_id: str, controller_id: str) -> SourceProvenanceRevision:
    return SourceProvenanceRevision.create(
        source_id=source_id,
        revision=1,
        controller_id=controller_id,
        parent_source_ids=(),
    )


def _dep(source_id: str, *basis_ids: str) -> SourceDependenceRevision:
    return SourceDependenceRevision.create(
        source_id=source_id,
        revision=1,
        basis_ids=tuple(basis_ids),
    )


def _record(state, evidence_id: str, subject_id: str, source_id: str, channel: EvidenceChannel):
    return state["evidence"].record(
        TruthEvidence.create(
            evidence_id=evidence_id,
            subject_id=subject_id,
            source_id=source_id,
            source_family=f"family:{source_id}",
            channel=channel,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest=f"payload:{evidence_id}",
        )
    )


def _state():
    state = {
        "knowledge": KnowledgeLedger(),
        "evidence": EvidenceLedger(),
        "semantics": RelationSemanticsRegistry(),
        "knowledge_temporal": TemporalKnowledgeView(),
        "evidence_temporal": TemporalEvidenceView(),
        "provenance": SourceProvenanceRegistry(),
        "dependence": SourceDependenceRegistry(),
        "justifications": KnowledgeJustificationRegistry(),
        "undercutters": JustificationUndercutterRegistry(),
        "claim_context": ClaimContextBindingRegistry(),
        "evidence_context": EvidenceContextBindingRegistry(),
        "temporal_context": TemporalContext.create(as_of=AS_OF),
        "truth_context": US,
    }
    support = _record(
        state,
        "claim-support",
        "claim-high-v9",
        "claim-source",
        EvidenceChannel.OBSERVATION,
    )
    state["provenance"].register(_prov("claim-source", "claim-controller"))
    state["dependence"].register(_dep("claim-source", "basis:decision"))
    claim = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="claim-high-v9",
            subject="system",
            relation="is_safe",
            object="yes",
            risk=KnowledgeRisk.HIGH,
            evidence_ids=(support.evidence_id,),
        )
    )
    state["claim"] = claim
    state["claim_context"].register(
        ClaimContextBindingRevision.create(
            claim=claim,
            qualifiers=(("jurisdiction", "us"),),
        ),
        knowledge=state["knowledge"],
    )
    state["evidence_context"].register(
        EvidenceContextBindingRevision.create(
            evidence=support,
            qualifiers=(("jurisdiction", "us"),),
        ),
        evidence=state["evidence"],
    )
    return state


def _add_verifier(state, verifier_id, controller_id, channel, basis_ids, *, jurisdiction="us"):
    state["provenance"].register(_prov(verifier_id, controller_id))
    state["dependence"].register(_dep(verifier_id, *basis_ids))
    item = _record(
        state,
        f"evidence:{verifier_id}",
        state["claim"].claim_id,
        verifier_id,
        channel,
    )
    state["evidence_context"].register(
        EvidenceContextBindingRevision.create(
            evidence=item,
            qualifiers=(("jurisdiction", jurisdiction),),
        ),
        evidence=state["evidence"],
    )
    return item


def _scope(state):
    return ContextEpistemicJudge().relation_aware_temporal_scope(
        state["claim"].claim_id,
        truth_context=state["truth_context"],
        temporal_context=state["temporal_context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        source_dependence=state["dependence"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
        claim_context=state["claim_context"],
        evidence_context=state["evidence_context"],
    )


def _verification(state, scope):
    ledger = ContextTruthVerificationLedger()
    for verifier_id, channel in (
        ("v-a", EvidenceChannel.TEST),
        ("v-b", EvidenceChannel.REPRODUCTION),
    ):
        ledger.record(
            ContextTruthVerificationReceipt.create(
                receipt_id=f"receipt:{verifier_id}",
                claim_id=state["claim"].claim_id,
                verifier_id=verifier_id,
                channel=channel,
                passed=True,
                scope_digest=scope.digest,
                truth_context_digest=state["truth_context"].digest,
                temporal_context_digest=state["temporal_context"].digest,
                as_of=state["temporal_context"].as_of,
                evidence_ids=(f"evidence:{verifier_id}",),
                source_provenance_digest=state["provenance"].projection_digest((verifier_id,)),
                source_dependence_digest=state["dependence"].projection_digest((verifier_id,)),
                evidence_context_digest=state["evidence_context"].projection_digest(
                    (f"evidence:{verifier_id}",)
                ),
            )
        )
    return ledger


def _close(state):
    scope = _scope(state)
    verification = _verification(state, scope)
    gate = ContextTruthAssuranceGate()
    certificate = gate.close(
        claim_id=state["claim"].claim_id,
        truth_context=state["truth_context"],
        temporal_context=state["temporal_context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        source_dependence=state["dependence"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
        claim_context=state["claim_context"],
        evidence_context=state["evidence_context"],
        verification=verification,
    )
    return scope, verification, gate, certificate


def _validate(state, gate, verification, certificate):
    return gate.validate_certificate(
        certificate,
        truth_context=state["truth_context"],
        temporal_context=state["temporal_context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        source_dependence=state["dependence"],
        justifications=state["justifications"],
        undercutters=state["undercutters"],
        claim_context=state["claim_context"],
        evidence_context=state["evidence_context"],
        verification=verification,
    )


def test_a15_high_assurance_preserves_common_basis_collapse():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:shared",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:shared",))
    _, _, _, certificate = _close(state)
    assert certificate.closed is False
    assert "insufficient_independent_verification" in certificate.reasons


def test_a15_high_assurance_closes_with_two_context_valid_disjoint_verifiers():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:b",))
    _, _, _, certificate = _close(state)
    assert certificate.closed is True
    assert certificate.reasons == ()


def test_a15_target_context_mismatch_blocks_closure_even_with_verifiers():
    state = _state()
    state["truth_context"] = EU
    _add_verifier(
        state,
        "v-a",
        "controller-a",
        EvidenceChannel.TEST,
        ("basis:a",),
        jurisdiction="eu",
    )
    _add_verifier(
        state,
        "v-b",
        "controller-b",
        EvidenceChannel.REPRODUCTION,
        ("basis:b",),
        jurisdiction="eu",
    )
    _, _, _, certificate = _close(state)
    assert certificate.closed is False
    assert "target_context_mismatch" in certificate.reasons
    assert "epistemic_claim_not_supported" in certificate.reasons


def test_a15_relevant_context_revision_stales_certificate_but_unrelated_does_not():
    state = _state()
    _add_verifier(state, "v-a", "controller-a", EvidenceChannel.TEST, ("basis:a",))
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:b",))
    _, verification, gate, certificate = _close(state)
    assert certificate.closed is True
    assert _validate(state, gate, verification, certificate)

    unrelated = _record(
        state,
        "unrelated-evidence",
        "other-claim",
        "other-source",
        EvidenceChannel.OBSERVATION,
    )
    state["evidence_context"].register(
        EvidenceContextBindingRevision.create(
            evidence=unrelated,
            qualifiers=(("jurisdiction", "eu"),),
        ),
        evidence=state["evidence"],
    )
    assert _validate(state, gate, verification, certificate)

    previous = state["claim_context"].current(state["claim"].claim_id)
    assert previous is not None
    state["claim_context"].register(
        ClaimContextBindingRevision.create(
            claim=state["claim"],
            revision=2,
            predecessor_digest=previous.digest,
            qualifiers=(("jurisdiction", "us"), ("mode", "strict")),
        ),
        knowledge=state["knowledge"],
    )
    assert _validate(state, gate, verification, certificate) is False


def test_a15_context_mismatched_verification_evidence_blocks_closure():
    state = _state()
    _add_verifier(
        state,
        "v-a",
        "controller-a",
        EvidenceChannel.TEST,
        ("basis:a",),
        jurisdiction="eu",
    )
    _add_verifier(state, "v-b", "controller-b", EvidenceChannel.REPRODUCTION, ("basis:b",))
    _, _, _, certificate = _close(state)
    assert certificate.closed is False
    assert "verification_context_invalid" in certificate.reasons
    assert "insufficient_independent_verification" in certificate.reasons


def test_a15_v8_certificate_cannot_masquerade_as_v9():
    state = _state()
    old = DependenceTruthClosureCertificate.create(
        claim_id=state["claim"].claim_id,
        risk=state["claim"].risk,
        scope_digest="scope:v8",
        verification_scope_digest="verification:v8",
        temporal_context_digest=state["temporal_context"].digest,
        as_of=state["temporal_context"].as_of,
        verification_receipt_ids=(),
        epistemic_debt_ids=(),
        closed=False,
        reasons=("v8",),
    )
    with pytest.raises(ValueError, match="unsupported context assurance protocol"):
        ContextTruthClosureCertificate.from_state(old.to_state())
