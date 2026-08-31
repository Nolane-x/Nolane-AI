from dataclasses import replace

import pytest

from nolane.external_core.goal_design import DecisionReceipt
from nolane.external_core.goal_design_authenticity import (
    expected_decision_receipt_id,
    verify_decision_receipt,
)
from nolane.external_core.goal_design_integrity import (
    GOAL_DESIGN_PLANES,
    GoalIntegrityAttestation,
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
    GoalIntegrityMetricBinding,
    assess_goal_integrity,
    mint_goal_integrity_receipt,
    verify_goal_integrity_receipt,
)


def _clause(
    clause_id: str,
    kind: GoalIntegrityClauseKind,
    statement: str,
    *,
    planes=GOAL_DESIGN_PLANES,
    goal_id: str = "goal:ship",
):
    return GoalIntegrityClause(
        clause_id=clause_id,
        goal_id=goal_id,
        kind=kind,
        statement=statement,
        provenance_ref=f"prov:{clause_id}",
        required_planes=tuple(planes),
    )


def _contract() -> GoalIntegrityContract:
    terminal = _clause(
        "intent:terminal",
        GoalIntegrityClauseKind.TERMINAL_GOAL,
        "Improve verified user task completion without sacrificing user control.",
    )
    safety = _clause(
        "constraint:control",
        GoalIntegrityClauseKind.HARD_CONSTRAINT,
        "Never remove explicit user control to improve completion metrics.",
        planes=("requirements", "planning", "architecture", "integration"),
    )
    anti = _clause(
        "anti:proxy",
        GoalIntegrityClauseKind.ANTI_GOAL,
        "Do not optimize engagement as a substitute for task completion.",
        planes=("requirements", "planning", "context"),
    )
    criterion = _clause(
        "criterion:verified-completion",
        GoalIntegrityClauseKind.SUCCESS_CRITERION,
        "Verified completion improves on the agreed evaluation set.",
        planes=("requirements", "planning", "context"),
    )
    metric = GoalIntegrityMetricBinding(
        metric_id="metric:verified-completion",
        goal_id="goal:ship",
        criterion_ref=criterion.clause_id,
        metric_ref="eval:verified-completion-v1",
        provenance_ref="prov:metric",
    )
    return GoalIntegrityContract(
        goal_id="goal:ship",
        clauses=(terminal, safety, anti, criterion),
        metric_bindings=(metric,),
    )


def _attestation(
    contract: GoalIntegrityContract,
    plane: str,
    *,
    preserved=None,
    violated=(),
    contract_digest=None,
    goal_id=None,
    attestation_id=None,
):
    violated = tuple(violated)
    if preserved is None:
        violated_set = set(violated)
        preserved = tuple(
            clause.clause_id
            for clause in contract.clauses
            if plane in clause.required_planes and clause.clause_id not in violated_set
        )
    return GoalIntegrityAttestation(
        attestation_id=attestation_id or f"att:{plane}",
        goal_id=goal_id or contract.goal_id,
        plane=plane,
        subject_ref=f"{plane}:rev-1",
        contract_digest=contract.digest if contract_digest is None else contract_digest,
        preserved_clause_ids=tuple(preserved),
        violated_clause_ids=violated,
        evidence_refs=(f"evidence:{plane}",),
    )


def _complete_attestations(contract: GoalIntegrityContract):
    return tuple(_attestation(contract, plane) for plane in GOAL_DESIGN_PLANES)


def _decision_receipt() -> DecisionReceipt:
    provisional = DecisionReceipt(
        receipt_id="",
        goal_id="goal:ship",
        selected_option_id="option:safe",
        snapshot_digest="snapshot:1",
        version_vector={plane: f"{plane}:1" for plane in GOAL_DESIGN_PLANES},
        evaluation_digest="evaluation:1",
        proof_obligation_ids=(),
        uncertainty_ids=(),
        evidence_refs=("evidence:decision",),
    )
    return replace(
        provisional,
        receipt_id=expected_decision_receipt_id(provisional),
    )


def test_contract_is_content_addressed_and_terminal_intent_is_identity_bearing():
    original = _contract()
    changed_terminal = replace(
        original.clauses[0],
        statement="Maximize raw completion count regardless of user control.",
    )
    changed = GoalIntegrityContract(
        goal_id=original.goal_id,
        clauses=(changed_terminal,) + original.clauses[1:],
        metric_bindings=original.metric_bindings,
    )

    assert original.digest != changed.digest
    assert original.terminal_clause_ids == ("intent:terminal",)


def test_contract_order_is_canonical_and_noise_free():
    contract = _contract()
    reordered = GoalIntegrityContract(
        goal_id=contract.goal_id,
        clauses=tuple(reversed(contract.clauses)),
        metric_bindings=tuple(reversed(contract.metric_bindings)),
    )

    assert reordered == contract
    assert reordered.digest == contract.digest


