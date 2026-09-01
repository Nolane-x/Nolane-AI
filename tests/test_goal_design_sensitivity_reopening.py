from copy import deepcopy
from types import SimpleNamespace

import pytest

from nolane.external_core.architecture import ArchitectureGraph
from nolane.external_core.goal_design import (
    DecisionClass,
    DesignOption,
    DesignScenario,
    GoalSpec,
    UncertaintyItem,
)
from nolane.external_core.goal_design_reopening import (
    DecisionReopeningAuthority,
    ReopeningCaseStatus,
    ReopeningDisposition,
    ReopeningObligationStatus,
)
from nolane.external_core.goal_design_runtime import DecisionLifecycle, GoalDesignRuntime
from nolane.external_core.goal_design_stress import (
    RecoveryProfile,
    StressWorldEvidence,
    StressWorldKind,
)
from nolane.external_core.goal_design_truth import (
    AssumptionClaim,
    AssumptionEvidence,
    AssumptionPolarity,
    AssumptionStatus,
    AssumptionTruthMaintenance,
)
from nolane.external_core.integration import IntegrationGraph
from nolane.external_core.planning import MasterPlanGraph
from nolane.external_core.requirements import RequirementGraph


def _truth(*, criticality: float = 0.5) -> AssumptionTruthMaintenance:
    truth = AssumptionTruthMaintenance()
    truth.register(
        AssumptionClaim(
            "asm:core",
            "Core design assumption",
            criticality=criticality,
            requirement_refs=("req:core",),
        )
    )
    truth.add_evidence(
        AssumptionEvidence(
            "ev:core:support",
            "asm:core",
            AssumptionPolarity.SUPPORTS,
            0.9,
            "evidence:core:support",
        )
    )
    return truth


def _runtime(truth: AssumptionTruthMaintenance) -> GoalDesignRuntime:
    requirements = SimpleNamespace(graph=RequirementGraph())
    planning = SimpleNamespace(graph=MasterPlanGraph(requirements))
    architecture = SimpleNamespace(graph=ArchitectureGraph())
    integration = SimpleNamespace(graph=IntegrationGraph(), architecture=architecture)
    context = SimpleNamespace(
        max_memories=64,
        max_events=128,
        context_policy_version="policy:sensitivity-reopening",
    )
    return GoalDesignRuntime(
        requirements=requirements,
        planning=planning,
        architecture=architecture,
        integration=integration,
        context=context,
        truth=truth,
    )


def _admit(
    runtime: GoalDesignRuntime,
    *,
    decision_class: DecisionClass = DecisionClass.REVERSIBLE,
    uncertainties=(),
):
    snapshot = runtime.freeze()
    nontrivial = decision_class in {
        DecisionClass.COSTLY_REVERSIBLE,
        DecisionClass.IRREVERSIBLE,
    }
    if nontrivial:
        scenarios = (
            DesignScenario("base", probability=0.7),
            DesignScenario("adverse", probability=0.2, tags=("adversarial",)),
            DesignScenario("tail", probability=0.1, tags=("tail",)),
        )
        selected_utilities = {"base": 0.90, "adverse": 0.84, "tail": 0.80}
        alternative_utilities = {"base": 0.70, "adverse": 0.65, "tail": 0.60}
    else:
        scenarios = (DesignScenario("base"),)
        selected_utilities = {"base": 0.90}
        alternative_utilities = {"base": 0.70}

    options = [
        DesignOption(
            "option:sensitivity-reopening",
            "Sensitivity-aware option",
            selected_utilities,
            {},
            decision_class,
            rollback_ref=(
                "rollback:sensitivity-reopening"
                if decision_class is not DecisionClass.IRREVERSIBLE
                else None
            ),
            assumption_refs=("asm:core",),
        )
    ]
    if nontrivial:
        options.append(
            DesignOption(
                "option:sensitivity-alternative",
                "Explicit reversible alternative",
                alternative_utilities,
                {},
                DecisionClass.REVERSIBLE,
                rollback_ref="rollback:sensitivity-alternative",
                assumption_refs=("asm:core",),
            )
        )

    stress_worlds = ()
    recovery_profiles = ()
    if nontrivial:
        worlds = [
            StressWorldEvidence(
                "world:sensitivity-adverse",
                "adverse",
                StressWorldKind.ADVERSARIAL,
                plausibility=0.6,
                severity=0.8,
                evidence_refs=("evidence:sensitivity-adverse",),
            )
        ]
        if decision_class is DecisionClass.IRREVERSIBLE:
            worlds.append(
                StressWorldEvidence(
                    "world:sensitivity-tail",
                    "tail",
                    StressWorldKind.TAIL,
                    plausibility=0.3,
                    severity=0.9,
                    evidence_refs=("evidence:sensitivity-tail",),
                )
            )
            profile = RecoveryProfile(
                option_id="option:sensitivity-reopening",
                containment_ref="containment:sensitivity-reopening",
                recovery_probability=0.90,
                recovery_cost=0.20,
                recovery_latency=0.10,
                residual_harm=0.15,
                evidence_refs=("evidence:sensitivity-containment",),
            )
        else:
            profile = RecoveryProfile(
                option_id="option:sensitivity-reopening",
                rollback_ref="rollback:sensitivity-reopening",
                recovery_probability=0.90,
                recovery_cost=0.20,
                recovery_latency=0.10,
                residual_harm=0.12,
                evidence_refs=("evidence:sensitivity-rollback",),
            )
        stress_worlds = tuple(worlds)
        recovery_profiles = (profile,)

    return runtime.admit(
        goal=GoalSpec(
            "goal:sensitivity-reopening",
            "Preserve decision validity under material truth change",
            assumption_refs=("asm:core",),
        ),
        scenarios=scenarios,
        options=tuple(options),
        selected_option_id="option:sensitivity-reopening",
        snapshot=snapshot,
        uncertainties=tuple(uncertainties),
        stress_worlds=stress_worlds,
        recovery_profiles=recovery_profiles,
    )


