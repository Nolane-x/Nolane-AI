from __future__ import annotations

from copy import deepcopy

import pytest

from nolane.external_core.assurance_justification_truth import JustificationTruthAssuranceGate
from nolane.external_core.epistemic_justification_truth import (
    JUSTIFICATION_BINDING_MODE,
    JustificationEpistemicJudge,
)
from nolane.external_core.epistemic_truth import EpistemicDisposition
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
from nolane.external_core.verification_provenance_truth import ProvenanceTruthVerificationReceipt
from nolane.memory.knowledge import RelationSemanticsRegistry


AS_OF = "2026-08-31T00:00:00Z"


def _provenance(source_id: str, controller_id: str) -> SourceProvenanceRevision:
    return SourceProvenanceRevision.create(
        source_id=source_id,
        revision=1,
        predecessor_digest="",
        controller_id=controller_id,
        parent_source_ids=(),
    )


def _record_evidence(
    ledger: EvidenceLedger,
    *,
    evidence_id: str,
    claim_id: str,
    source_id: str,
    polarity: EvidencePolarity = EvidencePolarity.SUPPORT,
    channel: EvidenceChannel = EvidenceChannel.OBSERVATION,
) -> None:
    ledger.record(
        TruthEvidence.create(
            evidence_id=evidence_id,
            subject_id=claim_id,
            source_id=source_id,
            source_family=f"legacy-family:{source_id}",
            channel=channel,
            polarity=polarity,
            payload_digest=f"payload:{evidence_id}",
        )
    )


def _base_state(*, verifier_controllers=("verifier-controller-1", "verifier-controller-2", "verifier-controller-3")):
    knowledge = KnowledgeLedger()
    evidence = EvidenceLedger()
    relation_semantics = RelationSemanticsRegistry()
    knowledge_temporal = TemporalKnowledgeView()
    evidence_temporal = TemporalEvidenceView()
    provenance = SourceProvenanceRegistry()
    justifications = KnowledgeJustificationRegistry()
    context = TemporalContext.create(as_of=AS_OF)

    _record_evidence(
        evidence,
        evidence_id="legacy-support",
        claim_id="claim-critical",
        source_id="legacy-source",
    )
    _record_evidence(
        evidence,
        evidence_id="alternate-support",
        claim_id="claim-critical",
        source_id="alternate-source",
    )
    _record_evidence(
        evidence,
        evidence_id="alternate-refute",
        claim_id="claim-critical",
        source_id="refute-source",
        polarity=EvidencePolarity.REFUTE,
    )
    for source_id, controller_id in (
        ("legacy-source", "legacy-controller"),
        ("alternate-source", "alternate-controller"),
        ("refute-source", "refute-controller"),
    ):
        provenance.register(_provenance(source_id, controller_id))

    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-critical",
            subject="system",
            relation="is_safe",
            object="yes",
            risk=KnowledgeRisk.CRITICAL,
            evidence_ids=("legacy-support",),
        )
    )

    channels = (
        EvidenceChannel.TEST,
        EvidenceChannel.REPRODUCTION,
        EvidenceChannel.ADVERSARIAL,
    )
    for index, (controller_id, channel) in enumerate(zip(verifier_controllers, channels), start=1):
        verifier_id = f"verifier-{index}"
        verification_evidence_id = f"verification-evidence-{index}"
        provenance.register(_provenance(verifier_id, controller_id))
        _record_evidence(
            evidence,
            evidence_id=verification_evidence_id,
            claim_id=claim.claim_id,
            source_id=verifier_id,
            channel=channel,
        )

    return {
        "knowledge": knowledge,
        "evidence": evidence,
        "relation_semantics": relation_semantics,
        "knowledge_temporal": knowledge_temporal,
        "evidence_temporal": evidence_temporal,
        "provenance": provenance,
        "justifications": justifications,
        "context": context,
        "claim": claim,
        "channels": channels,
    }


def _add_alt(state, *, justification_id="j-alt", evidence_ids=("alternate-support",), parent_claim_ids=()):
    row = KnowledgeJustificationRevision.create(
        justification_id=justification_id,
        claim=state["claim"],
        evidence_ids=evidence_ids,
        parent_claim_ids=parent_claim_ids,
    )
    return state["justifications"].register(row, knowledge=state["knowledge"])


