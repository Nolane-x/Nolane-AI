import pytest

from nolane.external_core.goal_design import DecisionReceipt
from nolane.external_core.goal_design_ledger import AuthorityLevel, EventKind, GoalDesignLedger
from nolane.external_core.goal_design_runtime import DecisionAuthorityIndex, DecisionLifecycle


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
