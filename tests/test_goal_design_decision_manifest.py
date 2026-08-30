from dataclasses import replace

from nolane.external_core.goal_design import (
    DecisionClass,
    DesignOption,
    DesignScenario,
    GoalDesignCoherencePlane,
    GoalDesignVersionVector,
    GoalObjective,
    GoalSpec,
    ObjectiveDirection,
    ProofObligation,
    ProofStatus,
    TraceabilityState,
    UncertaintyItem,
)


def _goal(**overrides):
    base = dict(
        goal_id="goal:manifest",
        statement="Bind design authority to the complete decision input state",
        objectives=(
            GoalObjective("quality", ObjectiveDirection.MAXIMIZE, weight=0.7),
            GoalObjective("risk", ObjectiveDirection.MINIMIZE, weight=0.3),
        ),
        constraints=("preserve specialist authority",),
        assumptions=("five-plane state is observable",),
        evidence_refs=("ev:goal",),
    )
    base.update(overrides)
    return GoalSpec(**base)


def _scenarios():
    return (
        DesignScenario("base", 0.8, tags=("baseline",), evidence_refs=("ev:base",)),
        DesignScenario("break", 0.2, tags=("counterfactual",), evidence_refs=("ev:break",)),
    )


def _options(requirement_refs=("req:1",)):
    return (
        DesignOption(
            "selected",
            "Federated design",
            {"base": 0.9, "break": 0.75},
            {"quality": 0.92, "risk": 0.12},
            decision_class=DecisionClass.REVERSIBLE,
            evidence_refs=("ev:selected",),
            requirement_refs=requirement_refs,
            component_refs=("cmp:1",),
            assumptions=("adapter remains read-only",),
        ),
        DesignOption(
            "alternate",
            "Alternative design",
            {"base": 0.72, "break": 0.64},
            {"quality": 0.75, "risk": 0.25},
            evidence_refs=("ev:alternate",),
        ),
    )


def _vector():
    return GoalDesignVersionVector("r1", "p1", "a1", "i1", "c1")


def _traceability():
    return TraceabilityState(
        active_requirement_ids=("req:1",),
        planned_requirement_ids=("req:1",),
        architecture_component_ids=("cmp:1",),
        integration_component_refs=("cmp:1",),
    )


def _admit(*, goal=None, scenarios=None, options=None, proofs=None, uncertainties=None, traceability=None):
    authority = GoalDesignCoherencePlane()
    vector = _vector()
    snapshot = authority.freeze_snapshot(vector)
    return authority.admit_decision(
        goal=goal or _goal(),
        scenarios=scenarios or _scenarios(),
        options=options or _options(),
        selected_option_id="selected",
        snapshot=snapshot,
        current_vector=vector,
        proof_obligations=proofs or (),
        uncertainties=uncertainties or (),
        traceability=traceability if traceability is not None else _traceability(),
    )


def test_receipt_exposes_complete_content_addressed_decision_manifest():
    receipt = _admit(
        proofs=(
            ProofObligation(
                "proof:1",
                "compatibility verified",
                ProofStatus.SATISFIED,
                evidence_refs=("ev:proof",),
            ),
        ),
        uncertainties=(
            UncertaintyItem(
                "uncertainty:1",
                "downstream implementation variance",
                0.3,
                0.4,
                0.5,
                evidence_refs=("ev:uncertainty",),
                resolved=True,
            ),
        ),
    )

    assert receipt.goal_digest
    assert receipt.scenario_set_digest
    assert receipt.option_set_digest
    assert receipt.proof_state_digest
    assert receipt.uncertainty_state_digest
    assert receipt.traceability_digest
    assert receipt.input_manifest_digest


def test_receipt_identity_changes_when_goal_assumption_changes_without_goal_id_change():
    first = _admit()
    changed_goal = _goal(assumptions=("five-plane state is observable", "architecture source changed"))
    second = _admit(goal=changed_goal)
    assert first.receipt_id != second.receipt_id
    assert first.goal_digest != second.goal_digest


def test_receipt_identity_changes_when_selected_option_dependencies_change():
    first = _admit(options=_options(("req:1",)))
    second = _admit(options=_options(("req:1", "req:2")))
    assert first.receipt_id != second.receipt_id
    assert first.option_set_digest != second.option_set_digest


def test_receipt_identity_changes_when_proof_semantics_change_with_same_proof_id():
    satisfied = ProofObligation(
        "proof:1",
        "compatibility verified",
        ProofStatus.SATISFIED,
        evidence_refs=("ev:proof",),
    )
    waived = ProofObligation(
        "proof:1",
        "compatibility verified",
        ProofStatus.WAIVED,
        evidence_refs=("ev:proof",),
        waiver_reason="temporary controlled exception",
    )
    first = _admit(proofs=(satisfied,))
    second = _admit(proofs=(waived,))
    assert first.receipt_id != second.receipt_id
    assert first.proof_state_digest != second.proof_state_digest


def test_receipt_identity_changes_when_uncertainty_state_changes_with_same_uncertainty_id():
    unresolved = UncertaintyItem(
        "uncertainty:1",
        "downstream implementation variance",
        0.3,
        0.4,
        0.5,
        evidence_refs=("ev:uncertainty",),
        resolved=False,
    )
    resolved = replace(unresolved, resolved=True, mitigation_ref="mitigation:1")
    first = _admit(uncertainties=(unresolved,))
    second = _admit(uncertainties=(resolved,))
    assert first.receipt_id != second.receipt_id
    assert first.uncertainty_state_digest != second.uncertainty_state_digest


def test_evaluation_digest_binds_goal_and_complete_option_set_not_only_numeric_outputs():
    authority = GoalDesignCoherencePlane()
    first = authority.evaluate_options(_goal(), _scenarios(), _options())
    changed_goal = _goal(
        objectives=(
            GoalObjective("quality", ObjectiveDirection.MAXIMIZE, weight=0.5, description="quality v2"),
            GoalObjective("risk", ObjectiveDirection.MINIMIZE, weight=0.5),
        )
    )
    second = authority.evaluate_options(changed_goal, _scenarios(), _options())
    assert first.digest != second.digest


def test_identical_complete_decision_inputs_remain_deterministic():
    first = _admit()
    second = _admit()
    assert first.receipt_id == second.receipt_id
    assert first.input_manifest_digest == second.input_manifest_digest


def test_receipt_inherits_evidence_from_every_evaluated_option():
    receipt = _admit()

    assert "ev:selected" in receipt.evidence_refs
    assert "ev:alternate" in receipt.evidence_refs
