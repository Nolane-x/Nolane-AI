import pytest

from nolane.external_core.goal_design import DecisionReceipt, GoalDesignCoherencePlane, GoalDesignVersionVector
from nolane.external_core.goal_design_ledger import AuthorityLevel, EventKind, GoalDesignLedger


def _snapshot():
    return GoalDesignCoherencePlane().freeze_snapshot(GoalDesignVersionVector("r1", "p1", "a1", "i1", "c1"))


def _receipt(*, manifest_digest: str) -> DecisionReceipt:
    return DecisionReceipt(
        receipt_id="receipt:audit",
        goal_id="goal:audit",
        selected_option_id="option:audit",
        snapshot_digest="snapshot:audit",
        version_vector={
            "requirements": "r1",
            "planning": "p1",
            "architecture": "a1",
            "integration": "i1",
            "context": "c1",
        },
        evaluation_digest="evaluation:audit",
        proof_obligation_ids=(),
        uncertainty_ids=(),
        evidence_refs=("evidence:audit",),
        input_manifest_digest=manifest_digest,
    )


def test_generic_cognition_cannot_self_grant_authority():
    ledger = GoalDesignLedger()
    with pytest.raises(ValueError, match="typed authority"):
        ledger.append(EventKind.PROPOSAL, {"idea": "rewrite everything"}, authority_level=AuthorityLevel.AUTHORITY)


def test_snapshot_is_typed_authority_and_content_addressed():
    ledger = GoalDesignLedger()
    snapshot = _snapshot()
    first = ledger.record_snapshot(snapshot)
    second = ledger.record_snapshot(snapshot)
    assert first.authority_level is AuthorityLevel.AUTHORITY
    assert first.event_id == second.event_id
    assert len(ledger.events) == 1


def test_decision_authority_event_explicitly_binds_input_manifest_digest():
    ledger = GoalDesignLedger()
    first = ledger.record_decision(_receipt(manifest_digest="manifest:a"))
    second = ledger.record_decision(_receipt(manifest_digest="manifest:b"))

    assert first.payload_digest != second.payload_digest
    assert first.event_id != second.event_id
    assert len(ledger.events) == 2


def test_unknown_causal_parent_is_rejected():
    with pytest.raises(ValueError, match="causal parents"):
        GoalDesignLedger().append(EventKind.OBSERVATION, {"x": 1}, parent_ids=("missing",))
