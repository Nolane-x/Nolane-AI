from dataclasses import replace

import pytest

from nolane.external_core.goal_design import (
    DecisionClass,
    DesignOption,
    DesignScenario,
    GoalSpec,
)
from nolane.external_core.goal_design_stress import (
    GoalDesignStressAuthority,
    RecoveryProfile,
    StressPolicy,
    StressWorldEvidence,
    StressWorldKind,
)


def _goal():
    return GoalSpec("goal:stress", "Keep non-trivial decisions robust under stress")


def _scenarios():
    return (
        DesignScenario("base", probability=0.70),
        DesignScenario("adverse", probability=0.20, tags=("adversarial",)),
        DesignScenario("tail", probability=0.10, tags=("tail",)),
    )


def _costly_options():
    return (
        DesignOption(
            "costly",
            "Higher-value migration with an expensive exit",
            {"base": 0.95, "adverse": 0.80, "tail": 0.75},
            {},
            decision_class=DecisionClass.COSTLY_REVERSIBLE,
            rollback_ref="rollback:costly",
        ),
        DesignOption(
            "safe",
            "Lower-value reversible alternative",
            {"base": 0.76, "adverse": 0.70, "tail": 0.68},
            {},
            decision_class=DecisionClass.REVERSIBLE,
            rollback_ref="rollback:safe",
        ),
    )


def _irreversible_options():
    return (
        DesignOption(
            "irreversible",
            "One-way architecture cutover",
            {"base": 0.98, "adverse": 0.82, "tail": 0.72},
            {},
            decision_class=DecisionClass.IRREVERSIBLE,
        ),
        DesignOption(
            "safe",
            "Lower-value reversible alternative",
            {"base": 0.70, "adverse": 0.64, "tail": 0.58},
            {},
            decision_class=DecisionClass.REVERSIBLE,
            rollback_ref="rollback:safe",
        ),
    )


def _challenge_world():
    return StressWorldEvidence(
        "world:adverse",
        "adverse",
        StressWorldKind.ADVERSARIAL,
        plausibility=0.70,
        severity=0.80,
        evidence_refs=("evidence:adverse",),
    )


def _tail_world():
    return StressWorldEvidence(
        "world:tail",
        "tail",
        StressWorldKind.TAIL,
        plausibility=0.35,
        severity=0.95,
        evidence_refs=("evidence:tail",),
    )


def _costly_profile():
    return RecoveryProfile(
        option_id="costly",
        rollback_ref="rollback:costly",
        recovery_probability=0.90,
        recovery_cost=0.20,
        recovery_latency=0.10,
        residual_harm=0.10,
        evidence_refs=("evidence:rollback",),
    )


def _containment_profile():
    return RecoveryProfile(
        option_id="irreversible",
        containment_ref="containment:irreversible",
        recovery_probability=0.92,
        recovery_cost=0.25,
        recovery_latency=0.15,
        residual_harm=0.18,
        evidence_refs=("evidence:containment",),
    )


def test_costly_authority_requires_evidence_bearing_challenge_world():
    authority = GoalDesignStressAuthority()
    token = authority.authorize(
        goal=_goal(),
        scenarios=_scenarios(),
        options=_costly_options(),
        selected_option_id="costly",
        worlds=(),
        recovery_profiles=(_costly_profile(),),
    )

    assert token.authorized is False
    assert any("adversarial" in item.lower() or "counterfactual" in item.lower() for item in token.blockers)


def test_valid_costly_token_is_content_addressed_and_exact_input_verifiable():
    authority = GoalDesignStressAuthority()
    kwargs = dict(
        goal=_goal(),
        scenarios=_scenarios(),
        options=_costly_options(),
        selected_option_id="costly",
        worlds=(_challenge_world(),),
        recovery_profiles=(_costly_profile(),),
    )
    first = authority.authorize(**kwargs)
    second = authority.authorize(**kwargs)

    assert first.authorized is True
    assert first.token_id == second.token_id
    assert first == second
    assert authority.verify_token(first, **kwargs) == first
    assert first.max_stress_exposure <= first.max_allowed_exposure
    assert "costly" in first.frontier_option_ids


def test_token_cannot_be_replayed_after_selected_option_or_world_changes():
    authority = GoalDesignStressAuthority()
    kwargs = dict(
        goal=_goal(),
        scenarios=_scenarios(),
        options=_costly_options(),
        selected_option_id="costly",
        worlds=(_challenge_world(),),
        recovery_profiles=(_costly_profile(),),
    )
    token = authority.authorize(**kwargs)

    with pytest.raises(ValueError, match="stress.*token|mismatch|stale"):
        authority.verify_token(token, **{**kwargs, "selected_option_id": "safe"})

    changed_world = replace(_challenge_world(), severity=0.90)
    with pytest.raises(ValueError, match="stress.*token|mismatch|stale"):
        authority.verify_token(token, **{**kwargs, "worlds": (changed_world,)})


def test_costly_rollback_profile_must_match_selected_option():
    authority = GoalDesignStressAuthority()
    forged_profile = replace(_costly_profile(), rollback_ref="rollback:other")
    token = authority.authorize(
        goal=_goal(),
        scenarios=_scenarios(),
        options=_costly_options(),
        selected_option_id="costly",
        worlds=(_challenge_world(),),
        recovery_profiles=(forged_profile,),
    )

    assert token.authorized is False
    assert any("rollback" in item.lower() for item in token.blockers)


