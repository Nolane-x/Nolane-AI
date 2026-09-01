from copy import deepcopy

import pytest

from nolane.external_core.goal_design import DecisionClass, stable_digest
from nolane.external_core.goal_design_reopening import (
    DecisionReopeningAuthority,
    ReopeningDisposition,
)
from nolane.external_core.goal_design_truth import (
    AssumptionClaim,
    AssumptionEvidence,
    AssumptionPolarity,
    AssumptionTruthMaintenance,
)


def _truth(*, criticality: float = 0.9, initial_support: float = 0.9):
    truth = AssumptionTruthMaintenance()
    truth.register(
        AssumptionClaim(
            "asm:core",
            "Core assumption",
            criticality=criticality,
        )
    )
    truth.add_evidence(
        AssumptionEvidence(
            "ev:initial",
            "asm:core",
            AssumptionPolarity.SUPPORTS,
            initial_support,
            "evidence:initial",
        )
    )
    return truth


def _open_refutation_case():
    truth = _truth()
    authority = DecisionReopeningAuthority()
    authority.register_decision(
        receipt_id="decision:core",
        decision_class=DecisionClass.REVERSIBLE,
        truth=truth,
        assumption_ids=("asm:core",),
    )
    truth.retract_evidence("ev:initial", reason_ref="correction:initial")
    truth.add_evidence(
        AssumptionEvidence(
            "ev:refute",
            "asm:core",
            AssumptionPolarity.REFUTES,
            0.99,
            "evidence:refute",
        )
    )
    authority.assess_change(
        receipt_id="decision:core",
        truth=truth,
        affected_assumption_ids=("asm:core",),
    )
    return truth, authority


def _recompute_state_digest(state):
    body = {
        "schema_version": state["schema_version"],
        "baselines": state["baselines"],
        "obligations": state["obligations"],
        "cases": state["cases"],
    }
    state["state_digest"] = stable_digest({"goal_design_reopening_state": body})


def _recompute_case_digest(case):
    payload = {key: value for key, value in case.items() if key != "digest"}
    case["digest"] = stable_digest({"goal_design_reopening_case": payload})


def test_favorable_unknown_to_supported_evidence_does_not_reopen():
    truth = _truth(initial_support=0.2)
    authority = DecisionReopeningAuthority()
    authority.register_decision(
        receipt_id="decision:favorable",
        decision_class=DecisionClass.REVERSIBLE,
        truth=truth,
        assumption_ids=("asm:core",),
    )

    truth.add_evidence(
        AssumptionEvidence(
            "ev:strong-support",
            "asm:core",
            AssumptionPolarity.SUPPORTS,
            0.9,
            "evidence:strong-support",
        )
    )
    assessment = authority.assess_change(
        receipt_id="decision:favorable",
        truth=truth,
        affected_assumption_ids=("asm:core",),
    )

    assert assessment.disposition is ReopeningDisposition.NO_REOPEN
    assert assessment.material_assumption_ids == ()
    assert assessment.monitored_assumption_ids == ("asm:core",)


def test_restore_rejects_ready_case_with_open_blocking_obligation_even_if_digests_recomputed():
    _, authority = _open_refutation_case()
    state = deepcopy(authority.to_state())
    case = state["cases"][0]
    assert state["obligations"][0]["status"] == "open"

    case["status"] = "ready_for_readmission"
    _recompute_case_digest(case)
    _recompute_state_digest(state)

    with pytest.raises(ValueError, match="ready|obligation|coherence"):
        DecisionReopeningAuthority.from_state(state)


def test_restore_rejects_false_new_receipt_flag_when_truth_digest_changed_even_if_digests_recomputed():
    _, authority = _open_refutation_case()
    state = deepcopy(authority.to_state())
    case = state["cases"][0]
    assert case["baseline_truth_digest"] != case["current_truth_digest"]

    case["requires_new_receipt"] = False
    _recompute_case_digest(case)
    _recompute_state_digest(state)

    with pytest.raises(ValueError, match="new receipt|truth digest|coherence"):
        DecisionReopeningAuthority.from_state(state)


def test_restore_rejects_case_whose_obligation_belongs_to_different_receipt():
    _, authority = _open_refutation_case()
    state = deepcopy(authority.to_state())
    obligation = state["obligations"][0]
    obligation["receipt_id"] = "decision:other"
    obligation_payload = {key: value for key, value in obligation.items() if key != "digest"}
    obligation["digest"] = stable_digest({"goal_design_reopening_obligation": obligation_payload})
    _recompute_state_digest(state)

    with pytest.raises(ValueError, match="receipt|obligation|coherence"):
        DecisionReopeningAuthority.from_state(state)
