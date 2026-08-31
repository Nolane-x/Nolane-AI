from dataclasses import replace
from types import SimpleNamespace

import pytest

from nolane.external_core.architecture import ArchitectureGraph
from nolane.external_core.goal_design import (
    CoherenceError,
    DecisionClass,
    DesignOption,
    DesignScenario,
    GoalDesignCoherencePlane,
    GoalDesignVersionVector,
    GoalSpec,
)
from nolane.external_core.goal_design_authenticity import (
    decision_event_payload,
    verify_decision_receipt,
)
from nolane.external_core.goal_design_ledger import AuthorityLevel, EventKind
from nolane.external_core.goal_design_runtime import (
    DecisionAuthorityIndex,
    DecisionLifecycle,
    GoalDesignRuntime,
)
from nolane.external_core.goal_design_truth import (
    AssumptionClaim,
    AssumptionEvidence,
    AssumptionPolarity,
    AssumptionTruthMaintenance,
)
from nolane.external_core.integration import IntegrationGraph
from nolane.external_core.planning import MasterPlanGraph
from nolane.external_core.requirements import RequirementGraph


def _truth(*, dependency: bool = False) -> AssumptionTruthMaintenance:
    truth = AssumptionTruthMaintenance()
    if dependency:
        truth.register(AssumptionClaim("asm:base", "Foundation assumption"))
        truth.register(
            AssumptionClaim(
                "asm:core",
                "Core assumption",
                depends_on=("asm:base",),
            )
        )
        truth.add_evidence(
            AssumptionEvidence(
                "ev:base:support",
                "asm:base",
                AssumptionPolarity.SUPPORTS,
                0.9,
                "evidence:base:support",
            )
        )
    else:
        truth.register(AssumptionClaim("asm:core", "Core assumption"))
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


def _runtime(truth: AssumptionTruthMaintenance | None = None) -> GoalDesignRuntime:
    requirements = SimpleNamespace(graph=RequirementGraph())
    planning = SimpleNamespace(graph=MasterPlanGraph(requirements))
    architecture = SimpleNamespace(graph=ArchitectureGraph())
    integration = SimpleNamespace(graph=IntegrationGraph(), architecture=architecture)
    context = SimpleNamespace(
        max_memories=64,
        max_events=128,
        context_policy_version="policy:truth-test",
    )
    return GoalDesignRuntime(
        requirements=requirements,
        planning=planning,
        architecture=architecture,
        integration=integration,
        context=context,
        truth=truth,
    )


def _admit_truth_bound(
    runtime: GoalDesignRuntime,
    *,
    assumption_refs: tuple[str, ...] = ("asm:core",),
):
    snapshot = runtime.freeze()
    return runtime.admit(
        goal=GoalSpec(
            "goal:truth-runtime",
            "Keep decisions synchronized with assumption truth",
            assumption_refs=assumption_refs,
        ),
        scenarios=(DesignScenario("base"),),
        options=(
            DesignOption(
                "option:truth-runtime",
                "Truth-aware option",
                {"base": 0.9},
                {},
                DecisionClass.REVERSIBLE,
                assumption_refs=assumption_refs,
            ),
        ),
        selected_option_id="option:truth-runtime",
        snapshot=snapshot,
    )


def test_runtime_admission_mints_v3_and_indexes_exact_assumption_dependencies():
    runtime = _runtime(_truth())
    receipt = _admit_truth_bound(runtime)

    assert verify_decision_receipt(receipt) == "v3"
    assert receipt.assumption_refs == ("asm:core",)
    assert receipt.assumption_state_digest == runtime.truth.snapshot(("asm:core",)).digest
    assert runtime.decisions.affected_by_assumptions(("asm:core",)) == (receipt.receipt_id,)

    record = runtime.decisions.get(receipt.receipt_id)
    event = runtime.ledger.get(record.authority_event_id)
    assert event.authority_level is AuthorityLevel.AUTHORITY
    assert event.kind is EventKind.DECISION
    assert "asm:core" in event.subject_refs
    payload = decision_event_payload(receipt)
    assert payload["assumption_state_digest"] == receipt.assumption_state_digest
    assert payload["assumption_refs"] == ["asm:core"]


def test_runtime_fails_closed_when_truth_bound_goal_has_no_truth_authority():
    runtime = _runtime(None)
    with pytest.raises(CoherenceError, match="truth authority"):
        _admit_truth_bound(runtime)


def test_runtime_applies_truth_policy_before_admitting_even_reversible_refuted_decision():
    truth = _truth()
    truth.retract_evidence(
        "ev:core:support",
        reason_ref="correction:core-support",
    )
    truth.add_evidence(
        AssumptionEvidence(
            "ev:core:refute",
            "asm:core",
            AssumptionPolarity.REFUTES,
            0.99,
            "evidence:core:refute",
        )
    )
    runtime = _runtime(truth)
    with pytest.raises(CoherenceError, match="refuted"):
        _admit_truth_bound(runtime)


