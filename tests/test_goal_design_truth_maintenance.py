from dataclasses import replace

import pytest

from nolane.external_core.goal_design import (
    CoherenceError,
    DecisionClass,
    DesignOption,
    DesignScenario,
    GoalDesignCoherencePlane,
    GoalDesignVersionVector,
    GoalSpec,
)
from nolane.external_core.goal_design_authenticity import verify_decision_receipt
from nolane.external_core.goal_design_truth import (
    AssumptionClaim,
    AssumptionEvidence,
    AssumptionPolarity,
    AssumptionStatus,
    AssumptionTruthMaintenance,
)


def _claim(assumption_id: str, **kwargs) -> AssumptionClaim:
    return AssumptionClaim(
        assumption_id=assumption_id,
        statement=kwargs.pop("statement", f"Claim {assumption_id}"),
        **kwargs,
    )


def _evidence(evidence_id: str, assumption_id: str, polarity: AssumptionPolarity, confidence: float) -> AssumptionEvidence:
    return AssumptionEvidence(
        evidence_id=evidence_id,
        assumption_id=assumption_id,
        polarity=polarity,
        confidence=confidence,
        evidence_ref=f"evidence:{evidence_id}",
    )


def test_truth_status_aggregates_independent_support_and_refutation_evidence():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:core"))
    truth.add_evidence(_evidence("support:1", "asm:core", AssumptionPolarity.SUPPORTS, 0.8))
    assert truth.assessment("asm:core").status is AssumptionStatus.SUPPORTED

    truth.add_evidence(_evidence("refute:1", "asm:core", AssumptionPolarity.REFUTES, 0.8))
    assessment = truth.assessment("asm:core")
    assert assessment.status is AssumptionStatus.CONTESTED
    assert assessment.support_score == pytest.approx(0.8)
    assert assessment.refute_score == pytest.approx(0.8)


def test_dependency_refutation_propagates_without_rewriting_dependent_evidence():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:foundation"))
    truth.register(_claim("asm:derived", depends_on=("asm:foundation",)))
    truth.add_evidence(_evidence("foundation:refute", "asm:foundation", AssumptionPolarity.REFUTES, 0.95))
    truth.add_evidence(_evidence("derived:support", "asm:derived", AssumptionPolarity.SUPPORTS, 0.95))

    assessment = truth.assessment("asm:derived")
    assert assessment.direct_status is AssumptionStatus.SUPPORTED
    assert assessment.status is AssumptionStatus.REFUTED
    assert assessment.dependency_blockers == ("asm:foundation",)


def test_retracting_evidence_changes_truth_without_deleting_history():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:retract"))
    truth.add_evidence(_evidence("ev:bad", "asm:retract", AssumptionPolarity.REFUTES, 0.9))
    before = truth.snapshot(("asm:retract",))
    assert truth.assessment("asm:retract").status is AssumptionStatus.REFUTED

    truth.retract_evidence("ev:bad", reason_ref="correction:ev-bad")
    after = truth.snapshot(("asm:retract",))
    assert truth.assessment("asm:retract").status is AssumptionStatus.UNKNOWN
    assert before.digest != after.digest
    state = truth.to_state()
    assert len(state["evidence"]) == 1
    assert len(state["retractions"]) == 1


def test_snapshot_binds_transitive_dependencies_and_evidence_state():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:base"))
    truth.register(_claim("asm:top", depends_on=("asm:base",)))
    truth.add_evidence(_evidence("base:support", "asm:base", AssumptionPolarity.SUPPORTS, 0.8))
    truth.add_evidence(_evidence("top:support", "asm:top", AssumptionPolarity.SUPPORTS, 0.8))

    first = truth.snapshot(("asm:top",))
    second = truth.snapshot(("asm:top",))
    assert first == second
    assert first.assumption_ids == ("asm:base", "asm:top")

    truth.add_evidence(_evidence("top:support:2", "asm:top", AssumptionPolarity.SUPPORTS, 0.2))
    assert truth.snapshot(("asm:top",)).digest != first.digest


def test_change_impact_propagates_through_assumption_graph_to_bound_design_refs():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:base", requirement_refs=("req:base",)))
    truth.register(
        _claim(
            "asm:derived",
            depends_on=("asm:base",),
            plan_refs=("plan:derived",),
            component_refs=("cmp:derived",),
            integration_candidate_refs=("cand:derived",),
        )
    )

    report = truth.analyze_change(("asm:base",))
    assert report.changed_assumption_ids == ("asm:base",)
    assert report.affected_assumption_ids == ("asm:base", "asm:derived")
    assert report.requirement_refs == ("req:base",)
    assert report.plan_refs == ("plan:derived",)
    assert report.component_refs == ("cmp:derived",)
    assert report.integration_candidate_refs == ("cand:derived",)
    assert report.digest


