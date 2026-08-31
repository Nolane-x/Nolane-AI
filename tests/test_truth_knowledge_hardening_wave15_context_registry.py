from __future__ import annotations

import pytest

from nolane.external_core.evidence_context_truth import (
    EVIDENCE_CONTEXT_PROJECTION_PROTOCOL,
    EVIDENCE_CONTEXT_PROTOCOL,
    EvidenceContextBindingRegistry,
    EvidenceContextBindingRevision,
)
from nolane.external_core.evidence_truth import (
    EvidenceChannel,
    EvidenceLedger,
    EvidencePolarity,
    TruthEvidence,
)
from nolane.external_core.knowledge_context_truth import (
    CLAIM_CONTEXT_PROJECTION_PROTOCOL,
    CLAIM_CONTEXT_PROTOCOL,
    TruthContext,
    ClaimContextBindingRegistry,
    ClaimContextBindingRevision,
)
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger


def _knowledge() -> tuple[KnowledgeLedger, KnowledgeClaim, KnowledgeClaim]:
    ledger = KnowledgeLedger()
    bound = ledger.add(
        KnowledgeClaim.create(
            claim_id="claim-bound",
            subject="policy",
            relation="permits",
            object="yes",
        )
    )
    global_claim = ledger.add(
        KnowledgeClaim.create(
            claim_id="claim-global",
            subject="policy",
            relation="exists",
            object="yes",
        )
    )
    return ledger, bound, global_claim


def _evidence() -> tuple[EvidenceLedger, TruthEvidence, TruthEvidence]:
    ledger = EvidenceLedger()
    bound = ledger.record(
        TruthEvidence.create(
            evidence_id="evidence-bound",
            subject_id="claim-bound",
            source_id="source-bound",
            source_family="family:bound",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:bound",
        )
    )
    global_evidence = ledger.record(
        TruthEvidence.create(
            evidence_id="evidence-global",
            subject_id="claim-global",
            source_id="source-global",
            source_family="family:global",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:global",
        )
    )
    return ledger, bound, global_evidence


def test_a15_truth_context_is_canonical_explicit_and_subset_matchable():
    context = TruthContext.create(
        qualifiers=(("region", "us-east"), ("mode", "production"))
    )
    same = TruthContext.create(
        qualifiers=(("mode", "production"), ("region", "us-east"))
    )
    assert context == same
    assert context.qualifiers == (("mode", "production"), ("region", "us-east"))
    assert context.matches((("mode", "production"),))
    assert not context.matches((("mode", "test"),))
    assert not context.matches((("jurisdiction", "eu"),))

    with pytest.raises(ValueError, match="explicit"):
        TruthContext.create(qualifiers=(("", "x"),))
    with pytest.raises(ValueError, match="unique"):
        TruthContext.create(qualifiers=(("mode", "a"), ("mode", "b")))


def test_a15_claim_context_registry_binds_exact_claim_and_revisions_strictly():
    knowledge, claim, _ = _knowledge()
    registry = ClaimContextBindingRegistry()
    first = registry.register(
        ClaimContextBindingRevision.create(
            claim=claim,
            revision=1,
            qualifiers=(("jurisdiction", "us"),),
        ),
        knowledge=knowledge,
    )
    assert registry.required_qualifiers(claim.claim_id) == (("jurisdiction", "us"),)

    with pytest.raises(ValueError, match="advance exactly once"):
        registry.register(
            ClaimContextBindingRevision.create(
                claim=claim,
                revision=3,
                predecessor_digest=first.digest,
                qualifiers=(("jurisdiction", "ca"),),
            ),
            knowledge=knowledge,
        )
    with pytest.raises(ValueError, match="predecessor"):
        registry.register(
            ClaimContextBindingRevision.create(
                claim=claim,
                revision=2,
                predecessor_digest="wrong",
                qualifiers=(("jurisdiction", "ca"),),
            ),
            knowledge=knowledge,
        )

    second = registry.register(
        ClaimContextBindingRevision.create(
            claim=claim,
            revision=2,
            predecessor_digest=first.digest,
            qualifiers=(("jurisdiction", "ca"),),
        ),
        knowledge=knowledge,
    )
    assert registry.current(claim.claim_id) == second


