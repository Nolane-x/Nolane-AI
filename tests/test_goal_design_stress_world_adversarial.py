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
from nolane.external_core.goal_design_stress import (
    GoalDesignStressAuthority,
    RecoveryProfile,
    StressPolicy,
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


def test_zero_materiality_world_cannot_satisfy_required_stress_coverage():
    authority = GoalDesignStressAuthority()
    scenarios = (
        DesignScenario("base", probability=0.8),
        DesignScenario("adverse", probability=0.2, tags=("adversarial",)),
    )
    options = (
        DesignOption(
            "costly",
            "Costly path",
            {"base": 0.92, "adverse": 0.88},
            {},
            decision_class=DecisionClass.COSTLY_REVERSIBLE,
            rollback_ref="rollback:costly",
        ),
        DesignOption(
            "alternative",
            "Reversible alternative",
            {"base": 0.70, "adverse": 0.65},
            {},
            decision_class=DecisionClass.REVERSIBLE,
            rollback_ref="rollback:alternative",
        ),
    )
    decorative_world = StressWorldEvidence(
        "world:decorative",
        "adverse",
        StressWorldKind.ADVERSARIAL,
        plausibility=0.0,
        severity=0.0,
        evidence_refs=("evidence:decorative",),
    )
    recovery = RecoveryProfile(
        option_id="costly",
        rollback_ref="rollback:costly",
        recovery_probability=0.90,
        recovery_cost=0.10,
        recovery_latency=0.10,
        residual_harm=0.10,
        evidence_refs=("evidence:recovery",),
    )

    token = authority.authorize(
        goal=GoalSpec("goal:material-stress", "Require materially non-zero stress"),
        scenarios=scenarios,
        options=options,
        selected_option_id="costly",
        worlds=(decorative_world,),
        recovery_profiles=(recovery,),
    )

    assert token.authorized is False
    assert any("material" in item.lower() for item in token.blockers)


def test_irreversible_tail_world_must_have_independent_evidence_provenance():
    authority = GoalDesignStressAuthority()
    scenarios = (
        DesignScenario("base", probability=0.70),
        DesignScenario("adverse", probability=0.20, tags=("adversarial",)),
        DesignScenario("tail", probability=0.10, tags=("tail",)),
    )
    options = (
        DesignOption(
            "irreversible",
            "High-value irreversible path",
            {"base": 0.95, "adverse": 0.90, "tail": 0.85},
            {},
            decision_class=DecisionClass.IRREVERSIBLE,
        ),
        DesignOption(
            "alternative",
            "Reversible alternative",
            {"base": 0.60, "adverse": 0.60, "tail": 0.60},
            {},
            decision_class=DecisionClass.REVERSIBLE,
            rollback_ref="rollback:alternative",
        ),
    )
    primary = StressWorldEvidence(
        "world:adverse",
        "adverse",
        StressWorldKind.ADVERSARIAL,
        plausibility=0.60,
        severity=0.70,
        evidence_refs=("evidence:shared-provenance",),
    )
    fake_independent_tail = StressWorldEvidence(
        "world:tail",
        "tail",
        StressWorldKind.TAIL,
        plausibility=0.30,
        severity=0.90,
        evidence_refs=("evidence:shared-provenance",),
    )
    recovery = RecoveryProfile(
        option_id="irreversible",
        containment_ref="containment:authority",
        recovery_probability=0.90,
        recovery_cost=0.10,
        recovery_latency=0.10,
        residual_harm=0.10,
        evidence_refs=("evidence:containment",),
    )

    token = authority.authorize(
        goal=GoalSpec("goal:independent-tail", "Require independent tail evidence"),
        scenarios=scenarios,
        options=options,
        selected_option_id="irreversible",
        worlds=(primary, fake_independent_tail),
        recovery_profiles=(recovery,),
    )

    assert token.authorized is False
    assert any("independent" in item.lower() and "provenance" in item.lower() for item in token.blockers)


def test_per_admission_policy_cannot_weaken_default_coherence_authority():
    permissive = StressPolicy(
        costly_max_exposure=1.0,
        costly_min_recovery_score=0.0,
        costly_max_residual_harm=1.0,
        irreversible_max_exposure=1.0,
        irreversible_min_recovery_score=0.0,
        irreversible_max_residual_harm=1.0,
    )
    minting_authority = GoalDesignStressAuthority(default_policy=permissive)
    goal = GoalSpec("goal:policy-authority", "Do not let decisions choose their own risk floor")
    scenarios = (
        DesignScenario("base", probability=0.8),
        DesignScenario("adverse", probability=0.2, tags=("adversarial",)),
    )
    options = (
        DesignOption(
            "costly",
            "High exposure under default policy",
            {"base": 0.99, "adverse": 0.20},
            {},
            decision_class=DecisionClass.COSTLY_REVERSIBLE,
            rollback_ref="rollback:costly",
        ),
        DesignOption(
            "alternative",
            "Low-value reversible alternative",
            {"base": 0.10, "adverse": 0.10},
            {},
            decision_class=DecisionClass.REVERSIBLE,
            rollback_ref="rollback:alternative",
        ),
    )
    world = StressWorldEvidence(
        "world:adverse",
        "adverse",
        StressWorldKind.ADVERSARIAL,
        plausibility=1.0,
        severity=1.0,
        evidence_refs=("evidence:adverse",),
    )
    profile = RecoveryProfile(
        option_id="costly",
        rollback_ref="rollback:costly",
        recovery_probability=0.90,
        recovery_cost=0.10,
        recovery_latency=0.10,
        residual_harm=0.10,
        evidence_refs=("evidence:recovery",),
    )
    token = minting_authority.authorize(
        goal=goal,
        scenarios=scenarios,
        options=options,
        selected_option_id="costly",
        worlds=(world,),
        recovery_profiles=(profile,),
        policy=permissive,
    )
    assert token.authorized is True
    assert token.max_stress_exposure > StressPolicy().costly_max_exposure

    plane = GoalDesignCoherencePlane()
    vector = GoalDesignVersionVector("r:1", "p:1", "a:1", "i:1", "c:1")
    snapshot = plane.freeze_snapshot(vector)
    with pytest.raises(CoherenceError, match="stress|policy"):
        plane.admit_decision(
            goal=goal,
            scenarios=scenarios,
            options=options,
            selected_option_id="costly",
            snapshot=snapshot,
            current_vector=vector,
            stress_token=token,
            stress_worlds=(world,),
            recovery_profiles=(profile,),
            stress_policy=permissive,
        )
