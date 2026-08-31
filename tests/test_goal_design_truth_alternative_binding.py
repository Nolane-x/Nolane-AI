from types import SimpleNamespace

import pytest

from nolane.external_core.architecture import ArchitectureGraph
from nolane.external_core.goal_design import (
    CoherenceError,
    DecisionClass,
    DesignOption,
    DesignScenario,
    GoalSpec,
)
from nolane.external_core.goal_design_runtime import GoalDesignRuntime
from nolane.external_core.goal_design_truth import (
    AssumptionClaim,
    AssumptionEvidence,
    AssumptionPolarity,
    AssumptionTruthMaintenance,
)
from nolane.external_core.integration import IntegrationGraph
from nolane.external_core.planning import MasterPlanGraph
from nolane.external_core.requirements import RequirementGraph


def _supported_truth() -> AssumptionTruthMaintenance:
    truth = AssumptionTruthMaintenance()
    for assumption_id in ("asm:goal", "asm:selected", "asm:alternative"):
        truth.register(AssumptionClaim(assumption_id, f"Claim {assumption_id}"))
        truth.add_evidence(
            AssumptionEvidence(
                f"ev:{assumption_id}",
                assumption_id,
                AssumptionPolarity.SUPPORTS,
                0.9,
                f"evidence:{assumption_id}",
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
        context_policy_version="policy:truth-alternatives",
    )
    return GoalDesignRuntime(
        requirements=requirements,
        planning=planning,
        architecture=architecture,
        integration=integration,
        context=context,
        truth=truth,
    )


def _admit_with_alternative(runtime: GoalDesignRuntime):
    snapshot = runtime.freeze()
    return runtime.admit(
        goal=GoalSpec(
            "goal:all-option-truth",
            "Bind the semantic truth state of the complete evaluated option set",
            assumption_refs=("asm:goal",),
        ),
        scenarios=(DesignScenario("base"),),
        options=(
            DesignOption(
                "option:selected",
                "Selected",
                {"base": 0.9},
                {},
                DecisionClass.REVERSIBLE,
                assumption_refs=("asm:selected",),
            ),
            DesignOption(
                "option:alternative",
                "Alternative",
                {"base": 0.8},
                {},
                DecisionClass.REVERSIBLE,
                assumption_refs=("asm:alternative",),
            ),
        ),
        selected_option_id="option:selected",
        snapshot=snapshot,
    )


def test_receipt_truth_snapshot_binds_goal_and_entire_option_set_assumptions():
    truth = _supported_truth()
    runtime = _runtime(truth)

    receipt = _admit_with_alternative(runtime)

    expected_refs = ("asm:alternative", "asm:goal", "asm:selected")
    assert receipt.assumption_refs == expected_refs
    assert receipt.assumption_state_digest == truth.snapshot(expected_refs).digest


def test_refuted_alternative_assumption_fails_closed_before_robust_evaluation():
    truth = _supported_truth()
    truth.retract_evidence(
        "ev:asm:alternative",
        reason_ref="correction:alternative-support",
    )
    truth.add_evidence(
        AssumptionEvidence(
            "ev:asm:alternative:refute",
            "asm:alternative",
            AssumptionPolarity.REFUTES,
            0.99,
            "evidence:asm:alternative:refute",
        )
    )
    runtime = _runtime(truth)

    with pytest.raises(CoherenceError, match="refuted"):
        _admit_with_alternative(runtime)
