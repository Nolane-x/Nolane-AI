from __future__ import annotations

import pytest

from nolane.external_core.knowledge_justification_truth import (
    KnowledgeJustificationRegistry,
    KnowledgeJustificationRevision,
)
from nolane.external_core.knowledge_truth import KnowledgeClaim, KnowledgeLedger
from nolane.external_core.knowledge_undercutter_truth import (
    JustificationUndercutterRegistry,
    JustificationUndercutterRevision,
)


def _state():
    knowledge = KnowledgeLedger()
    claim = knowledge.add(
        KnowledgeClaim.create(
            claim_id="restore-target",
            subject="system",
            relation="valid",
            object="yes",
        )
    )
    justifications = KnowledgeJustificationRegistry()
    first = justifications.register(
        KnowledgeJustificationRevision.create(
            justification_id="j-revisable",
            claim=claim,
            evidence_ids=("evidence-v1",),
        ),
        knowledge=knowledge,
    )
    undercutters = JustificationUndercutterRegistry()
    undercutters.register(
        JustificationUndercutterRevision.create(
            undercutter_id="u-historical",
            claim=claim,
            target_basis=first.basis(),
            evidence_ids=("attack-evidence",),
        ),
        knowledge=knowledge,
        justifications=justifications,
    )
    second = justifications.register(
        KnowledgeJustificationRevision.create(
            justification_id="j-revisable",
            claim=claim,
            revision=2,
            predecessor_digest=first.digest,
            evidence_ids=("evidence-v2",),
        ),
        knowledge=knowledge,
    )
    return knowledge, claim, justifications, undercutters, first, second


def test_a13_restore_preserves_auditable_attack_after_target_basis_revision():
    knowledge, _, justifications, undercutters, _, _ = _state()
    serialized = undercutters.to_state()

    restored = JustificationUndercutterRegistry.from_state(
        serialized,
        knowledge=knowledge,
        justifications=justifications,
    )

    assert restored.to_state() == serialized
    assert restored.digest == undercutters.digest


def test_a13_live_registration_still_rejects_new_attack_against_stale_basis():
    knowledge, claim, justifications, _, first, _ = _state()
    fresh_registry = JustificationUndercutterRegistry()

    with pytest.raises(ValueError, match="not currently effective"):
        fresh_registry.register(
            JustificationUndercutterRevision.create(
                undercutter_id="u-too-late",
                claim=claim,
                target_basis=first.basis(),
                evidence_ids=("late-attack",),
            ),
            knowledge=knowledge,
            justifications=justifications,
        )