def _scope(state):
    return JustificationEpistemicJudge().relation_aware_temporal_scope(
        state["claim"].claim_id,
        temporal_context=state["context"],
        knowledge=state["knowledge"],
        evidence=state["evidence"],
        relation_semantics=state["relation_semantics"],
        knowledge_temporal=state["knowledge_temporal"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
        justifications=state["justifications"],
    )


def _verification(state, scope):
    ledger = JustificationTruthVerificationLedger()
    for index, channel in enumerate(state["channels"], start=1):
        verifier_id = f"verifier-{index}"
        ledger.record(
            JustificationTruthVerificationReceipt.create(
                receipt_id=f"receipt-{index}",
                claim_id=state["claim"].claim_id,
                verifier_id=verifier_id,
                channel=channel,
                passed=True,
                scope_digest=scope.digest,
                temporal_context_digest=state["context"].digest,
                as_of=state["context"].as_of,
                evidence_ids=(f"verification-evidence-{index}",),
                source_provenance_digest=state["provenance"].projection_digest((verifier_id,)),
            )
        )
    return ledger


def _close(state):
    scope = _scope(state)
    verification = _verification(state, scope)
    certificate = JustificationTruthAssuranceGate().close(
        claim_id=state["claim"].claim_id,
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
    return scope, verification, certificate


def test_a12_alternative_justification_survives_dead_legacy_path():
    state = _base_state()
    _add_alt(state)
    state["evidence"].revoke("legacy-support", reason="legacy path withdrawn")

    scope = _scope(state)

    assert scope.binding_mode == JUSTIFICATION_BINDING_MODE
    assert scope.assessment("claim-critical").disposition is EpistemicDisposition.SUPPORTED
    assert scope.justification_status(scope.legacy_justification_id("claim-critical")).status == "dead"
    assert scope.justification_status("j-alt").status == "supported"


def test_a12_all_justifications_dead_makes_claim_unknown_and_blocks_closure():
    state = _base_state()
    _add_alt(state)
    state["evidence"].revoke("legacy-support", reason="legacy path withdrawn")
    state["evidence"].revoke("alternate-support", reason="alternate path withdrawn")

    scope, _, certificate = _close(state)

    assert scope.assessment("claim-critical").disposition is EpistemicDisposition.UNKNOWN
    assert certificate.closed is False
    assert "epistemic_claim_not_supported" in certificate.reasons


def test_a12_and_inside_one_path_is_strict_but_or_between_paths_survives():
    state = _base_state()
    _record_evidence(
        state["evidence"],
        evidence_id="alternate-support-2",
        claim_id="claim-critical",
        source_id="alternate-source-2",
    )
    state["provenance"].register(_provenance("alternate-source-2", "alternate-controller-2"))
    _add_alt(state, justification_id="j-conjunction", evidence_ids=("alternate-support", "alternate-support-2"))
    _add_alt(state, justification_id="j-survivor", evidence_ids=("alternate-support-2",))
    state["evidence"].revoke("legacy-support", reason="legacy dead")
    state["evidence"].revoke("alternate-support", reason="one conjunct dead")

    scope = _scope(state)

    assert scope.justification_status("j-conjunction").status == "dead"
    assert scope.justification_status("j-survivor").status == "supported"
    assert scope.assessment("claim-critical").disposition is EpistemicDisposition.SUPPORTED


def test_a12_refuting_alternative_cannot_be_hidden_by_supporting_or_path():
    state = _base_state()
    _add_alt(state, justification_id="j-support", evidence_ids=("alternate-support",))
    _add_alt(state, justification_id="j-refute", evidence_ids=("alternate-refute",))

    scope = _scope(state)

    assert scope.justification_status("j-support").status == "supported"
    assert scope.justification_status("j-refute").status == "refuted"
    assert scope.assessment("claim-critical").disposition is EpistemicDisposition.CONTRADICTED


def test_a12_duplicate_basis_cannot_mint_fake_multiple_justifications():
    state = _base_state()
    _add_alt(state, justification_id="j-alt")

    duplicate = KnowledgeJustificationRevision.create(
        justification_id="j-alias",
        claim=state["claim"],
        evidence_ids=("alternate-support",),
        parent_claim_ids=(),
    )
    with pytest.raises(ValueError, match="duplicate.*justification basis"):
        state["justifications"].register(duplicate, knowledge=state["knowledge"])

    legacy_duplicate = KnowledgeJustificationRevision.create(
        justification_id="j-legacy-alias",
        claim=state["claim"],
        evidence_ids=("legacy-support",),
        parent_claim_ids=(),
    )
    with pytest.raises(ValueError, match="legacy.*basis"):
        state["justifications"].register(legacy_duplicate, knowledge=state["knowledge"])


def test_a12_revision_rebind_gap_predecessor_and_dependency_cycle_fail_closed():
    state = _base_state()
    first = _add_alt(state)

    with pytest.raises(ValueError, match="predecessor"):
        state["justifications"].register(
            KnowledgeJustificationRevision.create(
                justification_id="j-alt",
                claim=state["claim"],
                revision=2,
                predecessor_digest="forged",
                evidence_ids=("alternate-support",),
            ),
            knowledge=state["knowledge"],
        )
    with pytest.raises(ValueError, match="advance exactly once"):
        state["justifications"].register(
            KnowledgeJustificationRevision.create(
                justification_id="j-alt",
                claim=state["claim"],
                revision=3,
                predecessor_digest=first.digest,
                evidence_ids=("alternate-support",),
            ),
            knowledge=state["knowledge"],
        )

    parent_a = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="claim-a",
            subject="a",
            relation="depends",
            object="ok",
        )
    )
    parent_b = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="claim-b",
            subject="b",
            relation="depends",
            object="ok",
        )
    )
    state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-a",
            claim=parent_a,
            parent_claim_ids=("claim-b",),
        ),
        knowledge=state["knowledge"],
    )
    with pytest.raises(ValueError, match="cycle"):
        state["justifications"].register(
            KnowledgeJustificationRevision.create(
                justification_id="j-b",
                claim=parent_b,
                parent_claim_ids=("claim-a",),
            ),
            knowledge=state["knowledge"],
        )


