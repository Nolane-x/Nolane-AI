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
    ProofObligation,
    ProofStatus,
    UncertaintyItem,
)
from nolane.external_core.goal_design_context import GoalDesignDecisionContextCompiler
from nolane.external_core.goal_design_integrity import (
    GOAL_DESIGN_PLANES,
    GoalIntegrityAttestation,
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
    assess_goal_integrity,
    mint_goal_integrity_receipt,
)


def _goal(statement="Preserve exact authorized semantics in compiled context"):
    return GoalSpec(
        "goal:context-adversarial",
        statement,
        objectives=(GoalObjective("quality", ObjectiveDirection.MAXIMIZE),),
        constraints=("Never substitute stale decision inputs.",),
        evidence_refs=("evidence:goal",),
    )


def _scenarios(probability=1.0):
    return (
        DesignScenario(
            "base",
            probability,
            evidence_refs=("evidence:scenario",),
        ),
    )


def _options(champion_label="Authorized champion", champion_utility=0.9):
    return (
        DesignOption(
            "champion",
            champion_label,
            {"base": champion_utility},
            {"quality": champion_utility},
            DecisionClass.REVERSIBLE,
            evidence_refs=("evidence:champion",),
        ),
        DesignOption(
            "rival",
            "Authorized rival",
            {"base": 0.4},
            {"quality": 0.4},
            DecisionClass.REVERSIBLE,
            evidence_refs=("evidence:rival",),
        ),
    )


def _proofs(claim="Context manifest remains exact"):
    return (
        ProofObligation(
            "proof:manifest",
            claim,
            status=ProofStatus.OPEN,
            evidence_refs=("evidence:proof",),
            blocking=False,
        ),
    )


def _uncertainties(statement="A downstream consumer may use stale context"):
    return (
        UncertaintyItem(
            "unknown:stale-context",
            statement,
            uncertainty=0.9,
            impact=0.9,
            decision_sensitivity=0.9,
            observability=0.5,
            evidence_refs=("evidence:uncertainty",),
        ),
    )


def _contract():
    goal_id = "goal:context-adversarial"
    return GoalIntegrityContract(
        goal_id=goal_id,
        clauses=(
            GoalIntegrityClause(
                "intent:terminal",
                goal_id,
                GoalIntegrityClauseKind.TERMINAL_GOAL,
                "Preserve exact authorized semantics.",
                "prov:terminal",
            ),
            GoalIntegrityClause(
                "constraint:no-rebind",
                goal_id,
                GoalIntegrityClauseKind.HARD_CONSTRAINT,
                "Never rebind context to stale decision inputs.",
                "prov:no-rebind",
            ),
        ),
    )


def _artifacts():
    goal = _goal()
    scenarios = _scenarios()
    options = _options()
    proofs = _proofs()
    uncertainties = _uncertainties()
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
        proof_obligations=proofs,
        uncertainties=uncertainties,
    )
    contract = _contract()
    clause_ids = tuple(clause.clause_id for clause in contract.clauses)
    attestations = tuple(
        GoalIntegrityAttestation(
            attestation_id=f"att:{plane_name}:{contract.digest[:12]}",
            goal_id=contract.goal_id,
            plane=plane_name,
            subject_ref=f"{plane_name}:authority",
            contract_digest=contract.digest,
            preserved_clause_ids=clause_ids,
            evidence_refs=(f"evidence:{plane_name}",),
        )
        for plane_name in GOAL_DESIGN_PLANES
    )
    assessment = assess_goal_integrity(contract, attestations)
    integrity_receipt = mint_goal_integrity_receipt(
        decision_receipt=receipt,
        contract=contract,
        assessment=assessment,
    )
    return receipt, contract, integrity_receipt, goal, scenarios, options, proofs, uncertainties


def _compile(*, goal=None, scenarios=None, options=None, proofs=None, uncertainties=None):
    receipt, contract, integrity_receipt, original_goal, original_scenarios, original_options, original_proofs, original_uncertainties = _artifacts()
    return GoalDesignDecisionContextCompiler().compile(
        decision_receipt=receipt,
        integrity_contract=contract,
        integrity_receipt=integrity_receipt,
        goal=original_goal if goal is None else goal,
        scenarios=original_scenarios if scenarios is None else scenarios,
        options=original_options if options is None else options,
        proof_obligations=original_proofs if proofs is None else proofs,
        uncertainties=original_uncertainties if uncertainties is None else uncertainties,
    )


def test_goal_statement_substitution_cannot_rebind_context_to_receipt_digest():
    with pytest.raises(ValueError, match="goal|manifest|digest|bind"):
        _compile(goal=_goal("Same goal id but substituted terminal semantics"))


def test_scenario_state_substitution_cannot_rebind_context_to_receipt_digest():
    mutated = (
        DesignScenario("base", 3.0, evidence_refs=("evidence:mutated-scenario",)),
    )
    with pytest.raises(ValueError, match="scenario|manifest|digest|bind"):
        _compile(scenarios=mutated)


def test_option_state_substitution_cannot_launder_champion_or_rival_pins():
    with pytest.raises(ValueError, match="option|evaluation|manifest|digest|bind"):
        _compile(options=_options("Substituted champion label", 0.51))


def test_proof_state_substitution_cannot_launder_open_proof_pin():
    with pytest.raises(ValueError, match="proof|manifest|digest|bind"):
        _compile(proofs=_proofs("Substituted proof claim under the same proof id"))


def test_uncertainty_state_substitution_cannot_launder_critical_unknown_pin():
    with pytest.raises(ValueError, match="uncertainty|manifest|digest|bind"):
        _compile(uncertainties=_uncertainties("Substituted uncertainty statement"))


def test_canonical_reordering_preserves_context_identity():
    receipt, contract, integrity_receipt, goal, scenarios, options, proofs, uncertainties = _artifacts()
    compiler = GoalDesignDecisionContextCompiler()
    original = compiler.compile(
        decision_receipt=receipt,
        integrity_contract=contract,
        integrity_receipt=integrity_receipt,
        goal=goal,
        scenarios=scenarios,
        options=options,
        proof_obligations=proofs,
        uncertainties=uncertainties,
    )
    reordered = compiler.compile(
        decision_receipt=receipt,
        integrity_contract=contract,
        integrity_receipt=integrity_receipt,
        goal=goal,
        scenarios=tuple(reversed(scenarios)),
        options=tuple(reversed(options)),
        proof_obligations=tuple(reversed(proofs)),
        uncertainties=tuple(reversed(uncertainties)),
    )
    assert reordered.context_id == original.context_id