def test_a15_evidence_context_registry_binds_exact_evidence_and_revisions_strictly():
    evidence, row, _ = _evidence()
    registry = EvidenceContextBindingRegistry()
    first = registry.register(
        EvidenceContextBindingRevision.create(
            evidence=row,
            revision=1,
            qualifiers=(("environment", "lab-a"),),
        ),
        evidence=evidence,
    )
    assert registry.required_qualifiers(row.evidence_id) == (("environment", "lab-a"),)

    second = registry.register(
        EvidenceContextBindingRevision.create(
            evidence=row,
            revision=2,
            predecessor_digest=first.digest,
            qualifiers=(("environment", "lab-b"),),
        ),
        evidence=evidence,
    )
    assert registry.current(row.evidence_id) == second


def test_a15_context_projection_marks_legacy_entities_global_and_is_relevant_only():
    knowledge, claim, global_claim = _knowledge()
    claim_registry = ClaimContextBindingRegistry()
    first = claim_registry.register(
        ClaimContextBindingRevision.create(
            claim=claim,
            revision=1,
            qualifiers=(("jurisdiction", "us"),),
        ),
        knowledge=knowledge,
    )
    before = claim_registry.projection_digest((claim.claim_id, global_claim.claim_id))
    state = claim_registry.projection_state((claim.claim_id, global_claim.claim_id))
    assert state["protocol"] == CLAIM_CONTEXT_PROJECTION_PROTOCOL
    assert any(
        row == {"claim_id": global_claim.claim_id, "status": "global"}
        for row in state["claims"]
    )

    unrelated = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-unrelated",
            subject="other",
            relation="is",
            object="true",
        )
    )
    claim_registry.register(
        ClaimContextBindingRevision.create(
            claim=unrelated,
            revision=1,
            qualifiers=(("mode", "other"),),
        ),
        knowledge=knowledge,
    )
    assert claim_registry.projection_digest((claim.claim_id, global_claim.claim_id)) == before

    claim_registry.register(
        ClaimContextBindingRevision.create(
            claim=claim,
            revision=2,
            predecessor_digest=first.digest,
            qualifiers=(("jurisdiction", "ca"),),
        ),
        knowledge=knowledge,
    )
    assert claim_registry.projection_digest((claim.claim_id, global_claim.claim_id)) != before


def test_a15_context_registry_restore_is_domain_separated_and_digest_bound():
    knowledge, claim, _ = _knowledge()
    claims = ClaimContextBindingRegistry()
    claims.register(
        ClaimContextBindingRevision.create(
            claim=claim,
            revision=1,
            qualifiers=(("jurisdiction", "us"),),
        ),
        knowledge=knowledge,
    )
    claim_state = claims.to_state()
    assert claim_state["protocol"] == CLAIM_CONTEXT_PROTOCOL
    assert ClaimContextBindingRegistry.from_state(
        claim_state, knowledge=knowledge
    ).to_state() == claim_state

    wrong = dict(claim_state)
    wrong["protocol"] = "wrong"
    with pytest.raises(ValueError, match="protocol"):
        ClaimContextBindingRegistry.from_state(wrong, knowledge=knowledge)

    evidence, row, _ = _evidence()
    evidence_registry = EvidenceContextBindingRegistry()
    evidence_registry.register(
        EvidenceContextBindingRevision.create(
            evidence=row,
            revision=1,
            qualifiers=(("environment", "lab-a"),),
        ),
        evidence=evidence,
    )
    evidence_state = evidence_registry.to_state()
    assert evidence_state["protocol"] == EVIDENCE_CONTEXT_PROTOCOL
    assert evidence_registry.projection_state((row.evidence_id,))["protocol"] == EVIDENCE_CONTEXT_PROJECTION_PROTOCOL
    assert EvidenceContextBindingRegistry.from_state(
        evidence_state, evidence=evidence
    ).to_state() == evidence_state