def test_a12_projection_is_relevant_only_and_restore_is_domain_separated():
    state = _base_state()
    first = _add_alt(state)
    before = state["justifications"].projection_digest(("claim-critical",), knowledge=state["knowledge"])

    unrelated = state["knowledge"].add(
        KnowledgeClaim.create(
            claim_id="claim-unrelated",
            subject="other",
            relation="state",
            object="ok",
            evidence_ids=("unrelated-legacy",),
        )
    )
    state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-unrelated",
            claim=unrelated,
            parent_claim_ids=(),
        ),
        knowledge=state["knowledge"],
    )
    assert state["justifications"].projection_digest(("claim-critical",), knowledge=state["knowledge"]) == before

    state["justifications"].register(
        KnowledgeJustificationRevision.create(
            justification_id="j-alt",
            claim=state["claim"],
            revision=2,
            predecessor_digest=first.digest,
            evidence_ids=("alternate-support",),
            enabled=False,
        ),
        knowledge=state["knowledge"],
    )
    assert state["justifications"].projection_digest(("claim-critical",), knowledge=state["knowledge"]) != before

    serialized = state["justifications"].to_state()
    forged = deepcopy(serialized)
    forged["protocol"] = "another-domain"
    with pytest.raises(ValueError, match="unsupported.*justification"):
        KnowledgeJustificationRegistry.from_state(forged, knowledge=state["knowledge"])

    duplicated = deepcopy(serialized)
    duplicated["revisions"].append(deepcopy(duplicated["revisions"][0]))
    with pytest.raises(ValueError, match="duplicate serialized justification revision"):
        KnowledgeJustificationRegistry.from_state(duplicated, knowledge=state["knowledge"])


def test_a12_live_supporting_source_controller_is_not_independent_verification():
    state = _base_state(
        verifier_controllers=("alternate-controller", "verifier-controller-2", "verifier-controller-3")
    )
    _add_alt(state)
    state["evidence"].revoke("legacy-support", reason="force alternate support path")

    scope, verification, certificate = _close(state)
    coverage = verification.coverage(
        state["claim"].claim_id,
        scope=scope,
        temporal_context=state["context"],
        evidence=state["evidence"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
    )

    assert coverage.independent_source_count == 2
    assert "receipt-1" in coverage.non_independent_receipt_ids
    assert certificate.closed is False
    assert "insufficient_independent_verification" in certificate.reasons


def test_a12_dead_path_source_controller_does_not_poison_live_verifier_independence():
    state = _base_state(
        verifier_controllers=("legacy-controller", "verifier-controller-2", "verifier-controller-3")
    )
    _add_alt(state)
    state["evidence"].revoke("legacy-support", reason="legacy path is dead")

    scope, verification, certificate = _close(state)
    coverage = verification.coverage(
        state["claim"].claim_id,
        scope=scope,
        temporal_context=state["context"],
        evidence=state["evidence"],
        evidence_temporal=state["evidence_temporal"],
        source_provenance=state["provenance"],
    )

    assert "legacy-source" in scope.source_ids
    assert "legacy-source" not in scope.supporting_source_ids
    assert coverage.independent_source_count == 3
    assert certificate.closed is True


def test_a12_v5_receipt_cannot_masquerade_as_v6():
    state = _base_state()
    scope = _scope(state)
    v5 = ProvenanceTruthVerificationReceipt.create(
        receipt_id="legacy-v5-receipt",
        claim_id=state["claim"].claim_id,
        verifier_id="verifier-1",
        channel=EvidenceChannel.TEST,
        passed=True,
        scope_digest=scope.digest,
        temporal_context_digest=state["context"].digest,
        as_of=state["context"].as_of,
        evidence_ids=("verification-evidence-1",),
        source_provenance_digest=state["provenance"].projection_digest(("verifier-1",)),
    )

    with pytest.raises(ValueError, match="unsupported justification verification protocol"):
        JustificationTruthVerificationReceipt.from_state(v5.to_state())
