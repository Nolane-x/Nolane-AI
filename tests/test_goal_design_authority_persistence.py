import pytest

from nolane.external_core.goal_design import (
    DecisionReceipt,
    GoalDesignCoherencePlane,
    GoalDesignVersionVector,
)
from nolane.external_core.goal_design_ledger import AuthorityLevel, EventKind, GoalDesignLedger
from nolane.external_core.goal_design_runtime import (
    DecisionAuthorityIndex,
    DecisionLifecycle,
    GoalDesignRuntime,
)


def _receipt(receipt_id="receipt:1"):
    return DecisionReceipt(
        receipt_id=receipt_id,
        goal_id="goal:1",
        selected_option_id="option:1",
        snapshot_digest="snapshot:1",
        version_vector={
            "requirements": "r1",
            "planning": "p1",
            "architecture": "a1",
            "integration": "i1",
            "context": "c1",
        },
        evaluation_digest="evaluation:1",
        proof_obligation_ids=("proof:1",),
        uncertainty_ids=("uncertainty:1",),
        evidence_refs=("evidence:1",),
    )


def test_decision_invalidation_is_minted_by_typed_authority_path():
    ledger = GoalDesignLedger()
    receipt = _receipt()
    decision = ledger.record_decision(receipt)

    invalidation = ledger.record_invalidation(
        receipt_id=receipt.receipt_id,
        snapshot_digest=receipt.snapshot_digest,
        reasons=("requirements authority changed",),
        parent_ids=(decision.event_id,),
    )

    assert invalidation.kind is EventKind.INVALIDATION
    assert invalidation.authority_level is AuthorityLevel.AUTHORITY
    assert invalidation.parent_ids == (decision.event_id,)
    assert invalidation.subject_refs == (receipt.receipt_id,)


def test_generic_invalidation_cannot_self_grant_authority():
    ledger = GoalDesignLedger()
    with pytest.raises(ValueError, match="typed authority"):
        ledger.append(
            EventKind.INVALIDATION,
            {"receipt_id": "receipt:1", "reasons": ["drift"]},
            authority_level=AuthorityLevel.AUTHORITY,
        )


def test_runtime_invalidation_uses_typed_authority_event_not_generic_evidence():
    ledger = GoalDesignLedger()
    receipt = _receipt()
    decision = ledger.record_decision(receipt)
    index = DecisionAuthorityIndex()
    record = index.register(receipt, dependency_refs=("req:core",), authority_event_id=decision.event_id)
    runtime = GoalDesignRuntime(
        requirements=None,
        planning=None,
        architecture=None,
        integration=None,
        context=None,
        ledger=ledger,
        decisions=index,
    )

    runtime._record_invalidation(record, ("requirements authority changed",))
    event = ledger.events[-1]
    assert event.kind is EventKind.INVALIDATION
    assert event.authority_level is AuthorityLevel.AUTHORITY
    assert event.parent_ids == (decision.event_id,)


def test_decision_authority_index_roundtrips_across_restart_without_losing_lifecycle():
    index = DecisionAuthorityIndex()
    receipt = _receipt()
    index.register(
        receipt,
        dependency_refs=("req:core", "cmp:core"),
        authority_event_id="event:decision",
    )
    index.mark_stale(receipt.receipt_id, ("requirements revision changed",))

    state = index.to_state()
    restored = DecisionAuthorityIndex.from_state(state)
    record = restored.get(receipt.receipt_id)

    assert record.lifecycle is DecisionLifecycle.STALE
    assert record.dependency_refs == ("cmp:core", "req:core")
    assert record.invalidation_reasons == ("requirements revision changed",)
    assert record.authority_event_id == "event:decision"
    assert record.receipt == receipt
    assert restored.to_state() == state
    assert restored.digest == index.digest


def test_decision_authority_state_rejects_duplicate_receipt_identity():
    receipt = _receipt()
    index = DecisionAuthorityIndex()
    index.register(receipt, dependency_refs=("req:core",))
    state = index.to_state()
    duplicate = dict(state)
    duplicate["records"] = list(state["records"]) + list(state["records"])

    with pytest.raises(ValueError, match="duplicate"):
        DecisionAuthorityIndex.from_state(duplicate)


def test_goal_design_ledger_roundtrips_and_preserves_causal_authority_digest():
    ledger = GoalDesignLedger()
    vector = GoalDesignVersionVector("r1", "p1", "a1", "i1", "c1")
    snapshot = GoalDesignCoherencePlane().freeze_snapshot(vector)
    snapshot_event = ledger.record_snapshot(snapshot)
    receipt = DecisionReceipt(
        receipt_id="receipt:roundtrip",
        goal_id="goal:roundtrip",
        selected_option_id="option:roundtrip",
        snapshot_digest=snapshot.digest,
        version_vector=vector.tokens(),
        evaluation_digest="evaluation:roundtrip",
        proof_obligation_ids=(),
        uncertainty_ids=(),
        evidence_refs=("evidence:roundtrip",),
    )
    decision = ledger.record_decision(receipt, parent_ids=(snapshot_event.event_id,))
    ledger.record_invalidation(
        receipt_id=receipt.receipt_id,
        snapshot_digest=snapshot.digest,
        reasons=("architecture drift",),
        parent_ids=(decision.event_id,),
    )

    state = ledger.to_state()
    restored = GoalDesignLedger.from_state(state)
    assert restored.to_state() == state
    assert restored.events == ledger.events
    assert restored.digest == ledger.digest
    assert restored.events[-1].authority_level is AuthorityLevel.AUTHORITY


def test_goal_design_ledger_restore_rejects_tampered_event_identity():
    ledger = GoalDesignLedger()
    receipt = _receipt()
    ledger.record_decision(receipt)
    state = ledger.to_state()
    state["events"][0]["payload_digest"] = "tampered"

    with pytest.raises(ValueError, match="identity digest mismatch"):
        GoalDesignLedger.from_state(state)