def _register_direct(
    authority: DecisionReopeningAuthority,
    truth: AssumptionTruthMaintenance,
    *,
    receipt_id: str = "decision:direct",
    decision_class: DecisionClass = DecisionClass.REVERSIBLE,
    uncertainties=(),
):
    return authority.register_decision(
        receipt_id=receipt_id,
        decision_class=decision_class,
        truth=truth,
        assumption_ids=("asm:core",),
        uncertainties=tuple(uncertainties),
    )


def test_low_materiality_supported_drift_is_monitored_without_reopening():
    truth = _truth(criticality=0.1)
    authority = DecisionReopeningAuthority()
    _register_direct(authority, truth)

    truth.add_evidence(
        AssumptionEvidence(
            "ev:core:small-support",
            "asm:core",
            AssumptionPolarity.SUPPORTS,
            0.2,
            "evidence:core:small-support",
        )
    )
    assessment = authority.assess_change(
        receipt_id="decision:direct",
        truth=truth,
        affected_assumption_ids=("asm:core",),
    )

    assert assessment.disposition is ReopeningDisposition.NO_REOPEN
    assert assessment.material_assumption_ids == ()
    assert assessment.monitored_assumption_ids == ("asm:core",)
    assert assessment.obligations == ()
    assert authority.open_case("decision:direct") is None


def test_refuted_bound_assumption_always_requires_reopening_and_blocking_proof():
    truth = _truth(criticality=0.05)
    authority = DecisionReopeningAuthority()
    _register_direct(authority, truth)

    truth.retract_evidence("ev:core:support", reason_ref="correction:core")
    truth.add_evidence(
        AssumptionEvidence(
            "ev:core:refute",
            "asm:core",
            AssumptionPolarity.REFUTES,
            0.99,
            "evidence:core:refute",
        )
    )
    assessment = authority.assess_change(
        receipt_id="decision:direct",
        truth=truth,
        affected_assumption_ids=("asm:core",),
    )

    assert assessment.disposition is ReopeningDisposition.REOPEN_REQUIRED
    assert assessment.material_assumption_ids == ("asm:core",)
    assert len(assessment.obligations) == 1
    obligation = assessment.obligations[0]
    assert obligation.status is ReopeningObligationStatus.OPEN
    assert obligation.blocking is True
    assert "asm:core" in obligation.claim
    assert authority.open_case("decision:direct").status is ReopeningCaseStatus.OPEN


def test_irreversible_high_criticality_contestation_reopens_under_lower_threshold():
    truth = _truth(criticality=0.9)
    authority = DecisionReopeningAuthority()
    _register_direct(
        authority,
        truth,
        decision_class=DecisionClass.IRREVERSIBLE,
        uncertainties=(
            UncertaintyItem(
                "unc:core",
                "Outcome remains sensitive to the core assumption",
                uncertainty=0.7,
                impact=0.9,
                decision_sensitivity=0.95,
                observability=0.4,
            ),
        ),
    )

    truth.add_evidence(
        AssumptionEvidence(
            "ev:core:contest",
            "asm:core",
            AssumptionPolarity.REFUTES,
            0.9,
            "evidence:core:contest",
        )
    )
    assessment = authority.assess_change(
        receipt_id="decision:direct",
        truth=truth,
        affected_assumption_ids=("asm:core",),
    )

    assert truth.assessment("asm:core").status is AssumptionStatus.CONTESTED
    assert assessment.disposition is ReopeningDisposition.REOPEN_REQUIRED
    assert assessment.sensitivity_score > assessment.reopening_threshold


