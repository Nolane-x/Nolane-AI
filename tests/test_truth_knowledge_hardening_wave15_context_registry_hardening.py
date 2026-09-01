from __future__ import annotations

import pytest

from nolane.external_core.evidence_context_truth import (
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
    CLAIM_CONTEXT_PROTOCOL,
    ClaimContextBindingRegistry,
    ClaimContextBindingRevision,
)
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger


def test_a15_claim_context_rejects_cross_ledger_same_id_content_rebind():
    original_ledger = KnowledgeLedger()
    original = original_ledger.add(
        KnowledgeClaim.create(
            claim_id="same-id",
            subject="system",
            relation="mode",
            object="production",
        )
    )
    row = ClaimContextBindingRevision.create(
        claim=original,
        revision=1,
        qualifiers=(("region", "us"),),
    )

    rebound_ledger = KnowledgeLedger()
    rebound_ledger.add(
        KnowledgeClaim.create(
            claim_id="same-id",
            subject="system",
            relation="mode",
            object="test",
        )
    )
    with pytest.raises(ValueError, match="content digest"):
        ClaimContextBindingRegistry().register(row, knowledge=rebound_ledger)


def test_a15_evidence_context_rejects_cross_ledger_same_id_content_rebind():
    original_ledger = EvidenceLedger()
    original = original_ledger.record(
        TruthEvidence.create(
            evidence_id="same-evidence",
            subject_id="claim-a",
            source_id="source-a",
            source_family="family:a",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:a",
        )
    )
    row = EvidenceContextBindingRevision.create(
        evidence=original,
        revision=1,
        qualifiers=(("region", "us"),),
    )

    rebound_ledger = EvidenceLedger()
    rebound_ledger.record(
        TruthEvidence.create(
            evidence_id="same-evidence",
            subject_id="claim-a",
            source_id="source-a",
            source_family="family:a",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:changed",
        )
    )
    with pytest.raises(ValueError, match="content digest"):
        EvidenceContextBindingRegistry().register(row, evidence=rebound_ledger)


def test_a15_claim_context_restore_rejects_duplicate_serialized_revision():
    knowledge = KnowledgeLedger()
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="claim-a",
            subject="system",
            relation="mode",
            object="production",
        )
    )
    row = ClaimContextBindingRevision.create(
        claim=claim,
        revision=1,
        qualifiers=(("region", "us"),),
    )
    state = {
        "protocol": CLAIM_CONTEXT_PROTOCOL,
        "revisions": [row.to_state(), row.to_state()],
    }
    with pytest.raises(ValueError, match="duplicate"):
        ClaimContextBindingRegistry.from_state(state, knowledge=knowledge)


def test_a15_evidence_context_restore_rejects_duplicate_serialized_revision():
    evidence = EvidenceLedger()
    item = evidence.record(
        TruthEvidence.create(
            evidence_id="evidence-a",
            subject_id="claim-a",
            source_id="source-a",
            source_family="family:a",
            channel=EvidenceChannel.OBSERVATION,
            polarity=EvidencePolarity.SUPPORT,
            payload_digest="payload:a",
        )
    )
    row = EvidenceContextBindingRevision.create(
        evidence=item,
        revision=1,
        qualifiers=(("region", "us"),),
    )
    state = {
        "protocol": EVIDENCE_CONTEXT_PROTOCOL,
        "revisions": [row.to_state(), row.to_state()],
    }
    with pytest.raises(ValueError, match="duplicate"):
        EvidenceContextBindingRegistry.from_state(state, evidence=evidence)
