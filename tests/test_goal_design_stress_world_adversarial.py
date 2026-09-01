from nolane.external_core.goal_design import (
    DecisionClass,
    DesignOption,
    DesignScenario,
    GoalSpec,
)
from nolane.external_core.goal_design_stress import (
    GoalDesignStressAuthority,
    RecoveryProfile,
    StressWorldEvidence,
    StressWorldKind,
)


def test_competitor_profile_cannot_lowball_structural_reversibility_to_launder_frontier():
    authority = GoalDesignStressAuthority()
    scenarios = (
        DesignScenario("base", probability=0.8),
        DesignScenario("adverse", probability=0.2, tags=("adversarial",)),
    )
    options = (
        DesignOption(
            "costly",
            "Dominated costly path",
            {"base": 0.70, "adverse": 0.62},
            {},
            decision_class=DecisionClass.COSTLY_REVERSIBLE,
            rollback_ref="rollback:costly",
        ),
        DesignOption(
            "safe",
            "Structurally reversible and more robust path",
            {"base": 0.92, "adverse": 0.82},
            {},
            decision_class=DecisionClass.REVERSIBLE,
            rollback_ref="rollback:safe",
        ),
    )
    world = StressWorldEvidence(
        "world:adverse",
        "adverse",
        StressWorldKind.ADVERSARIAL,
        plausibility=0.6,
        severity=0.8,
        evidence_refs=("evidence:adverse",),
    )
    selected_profile = RecoveryProfile(
        option_id="costly",
        rollback_ref="rollback:costly",
        recovery_probability=0.90,
        recovery_cost=0.15,
        recovery_latency=0.10,
        residual_harm=0.10,
        evidence_refs=("evidence:costly-recovery",),
    )
    malicious_lowball = RecoveryProfile(
        option_id="safe",
        rollback_ref="rollback:safe",
        recovery_probability=0.01,
        recovery_cost=0.99,
        recovery_latency=0.99,
        residual_harm=0.99,
        evidence_refs=("evidence:claimed-bad-safe-recovery",),
    )

    token = authority.authorize(
        goal=GoalSpec("goal:anti-lowball", "Do not launder frontier by degrading rivals"),
        scenarios=scenarios,
        options=options,
        selected_option_id="costly",
        worlds=(world,),
        recovery_profiles=(selected_profile, malicious_lowball),
    )

    assert token.authorized is False
    assert "costly" not in token.frontier_option_ids
    assert any("reversibility frontier" in item.lower() for item in token.blockers)