def test_resolving_reopening_obligation_never_reactivates_old_truth_bound_receipt():
    truth = _truth()
    authority = DecisionReopeningAuthority()
    baseline = _register_direct(authority, truth)

    truth.retract_evidence("ev:core:support", reason_ref="correction:core")
    truth.add_evidence(
        AssumptionEvidence(
            "ev:core:refute",
            "asm:core",
            AssumptionPolarity.REFUTES,
            0.99,
            "evidence:core:refute",
        )
    )
    assessment = authority.assess_change(
        receipt_id="decision:direct",
        truth=truth,
        affected_assumption_ids=("asm:core",),
    )
    obligation = assessment.obligations[0]
    authority.satisfy_obligation(
        obligation.obligation_id,
        evidence_refs=("evidence:robustness-reanalysis",),
    )

    case = authority.open_case("decision:direct")
    assert case.status is ReopeningCaseStatus.READY_FOR_READMISSION
    assert authority.ready_for_readmission("decision:direct") is True
    assert truth.snapshot(("asm:core",)).digest != baseline.assumption_state_digest
    assert case.requires_new_receipt is True


def test_reopening_obligation_cannot_be_satisfied_without_evidence():
    truth = _truth()
    authority = DecisionReopeningAuthority()
    _register_direct(authority, truth)
    truth.retract_evidence("ev:core:support", reason_ref="correction:core")
    truth.add_evidence(
        AssumptionEvidence(
            "ev:core:refute",
            "asm:core",
            AssumptionPolarity.REFUTES,
            0.99,
            "evidence:core:refute",
        )
    )
    obligation = authority.assess_change(
        receipt_id="decision:direct",
        truth=truth,
        affected_assumption_ids=("asm:core",),
    ).obligations[0]

    with pytest.raises(ValueError, match="evidence"):
        authority.satisfy_obligation(obligation.obligation_id, evidence_refs=())


def test_reopening_state_roundtrip_is_content_addressed_and_tamper_evident():
    truth = _truth()
    authority = DecisionReopeningAuthority()
    _register_direct(authority, truth)
    truth.retract_evidence("ev:core:support", reason_ref="correction:core")
    truth.add_evidence(
        AssumptionEvidence(
            "ev:core:refute",
            "asm:core",
            AssumptionPolarity.REFUTES,
            0.99,
            "evidence:core:refute",
        )
    )
    authority.assess_change(
        receipt_id="decision:direct",
        truth=truth,
        affected_assumption_ids=("asm:core",),
    )

    state = authority.to_state()
    restored = DecisionReopeningAuthority.from_state(state)
    assert restored.to_state() == state
    assert restored.open_case("decision:direct") == authority.open_case("decision:direct")

    tampered = deepcopy(state)
    tampered["cases"][0]["sensitivity_score"] = 0.0
    with pytest.raises(ValueError, match="digest|identity|tamper"):
        DecisionReopeningAuthority.from_state(tampered)


def test_runtime_low_materiality_truth_drift_does_not_stale_decision():
    truth = _truth(criticality=0.1)
    runtime = _runtime(truth)
    receipt = _admit(runtime)

    truth.add_evidence(
        AssumptionEvidence(
            "ev:core:small-support",
            "asm:core",
            AssumptionPolarity.SUPPORTS,
            0.2,
            "evidence:core:small-support",
        )
    )
    impact = runtime.apply_assumption_change(("asm:core",))

    assert impact.invalidated_decision_ids == ()
    assert impact.reviewed_decision_ids == (receipt.receipt_id,)
    assert impact.reopening_case_ids == ()
    assert runtime.decisions.get(receipt.receipt_id).lifecycle is DecisionLifecycle.ACTIVE


def test_runtime_material_refutation_stales_and_exposes_structured_reopening_case():
    truth = _truth()
    runtime = _runtime(truth)
    receipt = _admit(runtime)

    truth.retract_evidence("ev:core:support", reason_ref="correction:core")
    truth.add_evidence(
        AssumptionEvidence(
            "ev:core:refute",
            "asm:core",
            AssumptionPolarity.REFUTES,
            0.99,
            "evidence:core:refute",
        )
    )
    impact = runtime.apply_assumption_change(("asm:core",))

    assert impact.invalidated_decision_ids == (receipt.receipt_id,)
    assert impact.reviewed_decision_ids == (receipt.receipt_id,)
    assert len(impact.reopening_case_ids) == 1
    case = runtime.reopening.open_case(receipt.receipt_id)
    assert case.case_id == impact.reopening_case_ids[0]
    assert case.status is ReopeningCaseStatus.OPEN
    assert runtime.decisions.get(receipt.receipt_id).lifecycle is DecisionLifecycle.STALE


def test_runtime_irreversible_uncertainty_pressure_is_bound_at_admission():
    truth = _truth(criticality=0.9)
    runtime = _runtime(truth)
    receipt = _admit(
        runtime,
        decision_class=DecisionClass.IRREVERSIBLE,
        uncertainties=(
            UncertaintyItem(
                "unc:irreversible",
                "Irreversible outcome depends on contested world state",
                uncertainty=0.75,
                impact=0.9,
                decision_sensitivity=0.95,
                observability=0.4,
                mitigation_ref="mitigation:stress-world",
            ),
        ),
    )
    baseline = runtime.reopening.baseline(receipt.receipt_id)

    assert baseline.decision_class is DecisionClass.IRREVERSIBLE
    assert baseline.uncertainty_pressure > 0.5
    assert baseline.assumption_ids == ("asm:core",)
