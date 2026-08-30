from dataclasses import replace

import pytest

from nolane.external_core.goal_design import (
    CoherenceError,
    DecisionClass,
    DesignOption,
    DesignScenario,
    GoalDesignCoherencePlane,
    GoalDesignVersionVector,
    GoalObjective,
    GoalSpec,
    ObjectiveDirection,
    PlaneState,
    ProofObligation,
    ProofStatus,
    TraceabilityState,
    UncertaintyItem,
)


def _plane() -> GoalDesignCoherencePlane:
    return GoalDesignCoherencePlane()


def _goal() -> GoalSpec:
    return GoalSpec(
        goal_id="g:design",
        statement="Improve design authority without collapsing specialist autonomy",
        objectives=(
            GoalObjective("quality", ObjectiveDirection.MAXIMIZE, weight=0.6),
            GoalObjective("risk", ObjectiveDirection.MINIMIZE, weight=0.4),
        ),
        success_metrics=("cross_plane_coherence", "decision_reproducibility"),
    )


def _scenarios():
    return (
        DesignScenario("base", probability=0.7, tags=("baseline",)),
        DesignScenario("break", probability=0.3, tags=("counterfactual", "adversarial")),
    )


def _options():
    return (
        DesignOption(
            option_id="safe",
            label="Federated authority",
            utilities={"base": 0.82, "break": 0.70},
            objective_values={"quality": 0.84, "risk": 0.15},
            decision_class=DecisionClass.REVERSIBLE,
            evidence_refs=("ev:1",),
        ),
        DesignOption(
            option_id="dominated",
            label="Weaker clone",
            utilities={"base": 0.72, "break": 0.55},
            objective_values={"quality": 0.70, "risk": 0.30},
            decision_class=DecisionClass.REVERSIBLE,
        ),
    )


def _vector(**overrides):
    base = dict(requirements="req:v3", planning="plan:v4", architecture="arch:v5", integration="int:v2", context="ctx:v7")
    base.update(overrides)
    return GoalDesignVersionVector(**base)


def test_uncertainty_frontier_prioritizes_high_impact_sensitive_unknowns():
    frontier = _plane().uncertainty_frontier(
        [
            UncertaintyItem("u-low", "minor", 0.8, 0.2, 0.2, observability=1.0),
            UncertaintyItem("u-high", "irreversible blast radius", 0.9, 1.0, 1.0, observability=0.0),
        ]
    )
    assert frontier[0].uncertainty_id == "u-high"
    assert frontier[0].risk_score > frontier[1].risk_score


def test_pareto_frontier_preserves_vector_objectives_and_removes_dominated_option():
    ids = {o.option_id for o in _plane().pareto_frontier(_goal(), _options())}
    assert ids == {"safe"}


def test_snapshot_digest_changes_if_any_plane_state_changes():
    plane = _plane()
    a = plane.freeze_snapshot(_vector())
    b = plane.freeze_snapshot(_vector(context="ctx:v8"))
    assert a.digest != b.digest


def test_verify_snapshot_fails_closed_on_stale_plane():
    plane = _plane()
    snapshot = plane.freeze_snapshot(_vector())
    report = plane.verify_snapshot(snapshot, _vector(architecture="arch:v6"))
    assert not report.coherent
    assert any(issue.code == "STALE_ARCHITECTURE" and issue.blocking for issue in report.issues)


def test_coherence_report_flags_active_requirement_without_plan_trace():
    report = _plane().coherence_report(
        TraceabilityState(active_requirement_ids=("r1", "r2"), planned_requirement_ids=("r1",))
    )
    assert not report.coherent
    assert any(issue.code == "UNPLANNED_REQUIREMENT" and issue.subject == "r2" for issue in report.issues)


def test_open_proof_obligation_blocks_decision():
    plane = _plane()
    snapshot = plane.freeze_snapshot(_vector())
    with pytest.raises(CoherenceError, match="proof"):
        plane.admit_decision(
            goal=_goal(), scenarios=_scenarios(), options=_options(), selected_option_id="safe",
            snapshot=snapshot, current_vector=_vector(),
            proof_obligations=(ProofObligation("p1", "prove compatibility", status=ProofStatus.OPEN),),
        )


def test_irreversible_decision_requires_counterfactual_or_adversarial_scenario():
    plane = _plane()
    snapshot = plane.freeze_snapshot(_vector())
    irreversible = DesignOption(
        "irreversible", "One-way migration", {"base": 0.9}, {"quality": 0.9, "risk": 0.1},
        decision_class=DecisionClass.IRREVERSIBLE,
    )
    with pytest.raises(CoherenceError, match="counterfactual"):
        plane.admit_decision(
            goal=_goal(), scenarios=(DesignScenario("base", 1.0),), options=(irreversible, _options()[0]),
            selected_option_id="irreversible", snapshot=snapshot, current_vector=_vector(),
        )


def test_costly_reversible_decision_requires_rollback_reference():
    plane = _plane()
    snapshot = plane.freeze_snapshot(_vector())
    costly = DesignOption(
        "costly", "Migration with expensive rollback", {"base": 0.8, "break": 0.6},
        {"quality": 0.86, "risk": 0.22}, decision_class=DecisionClass.COSTLY_REVERSIBLE,
    )
    with pytest.raises(CoherenceError, match="rollback"):
        plane.admit_decision(
            goal=_goal(), scenarios=_scenarios(), options=(costly, _options()[0]), selected_option_id="costly",
            snapshot=snapshot, current_vector=_vector(),
        )


def test_irreversible_high_risk_uncertainty_blocks_until_resolved():
    plane = _plane()
    snapshot = plane.freeze_snapshot(_vector())
    irreversible = DesignOption(
        "irr", "Delete compatibility layer", {"base": 0.92, "break": 0.35},
        {"quality": 0.95, "risk": 0.4}, decision_class=DecisionClass.IRREVERSIBLE,
    )
    with pytest.raises(CoherenceError, match="uncertainty"):
        plane.admit_decision(
            goal=_goal(), scenarios=_scenarios(), options=(irreversible, _options()[0]), selected_option_id="irr",
            snapshot=snapshot, current_vector=_vector(),
            uncertainties=(UncertaintyItem("u1", "unknown downstream dependency", 0.95, 1.0, 1.0, observability=0.0),),
        )


def test_decision_receipt_is_content_addressed_and_repeatable():
    plane = _plane()
    snapshot = plane.freeze_snapshot(_vector())
    kwargs = dict(
        goal=_goal(), scenarios=_scenarios(), options=_options(), selected_option_id="safe",
        snapshot=snapshot, current_vector=_vector(),
        proof_obligations=(ProofObligation("p1", "compatibility checked", status=ProofStatus.SATISFIED, evidence_refs=("ev:test",)),),
    )
    first = plane.admit_decision(**kwargs)
    second = plane.admit_decision(**kwargs)
    assert first.receipt_id == second.receipt_id
    assert first.snapshot_digest == snapshot.digest
    assert first.evaluation_digest == second.evaluation_digest
