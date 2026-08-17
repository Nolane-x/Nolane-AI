from cogcoder.r219_representation_types import VerifierObservation
from cogcoder.r220_language_synthesis import OperatorProposal
from cogcoder.r220_operator_language import OperatorProgram
from cogcoder.r239_predicate_macros import ProbeMacro, abstract_macro_template
from cogcoder.r239_typed_probe_dsl import add3, eq_probe, evaluate_typed_probe, sub3, trit_atom
from cogcoder.r241_competitive_discovery import discover_with_competing_macros


def _macro(macro_id, program, gain=18.0):
    template, types = abstract_macro_template(program)
    return ProbeMacro(macro_id, template, types, support=6, compression_gain=gain, raw_mdl_cost=template.mdl_cost, call_mdl_cost=2)


def _fixture():
    hypotheses = tuple(OperatorProposal(OperatorProgram.identity(), f"h{i}", 1) for i in range(6))
    atoms = ("a", "b", "c", "d", "e", "f")
    values = {
        "h0": {"a": 0, "b": 0, "c": 0, "d": 0, "e": 0, "f": 0},
        "h1": {"a": 0, "b": 0, "c": 1, "d": 0, "e": 1, "f": 0},
        "h2": {"a": 0, "b": 1, "c": 1, "d": 1, "e": 0, "f": 1},
        "h3": {"a": 1, "b": 0, "c": 1, "d": 1, "e": 1, "f": 0},
        "h4": {"a": 1, "b": 1, "c": 2, "d": 2, "e": 0, "f": 1},
        "h5": {"a": 2, "b": 1, "c": 0, "d": 0, "e": 2, "f": 2},
    }
    macros = (
        _macro("m-add", eq_probe(add3(trit_atom("a"), trit_atom("b")), trit_atom("c")), 20.0),
        _macro("m-sub", eq_probe(sub3(trit_atom("d"), trit_atom("e")), trit_atom("f")), 19.0),
    )
    return hypotheses, atoms, values, macros


def _truth_verifier(values, target="h0"):
    def verifier(program):
        return VerifierObservation(program.probe_id, bool(evaluate_typed_probe(program, values[target])), 0.99)
    return verifier


def _run(**overrides):
    hypotheses, atoms, values, macros = _fixture()
    kwargs = dict(
        verifier=_truth_verifier(values),
        counterexample_check=lambda h: h.operator_id == "h0",
        query_budget=6,
        probe_cost_budget=20.0,
        accept_probability=0.92,
        accept_margin=0.70,
        atom_shortlist_size=6,
        max_raw_candidates=180,
        max_macro_candidates=80,
        competition_threshold=0.52,
        macro_margin_over_raw=-0.08,
    )
    kwargs.update(overrides)
    return discover_with_competing_macros(hypotheses, atoms, values, (), macros, **kwargs)


def test_fixture_can_exercise_two_macro_ids():
    decision = _run(accept_probability=0.999, accept_margin=0.99)
    assert set(decision.selected_macro_ids) == {"m-add", "m-sub"}
    assert set(decision.route_history) >= {"m-add", "m-sub"}


def test_raw_fallback_is_possible_when_no_macro_beats_margin():
    decision = _run(accept_probability=0.999, accept_margin=0.99, macro_margin_over_raw=1.0)
    assert "raw" in decision.route_history
    assert decision.raw_probe_ids


def test_macro_candidate_cap_is_aggregate_across_episode():
    decision = _run(max_macro_candidates=9, accept_probability=0.999, accept_margin=0.99)
    assert decision.macro_candidates_evaluated <= 9


def test_high_reliability_semantic_conflict_quarantines_only_one_macro():
    hypotheses, atoms, values, macros = _fixture()
    calls = {"n": 0}

    def adversarial(program):
        calls["n"] += 1
        truth = bool(evaluate_typed_probe(program, values["h0"]))
        label = (not truth) if calls["n"] <= 2 else truth
        return VerifierObservation(program.probe_id, label, 0.99)

    decision = discover_with_competing_macros(
        hypotheses, atoms, values, (), macros,
        verifier=adversarial,
        counterexample_check=lambda h: h.operator_id == "h0",
        query_budget=6,
        probe_cost_budget=20.0,
        accept_probability=0.999,
        accept_margin=0.99,
        atom_shortlist_size=6,
        max_raw_candidates=180,
        max_macro_candidates=80,
        competition_threshold=0.52,
        macro_margin_over_raw=-0.08,
    )
    assert len(decision.quarantined_macro_ids) == 1
    assert len(set(decision.selected_macro_ids) - set(decision.quarantined_macro_ids)) >= 1


def test_router_cannot_bypass_frozen_acceptance_authority():
    rejected = _run(counterexample_check=lambda h: False, accept_probability=0.60, accept_margin=0.10)
    assert rejected.status == "abstain"
    assert rejected.operator_id is None
    assert rejected.reason == "counterexample_rejected_top_hypothesis"


def test_macro_candidate_schedule_is_horizon_stable_until_aggregate_cap_exhausts():
    short = _run(query_budget=5, accept_probability=1.0, accept_margin=1.0)
    long = _run(query_budget=6, accept_probability=1.0, accept_margin=1.0)
    assert short.queries == long.queries[: len(short.queries)]
    assert short.route_history == long.route_history[: len(short.route_history)]


def test_unconditional_ablation_keeps_same_router_but_disables_quarantine():
    hypotheses, atoms, values, macros = _fixture()
    calls = {"n": 0}

    def adversarial(program):
        calls["n"] += 1
        truth = bool(evaluate_typed_probe(program, values["h0"]))
        return VerifierObservation(program.probe_id, (not truth) if calls["n"] <= 2 else truth, 0.99)

    decision = discover_with_competing_macros(
        hypotheses, atoms, values, (), macros,
        verifier=adversarial,
        counterexample_check=lambda h: h.operator_id == "h0",
        query_budget=6,
        probe_cost_budget=20.0,
        accept_probability=0.999,
        accept_margin=0.99,
        atom_shortlist_size=6,
        max_raw_candidates=180,
        max_macro_candidates=80,
        competition_threshold=0.0,
        macro_margin_over_raw=-0.08,
        enable_macro_calibration=False,
    )
    assert decision.selected_macro_ids
    assert decision.quarantined_macro_ids == ()