def test_contract_requires_terminal_goal_and_unique_identities():
    with pytest.raises(ValueError, match="terminal"):
        GoalIntegrityContract(
            goal_id="goal:ship",
            clauses=(
                _clause(
                    "criterion:only",
                    GoalIntegrityClauseKind.SUCCESS_CRITERION,
                    "A proxy improved.",
                ),
            ),
        )

    terminal = _clause(
        "intent:dup",
        GoalIntegrityClauseKind.TERMINAL_GOAL,
        "Preserve the real intent.",
    )
    duplicate = _clause(
        "intent:dup",
        GoalIntegrityClauseKind.ANTI_GOAL,
        "Do not replace it.",
    )
    with pytest.raises(ValueError, match="duplicate clause"):
        GoalIntegrityContract(goal_id="goal:ship", clauses=(terminal, duplicate))


def test_metric_binding_must_target_success_criterion_not_terminal_goal():
    terminal = _clause(
        "intent:terminal",
        GoalIntegrityClauseKind.TERMINAL_GOAL,
        "Preserve user control.",
    )
    proxy = GoalIntegrityMetricBinding(
        metric_id="metric:proxy",
        goal_id="goal:ship",
        criterion_ref=terminal.clause_id,
        metric_ref="metric:engagement",
        provenance_ref="prov:metric",
    )

    with pytest.raises(ValueError, match="success criterion"):
        GoalIntegrityContract(
            goal_id="goal:ship",
            clauses=(terminal,),
            metric_bindings=(proxy,),
        )


def test_unknown_plane_and_self_contradictory_attestation_fail_closed():
    contract = _contract()
    with pytest.raises(ValueError, match="unknown Goal/Design plane"):
        _attestation(contract, "marketing")

    with pytest.raises(ValueError, match="both preserved and violated"):
        _attestation(
            contract,
            "requirements",
            preserved=("intent:terminal",),
            violated=("intent:terminal",),
        )


def test_missing_required_plane_attestation_blocks_authority():
    contract = _contract()
    attestations = tuple(
        _attestation(contract, plane)
        for plane in GOAL_DESIGN_PLANES
        if plane != "integration"
    )

    assessment = assess_goal_integrity(contract, attestations)

    assert not assessment.authorized
    assert ("integration", "intent:terminal") in assessment.missing_preservations
    assert ("integration", "constraint:control") in assessment.missing_preservations


def test_hard_constraint_or_anti_goal_violation_blocks_even_when_terminal_survives():
    contract = _contract()
    attestations = list(_complete_attestations(contract))
    requirements = _attestation(
        contract,
        "requirements",
        violated=("anti:proxy",),
    )
    attestations[GOAL_DESIGN_PLANES.index("requirements")] = requirements

    assessment = assess_goal_integrity(contract, attestations)

    assert not assessment.authorized
    assert assessment.violated_clause_ids == ("anti:proxy",)
    assert "intent:terminal" not in assessment.violated_clause_ids


def test_stale_attestation_cannot_authorize_a_new_contract_revision():
    contract = _contract()
    stale = _attestation(
        contract,
        "requirements",
        contract_digest="contract:old",
    )
    attestations = (stale,) + tuple(
        _attestation(contract, plane)
        for plane in GOAL_DESIGN_PLANES
        if plane != "requirements"
    )

    assessment = assess_goal_integrity(contract, attestations)

    assert not assessment.authorized
    assert assessment.stale_attestation_ids == ("att:requirements",)
    assert ("requirements", "intent:terminal") in assessment.missing_preservations


def test_foreign_attestation_is_non_authoritative_and_does_not_perturb_identity():
    contract = _contract()
    valid = _complete_attestations(contract)
    baseline = assess_goal_integrity(contract, valid)
    foreign = _attestation(
        contract,
        "requirements",
        goal_id="goal:other",
        attestation_id="att:foreign",
    )
    noisy = assess_goal_integrity(contract, valid + (foreign,))

    assert baseline.authorized
    assert noisy.authorized
    assert noisy == baseline
    assert noisy.digest == baseline.digest


def test_integrity_receipt_binds_existing_decision_without_rewriting_decision_identity():
    contract = _contract()
    assessment = assess_goal_integrity(contract, _complete_attestations(contract))
    decision = _decision_receipt()
    original_decision_id = decision.receipt_id

    integrity = mint_goal_integrity_receipt(
        decision_receipt=decision,
        contract=contract,
        assessment=assessment,
    )

    assert verify_decision_receipt(decision) == "v1"
    assert decision.receipt_id == original_decision_id
    assert integrity.decision_receipt_id == decision.receipt_id
    assert integrity.contract_digest == contract.digest
    assert verify_goal_integrity_receipt(integrity, decision) is None


def test_integrity_receipt_rejects_tamper_and_unauthorized_assessment():
    contract = _contract()
    decision = _decision_receipt()
    complete = assess_goal_integrity(contract, _complete_attestations(contract))
    integrity = mint_goal_integrity_receipt(
        decision_receipt=decision,
        contract=contract,
        assessment=complete,
    )

    tampered = replace(integrity, selected_option_id="option:proxy")
    with pytest.raises(ValueError, match="identity|selected option"):
        verify_goal_integrity_receipt(tampered, decision)

    incomplete = assess_goal_integrity(
        contract,
        tuple(
            _attestation(contract, plane)
            for plane in GOAL_DESIGN_PLANES
            if plane != "context"
        ),
    )
    with pytest.raises(ValueError, match="not authorized"):
        mint_goal_integrity_receipt(
            decision_receipt=decision,
            contract=contract,
            assessment=incomplete,
        )
