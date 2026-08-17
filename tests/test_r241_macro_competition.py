from dataclasses import fields, replace

import pytest

from cogcoder.r241_macro_competition import (
    MacroCompetitionAssessment,
    MacroCompetitionEvidence,
    MacroCompetitionState,
    assess_competing_macro,
    update_macro_competition_state,
)


def supportive_evidence(**overrides):
    base = dict(
        reported_reliability=0.97,
        semantic_alignment=0.94,
        prediction_stability=0.91,
        posterior_entropy=0.42,
        posterior_margin=0.44,
        information_gain=0.38,
        relative_cost=0.24,
        counterexample_survival=True,
    )
    base.update(overrides)
    return MacroCompetitionEvidence(**base)


def test_competition_evidence_validates_observable_ranges():
    ev = supportive_evidence()
    assert ev.reported_reliability == 0.97
    with pytest.raises(ValueError):
        supportive_evidence(reported_reliability=0.5)
    with pytest.raises(ValueError):
        supportive_evidence(semantic_alignment=1.1)
    with pytest.raises(ValueError):
        supportive_evidence(relative_cost=-0.01)


def test_machine_epsilon_boundary_noise_is_clamped_but_material_violation_rejected():
    low = supportive_evidence(information_gain=-4.440892098500627e-16)
    high = supportive_evidence(prediction_stability=1.0000000000000002)
    assert low.information_gain == 0.0
    assert high.prediction_stability == 1.0
    with pytest.raises(ValueError):
        supportive_evidence(information_gain=-1e-8)
    with pytest.raises(ValueError):
        supportive_evidence(prediction_stability=1.0 + 1e-8)


def test_information_boundary_excludes_hidden_identity_and_oracle_fields():
    names = {f.name.lower() for f in fields(MacroCompetitionEvidence)} | {
        f.name.lower() for f in fields(MacroCompetitionState)
    }
    forbidden = ("seed", "domain", "family", "target", "truth", "heldout", "actual_reliability", "oracle")
    assert not any(any(token in name for token in forbidden) for name in names)


def test_assessment_uses_conservative_lcb_and_supports_good_macro():
    state = MacroCompetitionState(macro_id="m-good", alpha=10.0, beta=2.0)
    assessment = assess_competing_macro(state, supportive_evidence(), threshold=0.55)
    assert isinstance(assessment, MacroCompetitionAssessment)
    assert 0.0 <= assessment.lower_confidence_bound < assessment.posterior_mean <= 1.0
    assert assessment.route == "macro"
    assert assessment.reason == "macro_competition_supported"


def test_low_reliability_shock_quarantines_only_updated_macro():
    a = MacroCompetitionState(macro_id="m-a", alpha=8.0, beta=2.0)
    b = MacroCompetitionState(macro_id="m-b", alpha=8.0, beta=2.0)
    peer_snapshot = b

    shocked = update_macro_competition_state(
        a,
        supportive_evidence(reported_reliability=0.56, semantic_alignment=0.20, counterexample_survival=False),
    )

    assert shocked.quarantined
    assert shocked.shock_count == 1
    assert b == peer_snapshot
    assert not b.quarantined


def test_repeated_high_reliability_semantic_conflict_quarantines_macro():
    state = MacroCompetitionState(macro_id="m-semantic", alpha=8.0, beta=2.0)
    conflict = supportive_evidence(
        reported_reliability=0.98,
        semantic_alignment=0.08,
        prediction_stability=0.82,
        counterexample_survival=None,
    )

    once = update_macro_competition_state(state, conflict)
    twice = update_macro_competition_state(once, conflict)

    assert not once.quarantined
    assert once.semantic_conflicts == 1
    assert twice.quarantined
    assert twice.semantic_conflicts == 2
    assert twice.shock_count >= 1


def test_histories_are_immutable_and_record_information_and_cost():
    state = MacroCompetitionState(macro_id="m-history")
    updated = update_macro_competition_state(state, supportive_evidence(information_gain=0.31, relative_cost=0.27))

    assert state.information_gain_history == ()
    assert state.cost_history == ()
    assert updated.information_gain_history == (0.31,)
    assert updated.cost_history == (0.27,)
    with pytest.raises(Exception):
        updated.alpha = 99.0
