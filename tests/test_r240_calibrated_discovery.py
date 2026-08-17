import benchmarks.kfigg.r239_recursive_typed_probe_dsl as b
from cogcoder.r239_typed_probe_dsl import evaluate_typed_probe
from cogcoder.r240_calibrated_discovery import discover_with_calibrated_macro_applicability


def _run(seed, regime):
    family='z3_bilinear_asym'
    hypotheses,atoms,values=b._prepared(family)
    target,equivalent=b._target(family,seed)
    target_values=values[target]
    def verifier(program):
        truth=evaluate_typed_probe(program,target_values)
        return b._noise_observation(family,seed,regime,program,bool(truth))
    return discover_with_calibrated_macro_applicability(
        hypotheses,atoms,values,b._initial_probes(family,seed,regime),b.learn_macro_library(),
        verifier=verifier,counterexample_check=lambda h:h.operator_id in equivalent,
        query_budget=b.QUERY_BUDGET,probe_cost_budget=b.PROBE_COST_BUDGET,
        accept_probability=b.ACCEPT_PROBABILITY,accept_margin=b.ACCEPT_MARGIN,
        atom_shortlist_size=b.ATOM_SHORTLIST_SIZE,max_raw_candidates=b.MAX_RAW_CANDIDATES,
        max_macro_candidates=b.MAX_MACRO_CANDIDATES,applicability_threshold=.60,
    ), equivalent


def test_clean_supported_trajectory_exercises_macro():
    d,equiv=_run(613,'held_clean')
    assert d.status=='accept' and d.operator_id in equiv
    assert 'macro' in d.applicability_routes
    assert d.macro_probe_ids


def test_low_reliability_shock_causes_raw_deferral():
    d,_=_run(601,'held_noisy')
    assert 'defer_raw' in d.applicability_routes
    first=d.applicability_routes.index('defer_raw')
    assert all(r=='defer_raw' for r in d.applicability_routes[first:])


def test_routing_cannot_bypass_acceptance_authority():
    d,_=_run(607,'held_noisy')
    if d.status=='accept':
        assert d.operator_id is not None
        assert d.posterior >= b.ACCEPT_PROBABILITY
        assert d.margin >= b.ACCEPT_MARGIN
    else:
        assert d.operator_id is None


def test_route_receipts_match_noninitial_decisions():
    d,_=_run(613,'held_noisy')
    assert len(d.applicability_routes) == max(0,len(d.queries)-1)
    assert len(d.applicability_lcbs)==len(d.applicability_routes)
    assert all(0.0 <= x <= 1.0 for x in d.applicability_lcbs)
