import pytest

from nolane.external_core.goal_design import (
    DecisionClass,
    DesignOption,
    DesignScenario,
    GoalDesignCoherencePlane,
    GoalDesignVersionVector,
    GoalObjective,
    GoalSpec,
    ObjectiveDirection,
)
from nolane.external_core.goal_design_context import (
    DecisionContextContradiction,
    DecisionContextPolicy,
    GoalDesignDecisionContextCompiler,
)
from nolane.external_core.goal_design_integrity import (
    GOAL_DESIGN_PLANES,
    GoalIntegrityAttestation,
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
    assess_goal_integrity,
    mint_goal_integrity_receipt,
)
from nolane.external_core.goal_design_integrity_runtime import GoalIntegrityRuntime


def _contract(goal_id):
    return GoalIntegrityContract(
        goal_id=goal_id,
        clauses=(
            GoalIntegrityClause(
                "intent:terminal",
                goal_id,
                GoalIntegrityClauseKind.TERMINAL_GOAL,
                "Preserve the exact authorized terminal objective.",
                "prov:terminal",
            ),
            GoalIntegrityClause(
                "constraint:context",
                goal_id,
                GoalIntegrityClauseKind.HARD_CONSTRAINT,
                "Compiled context cannot rebind semantic authority.",
                "prov:context",
            ),
        ),
    )


def _integrity_receipt(contract, receipt):
    clause_ids = tuple(clause.clause_id for clause in contract.clauses)
    attestations = tuple(
        GoalIntegrityAttestation(
            attestation_id=f"att:{plane}:{contract.digest[:12]}",
            goal_id=contract.goal_id,
            plane=plane,
            subject_ref=f"{plane}:authority",
            contract_digest=contract.digest,
            preserved_clause_ids=clause_ids,
            evidence_refs=(f"evidence:{plane}",),
        )
        for plane in GOAL_DESIGN_PLANES
    )
    assessment = assess_goal_integrity(contract, attestations)
    return mint_goal_integrity_receipt(
        decision_receipt=receipt,
        contract=contract,
        assessment=assessment,
    )


def _v2_artifacts():
    goal = GoalSpec(
        "goal:context-v2",
        "Compile exact v2 decision context",
        objectives=(GoalObjective("quality", ObjectiveDirection.MAXIMIZE),),
    )
    scenarios = (DesignScenario("base", 1.0),)
    options = (
        DesignOption(
            "champion",
            "Authorized champion",
            {"base": 0.9},
            {"quality": 0.9},
            DecisionClass.REVERSIBLE,
        ),
        DesignOption(
            "rival",
            "Authorized rival",
            {"base": 0.4},
            {"quality": 0.4},
            DecisionClass.REVERSIBLE,
        ),
    )
    plane = GoalDesignCoherencePlane()
    vector = GoalDesignVersionVector("r:1", "p:1", "a:1", "i:1", "c:1")
    snapshot = plane.freeze_snapshot(vector)
    receipt = plane.admit_decision(
        goal=goal,
        scenarios=scenarios,
        options=options,
        selected_option_id="champion",
        snapshot=snapshot,
        current_vector=vector,
    )
    contract = _contract(goal.goal_id)
    return goal, scenarios, options, receipt, contract, _integrity_receipt(contract, receipt)


def _v3_artifacts():
    goal = GoalSpec(
        "goal:context-v3",
        "Compile exact assumption-bound v3 decision context",
        objectives=(GoalObjective("quality", ObjectiveDirection.MAXIMIZE),),
        assumption_refs=("assumption:goal",),
    )
    scenarios = (DesignScenario("base", 1.0),)
    options = (
        DesignOption(
            "champion",
            "Truth-bound champion",
            {"base": 0.9},
            {"quality": 0.9},
            DecisionClass.REVERSIBLE,
            assumption_refs=("assumption:champion",),
        ),
        DesignOption(
            "rival",
            "Truth-bound rival",
            {"base": 0.4},
            {"quality": 0.4},
            DecisionClass.REVERSIBLE,
            assumption_refs=("assumption:rival",),
        ),
    )
    plane = GoalDesignCoherencePlane()
    vector = GoalDesignVersionVector("r:1", "p:1", "a:1", "i:1", "c:1")
    snapshot = plane.freeze_snapshot(vector)
    receipt = plane.admit_decision(
        goal=goal,
        scenarios=scenarios,
        options=options,
        selected_option_id="champion",
        snapshot=snapshot,
        current_vector=vector,
        assumption_state_digest="truth:snapshot:v3",
    )
    contract = _contract(goal.goal_id)
    return goal, scenarios, options, receipt, contract, _integrity_receipt(contract, receipt)