def test_assumption_change_stales_bound_decision_and_mints_causal_authority_events():
    truth = _truth()
    runtime = _runtime(truth)
    receipt = _admit_truth_bound(runtime)
    decision_event_id = runtime.decisions.get(receipt.receipt_id).authority_event_id

    truth.add_evidence(
        AssumptionEvidence(
            "ev:core:refute",
            "asm:core",
            AssumptionPolarity.REFUTES,
            0.95,
            "evidence:core:refute",
        )
    )
    impact = runtime.apply_assumption_change(("asm:core",))

    assert impact.invalidated_decision_ids == (receipt.receipt_id,)
    assert impact.changed_assumption_ids == ("asm:core",)
    assert runtime.decisions.get(receipt.receipt_id).lifecycle is DecisionLifecycle.STALE

    truth_event = runtime.ledger.get(impact.authority_event_id)
    assert truth_event.kind is EventKind.ASSUMPTION_CHANGE
    assert truth_event.authority_level is AuthorityLevel.AUTHORITY
    assert "asm:core" in truth_event.subject_refs

    invalidation = runtime.ledger.events[-1]
    assert invalidation.kind is EventKind.INVALIDATION
    assert decision_event_id in invalidation.parent_ids
    assert truth_event.event_id in invalidation.parent_ids


def test_transitive_dependency_change_stales_decision_bound_only_to_derived_assumption():
    truth = _truth(dependency=True)
    runtime = _runtime(truth)
    receipt = _admit_truth_bound(runtime, assumption_refs=("asm:core",))

    truth.add_evidence(
        AssumptionEvidence(
            "ev:base:refute",
            "asm:base",
            AssumptionPolarity.REFUTES,
            0.98,
            "evidence:base:refute",
        )
    )
    impact = runtime.apply_assumption_change(("asm:base",))

    assert "asm:core" in impact.affected_assumption_ids
    assert impact.invalidated_decision_ids == (receipt.receipt_id,)
    assert runtime.decisions.get(receipt.receipt_id).lifecycle is DecisionLifecycle.STALE


def test_unrelated_truth_change_does_not_create_false_decision_invalidation():
    truth = _truth()
    truth.register(AssumptionClaim("asm:unrelated", "Unrelated assumption"))
    runtime = _runtime(truth)
    receipt = _admit_truth_bound(runtime)

    truth.add_evidence(
        AssumptionEvidence(
            "ev:unrelated:support",
            "asm:unrelated",
            AssumptionPolarity.SUPPORTS,
            0.9,
            "evidence:unrelated:support",
        )
    )
    impact = runtime.apply_assumption_change(("asm:unrelated",))

    assert impact.invalidated_decision_ids == ()
    assert runtime.decisions.get(receipt.receipt_id).lifecycle is DecisionLifecycle.ACTIVE


def test_v2_decision_is_not_retroactively_bound_to_truth_authority():
    truth = _truth()
    runtime = _runtime(truth)
    snapshot = runtime.freeze()
    receipt = runtime.admit(
        goal=GoalSpec("goal:v2-runtime", "Remain historical v2"),
        scenarios=(DesignScenario("base"),),
        options=(DesignOption("option:v2-runtime", "v2", {"base": 0.8}, {}),),
        selected_option_id="option:v2-runtime",
        snapshot=snapshot,
    )
    assert verify_decision_receipt(receipt) == "v2"

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
    assert impact.invalidated_decision_ids == ()
    assert runtime.decisions.get(receipt.receipt_id).lifecycle is DecisionLifecycle.ACTIVE


def test_decision_index_persistence_roundtrip_preserves_v3_truth_binding_and_lookup():
    runtime = _runtime(_truth())
    receipt = _admit_truth_bound(runtime)

    state = runtime.decisions.to_state()
    restored = DecisionAuthorityIndex.from_state(state)

    restored_receipt = restored.get(receipt.receipt_id).receipt
    assert restored_receipt.assumption_refs == ("asm:core",)
    assert restored_receipt.assumption_state_digest == receipt.assumption_state_digest
    assert restored.affected_by_assumptions(("asm:core",)) == (receipt.receipt_id,)
    assert verify_decision_receipt(restored_receipt) == "v3"


def test_partial_v3_manifest_is_rejected_fail_closed_without_changing_v2_identity_rules():
    plane = GoalDesignCoherencePlane()
    vector = GoalDesignVersionVector("r1", "p1", "a1", "i1", "c1")
    snapshot = plane.freeze_snapshot(vector)

    with pytest.raises(CoherenceError, match="assumption"):
        plane.admit_decision(
            goal=GoalSpec("goal:refs-only", "refs without truth digest", assumption_refs=("asm:core",)),
            scenarios=(DesignScenario("base"),),
            options=(DesignOption("option:refs-only", "refs", {"base": 0.8}, {}),),
            selected_option_id="option:refs-only",
            snapshot=snapshot,
            current_vector=vector,
        )

    with pytest.raises(CoherenceError, match="assumption"):
        plane.admit_decision(
            goal=GoalSpec("goal:digest-only", "digest without refs"),
            scenarios=(DesignScenario("base"),),
            options=(DesignOption("option:digest-only", "digest", {"base": 0.8}, {}),),
            selected_option_id="option:digest-only",
            snapshot=snapshot,
            current_vector=vector,
            assumption_state_digest="truth:digest-without-refs",
        )


def test_tampered_v3_assumption_binding_cannot_be_restored_into_authority_index():
    runtime = _runtime(_truth())
    receipt = _admit_truth_bound(runtime)
    forged = replace(receipt, assumption_refs=("asm:other",))

    index = DecisionAuthorityIndex()
    with pytest.raises(ValueError, match="identity digest mismatch"):
        index.register(forged)
