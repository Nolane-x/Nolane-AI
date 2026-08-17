from dataclasses import asdict

import pytest

from cogcoder.r240_macro_applicability import MacroApplicabilityEvidence, assess_macro_applicability


def test_information_boundary_exposes_only_safe_fields():
    ev=MacroApplicabilityEvidence(observed_reliabilities=(.98,.96), posterior_entropy=.42, posterior_margin=.31, macro_raw_agreement=.73, prediction_stability=.88, search_cost_ratio=.61, counterexample_survival=None)
    forbidden={'seed','domain','family','target','truth','heldout','actual_reliability'}
    assert not (forbidden & set(asdict(ev)))


def test_high_quality_evidence_allows_macro():
    ev=MacroApplicabilityEvidence((.99,.98),.35,.45,.75,.90,.60,None)
    out=assess_macro_applicability(ev, threshold=.66)
    assert out.route=='macro'
    assert out.lower_confidence_bound >= .66


def test_low_reliability_shock_defers_macro():
    ev=MacroApplicabilityEvidence((.975,.975,.60),.55,.10,.70,.82,.60,None)
    out=assess_macro_applicability(ev, threshold=.66)
    assert out.route=='defer_raw'
    assert out.lower_confidence_bound < .66


def test_more_consistent_evidence_is_monotone():
    a=assess_macro_applicability(MacroApplicabilityEvidence((.94,.94),.6,.1,.6,.7,.8,None))
    b=assess_macro_applicability(MacroApplicabilityEvidence((.99,.99),.3,.5,.85,.95,.5,True))
    assert b.posterior_mean > a.posterior_mean
    assert b.lower_confidence_bound > a.lower_confidence_bound


def test_invalid_features_are_rejected():
    with pytest.raises(ValueError): MacroApplicabilityEvidence((.49,),.2,.2,.5,.5,.5,None)
    with pytest.raises(ValueError): MacroApplicabilityEvidence((.9,),1.1,.2,.5,.5,.5,None)


def test_assessment_is_deterministic_and_serializable():
    ev=MacroApplicabilityEvidence((.97,.96,.95),.4,.3,.7,.8,.6,True)
    a=assess_macro_applicability(ev); b=assess_macro_applicability(ev)
    assert a==b
    assert asdict(a)==asdict(b)
