from dataclasses import replace

import pytest

from nolane.external_core.goal_design import DecisionReceipt, stable_digest
from nolane.external_core.goal_design_authenticity import verify_decision_receipt
from nolane.external_core.goal_design_ledger import AuthorityLevel, EventKind, GoalDesignLedger
from nolane.external_core.goal_design_runtime import DecisionAuthorityIndex


def _receipt(*, token: str = "authentic") -> DecisionReceipt:
    fields = {
        "goal_id": f"goal:{token}",
        "selected_option_id": f"option:{token}",
        "snapshot_digest": f"snapshot:{token}",
        "version_vector": {
            "requirements": "r1",
            "planning": "p1",
            "architecture": "a1",
            "integration": "i1",
            "context": "c1",
        },
        "evaluation_digest": f"evaluation:{token}",
        "proof_obligation_ids": (f"proof:{token}",),
        "uncertainty_ids": (f"uncertainty:{token}",),
        "evidence_refs": (f"evidence:{token}",),
        "goal_digest": f"goal-digest:{token}",
        "scenario_set_digest": f"scenario-digest:{token}",
        "option_set_digest": f"option-digest:{token}",
        "proof_state_digest": f"proof-digest:{token}",
        "uncertainty_state_digest": f"uncertainty-digest:{token}",
        "traceability_digest": f"traceability-digest:{token}",
        "input_manifest_digest": f"manifest-digest:{token}",
    }
    payload = {
        "goal_id": fields["goal_id"],
        "selected_option_id": fields["selected_option_id"],
        "snapshot_digest": fields["snapshot_digest"],
        "version_vector": fields["version_vector"],
        "evaluation_digest": fields["evaluation_digest"],
        "proof_obligation_ids": list(fields["proof_obligation_ids"]),
        "uncertainty_ids": list(fields["uncertainty_ids"]),
        "evidence_refs": list(fields["evidence_refs"]),
        "goal_digest": fields["goal_digest"],
        "scenario_set_digest": fields["scenario_set_digest"],
        "option_set_digest": fields["option_set_digest"],
        "proof_state_digest": fields["proof_state_digest"],
        "uncertainty_state_digest": fields["uncertainty_state_digest"],
        "traceability_digest": fields["traceability_digest"],
        "input_manifest_digest": fields["input_manifest_digest"],
    }
    return DecisionReceipt(
        receipt_id=stable_digest({"goal_design_decision": payload}),
        **fields,
    )


def _legacy_v1_receipt() -> DecisionReceipt:
    fields = {
        "goal_id": "goal:legacy",
        "selected_option_id": "option:legacy",
        "snapshot_digest": "snapshot:legacy",
        "version_vector": {
            "requirements": "r1",
            "planning": "p1",
            "architecture": "a1",
            "integration": "i1",
            "context": "c1",
        },
        "evaluation_digest": "evaluation:legacy",
        "proof_obligation_ids": ("proof:legacy",),
        "uncertainty_ids": ("uncertainty:legacy",),
        "evidence_refs": ("evidence:legacy",),
    }
    payload = {
        **fields,
        "proof_obligation_ids": list(fields["proof_obligation_ids"]),
        "uncertainty_ids": list(fields["uncertainty_ids"]),
        "evidence_refs": list(fields["evidence_refs"]),
    }
    return DecisionReceipt(receipt_id=stable_digest({"goal_design_decision": payload}), **fields)


def test_authority_index_accepts_content_authentic_receipt():
    receipt = _receipt()
    record = DecisionAuthorityIndex().register(receipt)
    assert record.receipt == receipt


def test_legacy_v1_receipt_remains_authentic_and_ledger_admissible():
    receipt = _legacy_v1_receipt()
    assert verify_decision_receipt(receipt) == "v1"

    ledger = GoalDesignLedger()
    event = ledger.record_decision(receipt)
    index = DecisionAuthorityIndex()
    index.register(receipt, authority_event_id=event.event_id)
    index.validate_ledger_binding(ledger)


def test_partial_v2_manifest_is_rejected_as_ambiguous_authority():
    receipt = replace(_legacy_v1_receipt(), goal_digest="goal-digest:partial")

    with pytest.raises(ValueError, match="partially populated v2 manifest"):
        verify_decision_receipt(receipt)


def test_authority_index_rejects_receipt_body_rebound_under_old_identity():
    receipt = _receipt()
    forged = replace(receipt, selected_option_id="option:forged")

    with pytest.raises(ValueError, match="receipt.*identity|identity.*receipt"):
        DecisionAuthorityIndex().register(forged)


def test_authority_restore_rejects_tampered_receipt_body_with_unchanged_identity():
    receipt = _receipt()
    index = DecisionAuthorityIndex()
    index.register(receipt)
    state = index.to_state()
    state["records"][0]["receipt"]["input_manifest_digest"] = "manifest:forged"

    with pytest.raises(ValueError, match="receipt.*identity|identity.*receipt"):
        DecisionAuthorityIndex.from_state(state)


def test_ledger_rejects_forged_decision_receipt_before_minting_authority_event():
    receipt = _receipt()
    forged = replace(receipt, evaluation_digest="evaluation:forged")
    ledger = GoalDesignLedger()

    with pytest.raises(ValueError, match="receipt.*identity|identity.*receipt"):
        ledger.record_decision(forged)

    assert ledger.events == ()


def test_authority_index_ledger_binding_rejects_missing_authority_event():
    receipt = _receipt()
    index = DecisionAuthorityIndex()
    index.register(receipt, authority_event_id="event:missing")

    with pytest.raises(ValueError, match="authority event|ledger"):
        index.validate_ledger_binding(GoalDesignLedger())


def test_authority_index_ledger_binding_proves_exact_decision_event_semantics():
    receipt = _receipt()
    ledger = GoalDesignLedger()
    event = ledger.record_decision(receipt)
    index = DecisionAuthorityIndex()
    index.register(receipt, authority_event_id=event.event_id)
    index.validate_ledger_binding(ledger)

    rebound = ledger.to_state()
    rebound["events"][0]["kind"] = EventKind.PROPOSAL.value
    rebound["events"][0]["authority_level"] = AuthorityLevel.THOUGHT.value
    identity = {
        "kind": EventKind.PROPOSAL.value,
        "authority_level": AuthorityLevel.THOUGHT.value,
        "payload_digest": rebound["events"][0]["payload_digest"],
        "parents": rebound["events"][0]["parent_ids"],
        "subjects": rebound["events"][0]["subject_refs"],
    }
    forged_event_id = stable_digest({"goal_design_event": identity})
    rebound["events"][0]["event_id"] = forged_event_id
    forged_ledger = GoalDesignLedger.from_state(rebound)

    rebound_index_state = index.to_state()
    rebound_index_state["records"][0]["authority_event_id"] = forged_event_id
    rebound_index = DecisionAuthorityIndex.from_state(rebound_index_state)

    with pytest.raises(ValueError, match="not a decision authority event|does not prove"):
        rebound_index.validate_ledger_binding(forged_ledger)