def test_decision_policy_is_reversibility_sensitive_and_fail_closed_on_refutation():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:critical", criticality=0.9))

    assert truth.decision_blockers(("asm:critical",), DecisionClass.REVERSIBLE) == ()
    assert truth.decision_blockers(("asm:critical",), DecisionClass.COSTLY_REVERSIBLE)
    assert truth.decision_blockers(("asm:critical",), DecisionClass.IRREVERSIBLE)

    truth.add_evidence(_evidence("critical:support", "asm:critical", AssumptionPolarity.SUPPORTS, 0.9))
    assert truth.decision_blockers(("asm:critical",), DecisionClass.IRREVERSIBLE) == ()

    truth.add_evidence(_evidence("critical:refute", "asm:critical", AssumptionPolarity.REFUTES, 0.99))
    blockers = truth.decision_blockers(("asm:critical",), DecisionClass.REVERSIBLE)
    assert blockers and "refuted" in blockers[0].lower()


def test_persistence_roundtrip_preserves_truth_digest_and_retractions():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:persist"))
    truth.add_evidence(_evidence("persist:support", "asm:persist", AssumptionPolarity.SUPPORTS, 0.85))
    truth.retract_evidence("persist:support", reason_ref="correction:persist")

    state = truth.to_state()
    restored = AssumptionTruthMaintenance.from_state(state)
    assert restored.to_state() == state
    assert restored.digest == truth.digest
    assert restored.assessment("asm:persist").status is AssumptionStatus.UNKNOWN


def test_persistence_rejects_tampered_claim_or_evidence_content():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:tamper"))
    truth.add_evidence(_evidence("tamper:support", "asm:tamper", AssumptionPolarity.SUPPORTS, 0.8))

    state = truth.to_state()
    state["claims"][0]["statement"] = "forged statement"
    with pytest.raises(ValueError, match="digest"):
        AssumptionTruthMaintenance.from_state(state)

    state = truth.to_state()
    state["evidence"][0]["confidence"] = 0.01
    with pytest.raises(ValueError, match="digest"):
        AssumptionTruthMaintenance.from_state(state)


def test_snapshot_rejects_unknown_dependencies_and_cycles_fail_closed():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:orphan", depends_on=("asm:missing",)))
    with pytest.raises(ValueError, match="unknown"):
        truth.snapshot(("asm:orphan",))

    cyclic = AssumptionTruthMaintenance()
    cyclic.register(_claim("asm:a", depends_on=("asm:b",)))
    cyclic.register(_claim("asm:b", depends_on=("asm:a",)))
    with pytest.raises(ValueError, match="cycle"):
        cyclic.snapshot(("asm:a",))


def test_receipt_v3_binds_assumption_truth_snapshot_into_authority_identity():
    plane = GoalDesignCoherencePlane()
    vector = GoalDesignVersionVector("r1", "p1", "a1", "i1", "c1")
    snapshot = plane.freeze_snapshot(vector)
    goal = GoalSpec("goal:truth", "Bind assumption truth", assumption_refs=("asm:core",))
    scenario = DesignScenario("base")
    option = DesignOption(
        "option:truth",
        "Truth-bound option",
        {"base": 0.9},
        {},
        DecisionClass.REVERSIBLE,
        assumption_refs=("asm:core",),
    )

    receipt = plane.admit_decision(
        goal=goal,
        scenarios=(scenario,),
        options=(option,),
        selected_option_id=option.option_id,
        snapshot=snapshot,
        current_vector=vector,
        assumption_state_digest="assumption-snapshot:abc",
    )
    assert receipt.assumption_state_digest == "assumption-snapshot:abc"
    assert verify_decision_receipt(receipt) == "v3"

    forged = replace(receipt, assumption_state_digest="assumption-snapshot:forged")
    with pytest.raises(ValueError, match="identity digest mismatch"):
        verify_decision_receipt(forged)


def test_receipt_v2_without_assumption_truth_remains_compatible():
    plane = GoalDesignCoherencePlane()
    vector = GoalDesignVersionVector("r1", "p1", "a1", "i1", "c1")
    snapshot = plane.freeze_snapshot(vector)
    receipt = plane.admit_decision(
        goal=GoalSpec("goal:v2", "Legacy manifest decision"),
        scenarios=(DesignScenario("base"),),
        options=(DesignOption("option:v2", "v2", {"base": 0.7}, {}),),
        selected_option_id="option:v2",
        snapshot=snapshot,
        current_vector=vector,
    )
    assert receipt.assumption_state_digest == ""
    assert verify_decision_receipt(receipt) == "v2"