def test_irreversible_authority_requires_independent_tail_or_failure_world():
    authority = GoalDesignStressAuthority()
    token = authority.authorize(
        goal=_goal(),
        scenarios=_scenarios(),
        options=_irreversible_options(),
        selected_option_id="irreversible",
        worlds=(_challenge_world(),),
        recovery_profiles=(_containment_profile(),),
    )

    assert token.authorized is False
    assert any("tail" in item.lower() or "failure" in item.lower() for item in token.blockers)


def test_irreversible_authority_requires_containment_and_accepts_quantified_tail_proof():
    authority = GoalDesignStressAuthority()
    valid = authority.authorize(
        goal=_goal(),
        scenarios=_scenarios(),
        options=_irreversible_options(),
        selected_option_id="irreversible",
        worlds=(_challenge_world(), _tail_world()),
        recovery_profiles=(_containment_profile(),),
    )
    assert valid.authorized is True

    missing_containment = replace(_containment_profile(), containment_ref=None)
    blocked = authority.authorize(
        goal=_goal(),
        scenarios=_scenarios(),
        options=_irreversible_options(),
        selected_option_id="irreversible",
        worlds=(_challenge_world(), _tail_world()),
        recovery_profiles=(missing_containment,),
    )
    assert blocked.authorized is False
    assert any("containment" in item.lower() for item in blocked.blockers)


def test_stress_exposure_floor_blocks_catastrophic_selected_option():
    authority = GoalDesignStressAuthority()
    scenarios = _scenarios()
    options = (
        DesignOption(
            "costly",
            "Catastrophic under challenge",
            {"base": 0.98, "adverse": 0.01, "tail": 0.70},
            {},
            decision_class=DecisionClass.COSTLY_REVERSIBLE,
            rollback_ref="rollback:costly",
        ),
        _costly_options()[1],
    )
    world = replace(_challenge_world(), plausibility=1.0, severity=1.0)
    token = authority.authorize(
        goal=_goal(),
        scenarios=scenarios,
        options=options,
        selected_option_id="costly",
        worlds=(world,),
        recovery_profiles=(_costly_profile(),),
    )

    assert token.authorized is False
    assert token.max_stress_exposure > token.max_allowed_exposure
    assert any("exposure" in item.lower() for item in token.blockers)


def test_reversibility_frontier_blocks_option_dominated_in_robustness_and_exit_capacity():
    authority = GoalDesignStressAuthority()
    options = (
        DesignOption(
            "costly",
            "Dominated costly path",
            {"base": 0.70, "adverse": 0.62, "tail": 0.60},
            {},
            decision_class=DecisionClass.COSTLY_REVERSIBLE,
            rollback_ref="rollback:costly",
        ),
        DesignOption(
            "safe",
            "Stronger reversible path",
            {"base": 0.90, "adverse": 0.80, "tail": 0.76},
            {},
            decision_class=DecisionClass.REVERSIBLE,
            rollback_ref="rollback:safe",
        ),
    )
    token = authority.authorize(
        goal=_goal(),
        scenarios=_scenarios(),
        options=options,
        selected_option_id="costly",
        worlds=(_challenge_world(),),
        recovery_profiles=(_costly_profile(),),
    )

    assert token.authorized is False
    assert "costly" not in token.frontier_option_ids
    assert any("reversibility frontier" in item.lower() for item in token.blockers)


def test_reversibility_frontier_allows_real_robustness_tradeoff():
    authority = GoalDesignStressAuthority()
    token = authority.authorize(
        goal=_goal(),
        scenarios=_scenarios(),
        options=_costly_options(),
        selected_option_id="costly",
        worlds=(_challenge_world(),),
        recovery_profiles=(_costly_profile(),),
    )

    assert token.authorized is True
    assert "costly" in token.frontier_option_ids


def test_companion_stress_receipt_binds_exact_decision_and_token():
    authority = GoalDesignStressAuthority()
    token = authority.authorize(
        goal=_goal(),
        scenarios=_scenarios(),
        options=_costly_options(),
        selected_option_id="costly",
        worlds=(_challenge_world(),),
        recovery_profiles=(_costly_profile(),),
    )
    receipt = authority.bind_decision(token, decision_receipt_id="decision:accepted")
    again = authority.bind_decision(token, decision_receipt_id="decision:accepted")

    assert receipt == again
    assert receipt.decision_receipt_id == "decision:accepted"
    assert receipt.stress_token_id == token.token_id
    assert receipt.stress_token_digest == token.digest


def test_constructor_validation_is_fail_closed_and_policy_identity_is_canonical():
    with pytest.raises(ValueError, match="evidence"):
        StressWorldEvidence(
            "world:bad",
            "adverse",
            StressWorldKind.ADVERSARIAL,
            plausibility=0.5,
            severity=0.5,
            evidence_refs=(),
        )
    with pytest.raises(ValueError, match="finite|\[0, 1\]"):
        RecoveryProfile(
            option_id="costly",
            rollback_ref="rollback:costly",
            recovery_probability=float("nan"),
            recovery_cost=0.1,
            recovery_latency=0.1,
            residual_harm=0.1,
            evidence_refs=("evidence:bad",),
        )

    a = StressPolicy()
    b = StressPolicy()
    assert a.digest == b.digest