def test_v3_assumption_bound_context_compiles_against_exact_truth_capable_inputs():
    goal, scenarios, options, receipt, contract, integrity = _v3_artifacts()
    context = GoalDesignDecisionContextCompiler().compile(
        decision_receipt=receipt,
        integrity_contract=contract,
        integrity_receipt=integrity,
        goal=goal,
        scenarios=scenarios,
        options=options,
    )

    assert set(receipt.assumption_refs) == {
        "assumption:goal",
        "assumption:champion",
        "assumption:rival",
    }
    assert context.decision_receipt_id == receipt.receipt_id
    assert context.goal_digest == receipt.goal_digest
    assert context.option_set_digest == receipt.option_set_digest


def test_v3_rival_assumption_rebinding_is_rejected_even_when_option_id_is_unchanged():
    goal, scenarios, options, receipt, contract, integrity = _v3_artifacts()
    mutated = (
        options[0],
        DesignOption(
            "rival",
            options[1].label,
            options[1].utilities,
            options[1].objective_values,
            options[1].decision_class,
            assumption_refs=("assumption:substituted-rival",),
        ),
    )

    with pytest.raises(ValueError, match="assumption|option|manifest|digest"):
        GoalDesignDecisionContextCompiler().compile(
            decision_receipt=receipt,
            integrity_contract=contract,
            integrity_receipt=integrity,
            goal=goal,
            scenarios=scenarios,
            options=mutated,
        )


def test_foreign_goal_contradiction_cannot_enter_authorized_context():
    goal, scenarios, options, receipt, contract, integrity = _v2_artifacts()
    foreign = DecisionContextContradiction(
        "contradiction:foreign",
        "goal:foreign",
        "Foreign-goal evidence must not enter this decision context.",
        subject_refs=("champion",),
        evidence_refs=("evidence:foreign",),
        provenance_ref="provenance:foreign",
    )

    with pytest.raises(ValueError, match="different goal|contradiction"):
        GoalDesignDecisionContextCompiler().compile(
            decision_receipt=receipt,
            integrity_contract=contract,
            integrity_receipt=integrity,
            goal=goal,
            scenarios=scenarios,
            options=options,
            contradictions=(foreign,),
        )


def test_contradiction_reordering_preserves_context_identity():
    goal, scenarios, options, receipt, contract, integrity = _v2_artifacts()
    contradictions = (
        DecisionContextContradiction(
            "contradiction:a",
            goal.goal_id,
            "Evidence A conflicts with the current design hypothesis.",
            subject_refs=("champion",),
            evidence_refs=("evidence:a",),
            provenance_ref="provenance:a",
        ),
        DecisionContextContradiction(
            "contradiction:b",
            goal.goal_id,
            "Evidence B conflicts with the current design hypothesis.",
            subject_refs=("rival",),
            evidence_refs=("evidence:b",),
            provenance_ref="provenance:b",
        ),
    )
    compiler = GoalDesignDecisionContextCompiler()
    first = compiler.compile(
        decision_receipt=receipt,
        integrity_contract=contract,
        integrity_receipt=integrity,
        goal=goal,
        scenarios=scenarios,
        options=options,
        contradictions=contradictions,
    )
    second = compiler.compile(
        decision_receipt=receipt,
        integrity_contract=contract,
        integrity_receipt=integrity,
        goal=goal,
        scenarios=scenarios,
        options=options,
        contradictions=tuple(reversed(contradictions)),
    )

    assert first.context_id == second.context_id
    assert tuple(pin.pin_id for pin in first.pins) == tuple(pin.pin_id for pin in second.pins)


def test_runtime_rejects_conflicting_compiler_and_context_policy_configuration():
    compiler = GoalDesignDecisionContextCompiler(
        policy=DecisionContextPolicy(critical_uncertainty_threshold=0.8)
    )
    with pytest.raises(ValueError, match="compiler|policy|disagree"):
        GoalIntegrityRuntime.__new__(GoalIntegrityRuntime).__init__(
            decision_context_compiler=compiler,
            decision_context_policy=DecisionContextPolicy(critical_uncertainty_threshold=0.2),
        )
