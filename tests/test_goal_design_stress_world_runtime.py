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
from nolane.external_core.goal_design_stress import (
    RecoveryProfile,
    StressWorldEvidence,
    StressWorldKind,
)
from nolane.external_core.integration import IntegrationGraph
from nolane.external_core.planning import MasterPlanGraph
from nolane.external_core.requirements import RequirementGraph


def _runtime() -> GoalDesignRuntime:
    requirements = SimpleNamespace(graph=RequirementGraph())
    planning = SimpleNamespace(graph=MasterPlanGraph(requirements))
    architecture = SimpleNamespace(graph=ArchitectureGraph())
    integration = SimpleNamespace(graph=IntegrationGraph(), architecture=architecture)
    context = SimpleNamespace(
        max_memories=64,
        max_events=128,
        context_policy_version="policy:stress-runtime",
    )
    return GoalDesignRuntime(
        requirements=requirements,
        planning=planning,
        architecture=architecture,
        integration=integration,
        context=context,
    )


def _scenarios():
    return (
        DesignScenario("base", probability=0.8),
        DesignScenario("adverse", probability=0.2, tags=("adversarial",)),
    )


def _options():
    return (
        DesignOption(
            "costly",
            "Costly migration",
            {"base": 0.95, "adverse": 0.82},
            {},
            decision_class=DecisionClass.COSTLY_REVERSIBLE,
            rollback_ref="rollback:costly",
        ),
        DesignOption(
            "safe",
            "Reversible fallback",
            {"base": 0.72, "adverse": 0.68},
            {},
            decision_class=DecisionClass.REVERSIBLE,
            rollback_ref="rollback:safe",
        ),
    )


def _world():
    return StressWorldEvidence(
        "world:adverse",
        "adverse",
        StressWorldKind.ADVERSARIAL,
        plausibility=0.7,
        severity=0.8,
        evidence_refs=("evidence:adverse",),
    )


def _profile():
    return RecoveryProfile(
        option_id="costly",
        rollback_ref="rollback:costly",
        recovery_probability=0.92,
        recovery_cost=0.18,
        recovery_latency=0.12,
        residual_harm=0.10,
        evidence_refs=("evidence:rollback",),
    )


def test_runtime_nontrivial_admission_without_quantified_stress_is_blocked():
    runtime = _runtime()
    snapshot = runtime.freeze()

    with pytest.raises(CoherenceError, match="stress"):
        runtime.admit(
            goal=GoalSpec("goal:runtime-stress", "Require quantified runtime stress"),
            scenarios=_scenarios(),
            options=_options(),
            selected_option_id="costly",
            snapshot=snapshot,
        )


def test_runtime_valid_stress_admission_binds_companion_receipt():
    runtime = _runtime()
    snapshot = runtime.freeze()
    receipt = runtime.admit(
        goal=GoalSpec("goal:runtime-stress", "Require quantified runtime stress"),
        scenarios=_scenarios(),
        options=_options(),
        selected_option_id="costly",
        snapshot=snapshot,
        stress_worlds=(_world(),),
        recovery_profiles=(_profile(),),
    )

    stress_receipt = runtime.stress_receipt(receipt.receipt_id)
    assert stress_receipt is not None
    assert stress_receipt.decision_receipt_id == receipt.receipt_id
    token = runtime.stress_token(receipt.receipt_id)
    assert token is not None
    assert token.authorized is True
    assert stress_receipt.stress_token_id == token.token_id
    assert stress_receipt.stress_token_digest == token.digest


def test_runtime_reversible_admission_preserves_no_stress_companion_path():
    runtime = _runtime()
    snapshot = runtime.freeze()
    safe = _options()[1]
    receipt = runtime.admit(
        goal=GoalSpec("goal:runtime-reversible", "Preserve reversible compatibility"),
        scenarios=_scenarios(),
        options=(safe,),
        selected_option_id="safe",
        snapshot=snapshot,
    )

    assert runtime.stress_receipt(receipt.receipt_id) is None
    assert runtime.stress_token(receipt.receipt_id) is None
