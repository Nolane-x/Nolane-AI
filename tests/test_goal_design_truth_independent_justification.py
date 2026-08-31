import copy

import pytest

from nolane.external_core.goal_design import DecisionClass
from nolane.external_core.goal_design_truth import (
    AssumptionClaim,
    AssumptionEvidence,
    AssumptionJustification,
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


def _evidence(
    evidence_id: str,
    assumption_id: str,
    polarity: AssumptionPolarity,
    confidence: float = 0.95,
) -> AssumptionEvidence:
    return AssumptionEvidence(
        evidence_id=evidence_id,
        assumption_id=assumption_id,
        polarity=polarity,
        confidence=confidence,
        evidence_ref=f"evidence:{evidence_id}",
    )


def _support(truth: AssumptionTruthMaintenance, assumption_id: str) -> None:
    truth.add_evidence(
        _evidence(f"ev:{assumption_id}:support", assumption_id, AssumptionPolarity.SUPPORTS)
    )


def _refute(truth: AssumptionTruthMaintenance, assumption_id: str) -> None:
    support_id = f"ev:{assumption_id}:support"
    try:
        truth.retract_evidence(
            support_id,
            reason_ref=f"correction:{assumption_id}:support",
        )
    except ValueError:
        pass
    truth.add_evidence(
        _evidence(f"ev:{assumption_id}:refute", assumption_id, AssumptionPolarity.REFUTES)
    )


def _route(
    justification_id: str,
    assumption_id: str,
    *premise_refs: str,
) -> AssumptionJustification:
    return AssumptionJustification(
        justification_id=justification_id,
        assumption_id=assumption_id,
        premise_refs=tuple(premise_refs),
        provenance_ref=f"argument:{justification_id}",
    )


def test_independent_justification_survives_failure_of_one_route():
    truth = AssumptionTruthMaintenance()
    for assumption_id in ("asm:a", "asm:b", "asm:x", "asm:y", "asm:derived"):
        truth.register(_claim(assumption_id))
        _support(truth, assumption_id)

    truth.add_justification(_route("just:ab", "asm:derived", "asm:a", "asm:b"))
    truth.add_justification(_route("just:xy", "asm:derived", "asm:x", "asm:y"))
    assert truth.assessment("asm:derived").status is AssumptionStatus.SUPPORTED

    _refute(truth, "asm:a")
    assessment = truth.assessment("asm:derived")

    assert assessment.status is AssumptionStatus.SUPPORTED
    assert assessment.dependency_blockers == ()
    assert assessment.surviving_justification_ids == ("just:xy",)
    assert assessment.failed_justification_ids == ("just:ab",)
    assert truth.decision_blockers(("asm:derived",), DecisionClass.IRREVERSIBLE) == ()


def test_claim_retracts_only_after_every_independent_route_loses_support():
    truth = AssumptionTruthMaintenance()
    for assumption_id in ("asm:a", "asm:x", "asm:derived"):
        truth.register(_claim(assumption_id))
        _support(truth, assumption_id)
    truth.add_justification(_route("just:a", "asm:derived", "asm:a"))
    truth.add_justification(_route("just:x", "asm:derived", "asm:x"))

    _refute(truth, "asm:a")
    assert truth.assessment("asm:derived").status is AssumptionStatus.SUPPORTED

    _refute(truth, "asm:x")
    assessment = truth.assessment("asm:derived")
    assert assessment.status is AssumptionStatus.REFUTED
    assert assessment.surviving_justification_ids == ()
    assert assessment.failed_justification_ids == ("just:a", "just:x")
    assert truth.decision_blockers(("asm:derived",), DecisionClass.REVERSIBLE)


def test_legacy_depends_on_remains_one_conjunctive_justification_route():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:a"))
    truth.register(_claim("asm:b"))
    truth.register(_claim("asm:derived", depends_on=("asm:a", "asm:b")))
    for assumption_id in ("asm:a", "asm:b", "asm:derived"):
        _support(truth, assumption_id)

    assert truth.assessment("asm:derived").status is AssumptionStatus.SUPPORTED
    _refute(truth, "asm:a")
    assessment = truth.assessment("asm:derived")
    assert assessment.status is AssumptionStatus.REFUTED
    assert assessment.dependency_blockers == ("asm:a",)


def test_explicit_justification_can_rescue_legacy_dependency_route():
    truth = AssumptionTruthMaintenance()
    for assumption_id in ("asm:legacy", "asm:alternate", "asm:derived"):
        truth.register(_claim(assumption_id))
        _support(truth, assumption_id)
    truth.register(_claim("asm:with-legacy", depends_on=("asm:legacy",)))
    _support(truth, "asm:with-legacy")
    truth.add_justification(
        _route("just:alternate", "asm:with-legacy", "asm:alternate")
    )

    _refute(truth, "asm:legacy")
    assessment = truth.assessment("asm:with-legacy")
    assert assessment.status is AssumptionStatus.SUPPORTED
    assert assessment.dependency_blockers == ()
    assert assessment.surviving_justification_ids == ("just:alternate",)


def test_snapshot_closure_and_digest_bind_every_independent_route():
    truth = AssumptionTruthMaintenance()
    for assumption_id in ("asm:a", "asm:x", "asm:derived"):
        truth.register(_claim(assumption_id))
        _support(truth, assumption_id)
    truth.add_justification(_route("just:a", "asm:derived", "asm:a"))

    first = truth.snapshot(("asm:derived",))
    assert first.assumption_ids == ("asm:a", "asm:derived")

    truth.add_justification(_route("just:x", "asm:derived", "asm:x"))
    second = truth.snapshot(("asm:derived",))
    assert second.assumption_ids == ("asm:a", "asm:derived", "asm:x")
    assert second.digest != first.digest


def test_change_impact_traverses_explicit_justification_edges():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:base"))
    truth.register(_claim("asm:derived", plan_refs=("plan:derived",)))
    truth.add_justification(_route("just:base", "asm:derived", "asm:base"))

    impact = truth.analyze_change(("asm:base",))
    assert impact.affected_assumption_ids == ("asm:base", "asm:derived")
    assert impact.plan_refs == ("plan:derived",)


def test_justification_persistence_roundtrip_and_tamper_detection():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:base"))
    truth.register(_claim("asm:derived"))
    truth.add_justification(_route("just:base", "asm:derived", "asm:base"))

    state = truth.to_state()
    restored = AssumptionTruthMaintenance.from_state(state)
    assert restored.to_state() == state
    assert restored.digest == truth.digest

    tampered = copy.deepcopy(state)
    tampered["justifications"][0]["premise_refs"] = ["asm:forged"]
    with pytest.raises(ValueError, match="justification.*digest|digest.*justification"):
        AssumptionTruthMaintenance.from_state(tampered)


def test_justification_graph_rejects_unknown_premises_cycles_and_identity_rebinding():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:a"))
    truth.register(_claim("asm:b"))
    truth.add_justification(_route("just:a", "asm:a", "asm:missing"))
    with pytest.raises(ValueError, match="unknown"):
        truth.snapshot(("asm:a",))

    cyclic = AssumptionTruthMaintenance()
    cyclic.register(_claim("asm:a"))
    cyclic.register(_claim("asm:b"))
    cyclic.add_justification(_route("just:a", "asm:a", "asm:b"))
    cyclic.add_justification(_route("just:b", "asm:b", "asm:a"))
    with pytest.raises(ValueError, match="cycle"):
        cyclic.snapshot(("asm:a",))

    rebound = AssumptionTruthMaintenance()
    rebound.register(_claim("asm:a"))
    rebound.register(_claim("asm:b"))
    rebound.add_justification(_route("just:stable", "asm:a", "asm:b"))
    with pytest.raises(ValueError, match="cannot be rebound"):
        rebound.add_justification(_route("just:stable", "asm:b", "asm:a"))


def test_direct_refutation_dominates_even_when_an_independent_route_survives():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:base"))
    truth.register(_claim("asm:derived"))
    _support(truth, "asm:base")
    _support(truth, "asm:derived")
    truth.add_justification(_route("just:base", "asm:derived", "asm:base"))
    assert truth.assessment("asm:derived").status is AssumptionStatus.SUPPORTED

    _refute(truth, "asm:derived")
    assessment = truth.assessment("asm:derived")
    assert assessment.surviving_justification_ids == ("just:base",)
    assert assessment.status is AssumptionStatus.REFUTED


def test_no_surviving_route_never_upgrades_unknown_dependency_state_to_supported():
    truth = AssumptionTruthMaintenance()
    for assumption_id in ("asm:unknown", "asm:refuted", "asm:derived"):
        truth.register(_claim(assumption_id))
    _support(truth, "asm:derived")
    _refute(truth, "asm:refuted")
    truth.add_justification(_route("just:unknown", "asm:derived", "asm:unknown"))
    truth.add_justification(_route("just:refuted", "asm:derived", "asm:refuted"))

    assessment = truth.assessment("asm:derived")
    assert assessment.status is AssumptionStatus.UNKNOWN
    assert assessment.surviving_justification_ids == ()
    assert assessment.failed_justification_ids == ("just:refuted",)
    assert assessment.unsettled_justification_ids == ("just:unknown",)


def test_schema_v1_state_migrates_without_rewriting_legacy_snapshot_semantics():
    truth = AssumptionTruthMaintenance()
    truth.register(_claim("asm:base"))
    truth.register(_claim("asm:derived", depends_on=("asm:base",)))
    _support(truth, "asm:base")
    _support(truth, "asm:derived")
    before = truth.snapshot(("asm:derived",))

    legacy_state = truth.to_state()
    legacy_state["schema_version"] = 1
    legacy_state.pop("justifications")
    restored = AssumptionTruthMaintenance.from_state(legacy_state)

    after = restored.snapshot(("asm:derived",))
    assert after == before
    assert restored.to_state()["schema_version"] == 2
    assert restored.to_state()["justifications"] == []
