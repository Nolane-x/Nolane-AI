from dataclasses import replace

import pytest

from nolane.external_core.goal_design import (
    DecisionReceipt,
    GoalDesignCoherencePlane,
    GoalDesignVersionVector,
)
from nolane.external_core.goal_design_authenticity import expected_decision_receipt_id
from nolane.external_core.goal_design_ledger import AuthorityLevel, EventKind, GoalDesignLedger
from nolane.external_core.goal_design_runtime import (
    DecisionAuthorityIndex,
    DecisionLifecycle,
    GoalDesignRuntime,
)


def _content_address(receipt: DecisionReceipt) -> DecisionReceipt:
    return replace(receipt, receipt_id=expected_decision_receipt_id(receipt))


def _receipt(label="1"):
    return _content_address(
        DecisionReceipt(
            receipt_id="pending",
            goal_id=f"goal:{label}",
            selected_option_id=f"option:{label}",
            snapshot_digest="snapshot:1",
            version_vector={
                "requirements": "r1",
                "planning": "p1",
                "architecture": "a1",
                "integration": "i1",
                "context": "c1",
            },
            evaluation_digest=f"evaluation:{label}",
            proof_obligation_ids=(f"proof:{label}",),
            uncertainty_ids=(f"uncertainty:{label}",),
            evidence_refs=(f"evidence:{label}",),
        )
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


def test_decision_authority_index_roundtrips_proof_carrying_manifest_digests():
    receipt = _content_address(
        DecisionReceipt(
            receipt_id="pending",
            goal_id="goal:manifest",
            selected_option_id="option:manifest",
            snapshot_digest="snapshot:manifest",
            version_vector={
                "requirements": "r2",
                "planning": "p2",
                "architecture": "a2",
                "integration": "i2",
                "context": "c2",
            },
            evaluation_digest="evaluation:manifest",
            proof_obligation_ids=("proof:manifest",),
            uncertainty_ids=("uncertainty:manifest",),
            evidence_refs=("evidence:manifest",),
            goal_digest="digest:goal",
            scenario_set_digest="digest:scenarios",
            option_set_digest="digest:options",
            proof_state_digest="digest:proofs",
            uncertainty_state_digest="digest:uncertainties",
            traceability_digest="digest:traceability",
            input_manifest_digest="digest:manifest",
        )
    )
    index = DecisionAuthorityIndex()
    index.register(receipt, dependency_refs=("req:manifest", "cmp:manifest"))

    state = index.to_state()
    restored = DecisionAuthorityIndex.from_state(state)

    assert restored.get(receipt.receipt_id).receipt == receipt
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
    receipt = _content_address(
        DecisionReceipt(
            receipt_id="pending",
            goal_id="goal:roundtrip",
            selected_option_id="option:roundtrip",
            snapshot_digest=snapshot.digest,
            version_vector=vector.tokens(),
            evaluation_digest="evaluation:roundtrip",
            proof_obligation_ids=(),
            uncertainty_ids=(),
            evidence_refs=("evidence:roundtrip",),
        )
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


def test_revoked_decision_is_terminal_and_cannot_be_downgraded_or_superseded():
    index = DecisionAuthorityIndex()
    revoked = _receipt("revoked")
    replacement = _receipt("replacement")
    index.register(revoked)
    index.register(replacement)
    index.revoke(revoked.receipt_id, "explicit withdrawal")

    with pytest.raises(ValueError, match="terminal"):
        index.mark_stale(revoked.receipt_id, ("later authority drift",))
    with pytest.raises(ValueError, match="terminal"):
        index.supersede(revoked.receipt_id, by_receipt_id=replacement.receipt_id)

    assert index.get(revoked.receipt_id).lifecycle is DecisionLifecycle.REVOKED


def test_superseded_decision_is_terminal_and_cannot_be_rewritten():
    index = DecisionAuthorityIndex()
    original = _receipt("original")
    replacement = _receipt("replacement")
    index.register(original)
    index.register(replacement)
    index.supersede(original.receipt_id, by_receipt_id=replacement.receipt_id)

    with pytest.raises(ValueError, match="terminal"):
        index.mark_stale(original.receipt_id, ("later drift",))
    with pytest.raises(ValueError, match="terminal"):
        index.revoke(original.receipt_id, "late withdrawal")

    record = index.get(original.receipt_id)
    assert record.lifecycle is DecisionLifecycle.SUPERSEDED
    assert record.superseded_by == replacement.receipt_id


def test_stale_decision_may_move_forward_to_terminal_state():
    index = DecisionAuthorityIndex()
    stale_for_revoke = _receipt("stale-revoke")
    stale_for_supersede = _receipt("stale-supersede")
    replacement = _receipt("replacement")
    for receipt in (stale_for_revoke, stale_for_supersede, replacement):
        index.register(receipt)

    index.mark_stale(stale_for_revoke.receipt_id, ("requirements drift",))
    index.mark_stale(stale_for_supersede.receipt_id, ("architecture drift",))

    assert index.revoke(stale_for_revoke.receipt_id, "withdraw stale decision").lifecycle is DecisionLifecycle.REVOKED
    superseded = index.supersede(stale_for_supersede.receipt_id, by_receipt_id=replacement.receipt_id)
    assert superseded.lifecycle is DecisionLifecycle.SUPERSEDED
    assert superseded.superseded_by == replacement.receipt_id


def test_supersession_cycle_is_rejected_at_runtime():
    index = DecisionAuthorityIndex()
    first = _receipt("first")
    second = _receipt("second")
    index.register(first)
    index.register(second)
    index.supersede(first.receipt_id, by_receipt_id=second.receipt_id)

    with pytest.raises(ValueError, match="cycle|terminal"):
        index.supersede(second.receipt_id, by_receipt_id=first.receipt_id)

    assert index.get(second.receipt_id).lifecycle is DecisionLifecycle.ACTIVE


def test_restore_rejects_tampered_supersession_cycle():
    index = DecisionAuthorityIndex()
    first = _receipt("first")
    second = _receipt("second")
    index.register(first)
    index.register(second)
    state = index.to_state()
    rows = {row["receipt"]["receipt_id"]: row for row in state["records"]}
    rows[first.receipt_id]["lifecycle"] = DecisionLifecycle.SUPERSEDED.value
    rows[first.receipt_id]["superseded_by"] = second.receipt_id
    rows[second.receipt_id]["lifecycle"] = DecisionLifecycle.SUPERSEDED.value
    rows[second.receipt_id]["superseded_by"] = first.receipt_id

    with pytest.raises(ValueError, match="cycle"):
        DecisionAuthorityIndex.from_state(state)


def test_mark_stale_requires_at_least_one_authority_reason():
    index = DecisionAuthorityIndex()
    receipt = _receipt("no-reason")
    index.register(receipt)

    with pytest.raises(ValueError, match="reason"):
        index.mark_stale(receipt.receipt_id, ())

    assert index.get(receipt.receipt_id).lifecycle is DecisionLifecycle.ACTIVE


def test_supersession_requires_an_active_replacement_decision():
    index = DecisionAuthorityIndex()
    original = _receipt("original")
    replacement = _receipt("replacement")
    index.register(original)
    index.register(replacement)
    index.mark_stale(replacement.receipt_id, ("replacement drift",))

    with pytest.raises(ValueError, match="replacement.*active"):
        index.supersede(original.receipt_id, by_receipt_id=replacement.receipt_id)

    assert index.get(original.receipt_id).lifecycle is DecisionLifecycle.ACTIVE
