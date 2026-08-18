from benchmarks.kfigg.r257_verified_vocabulary_growth import build_promoted_vocabulary
from cogcoder.r257_vocabulary import AbstractionCall, Const, Field, evaluate_with_vocabulary
from cogcoder.r258_active_probe import discover_exposure_schemas


def test_discovers_identity_exposure_from_learned_structure_without_semantic_names():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    schemas = discover_exposure_schemas(
        vocabulary,
        constants=(-1, 0, 1),
        probe_values=(-3, -1, 0, 0.25, 1, 2, 5),
    )
    assert schemas
    assert all(schema.validation_cases == 7 for schema in schemas)
    assert all(schema.target_param_index not in dict(schema.fixed_params) for schema in schemas)

    # At least one learned 3-parameter abstraction must be controllable into a pure
    # identity of its remaining parameter. No abstraction/field semantic name is used.
    identity_schema = next(schema for schema in schemas if len(schema.fixed_params) == 2)
    abstraction = vocabulary.get(identity_schema.abstraction_id)
    args = []
    fixed = dict(identity_schema.fixed_params)
    for index in range(abstraction.parameter_count):
        args.append(Const(fixed[index]) if index in fixed else Field('opaque_latent'))
    call = AbstractionCall(abstraction.abstraction_id, tuple(args))
    for value in (-7, -0.5, 0, 0.125, 3, 11):
        assert evaluate_with_vocabulary(call, {'opaque_latent': value}, vocabulary) == value


def test_exposure_schema_order_is_deterministic_and_content_addressed():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    first = discover_exposure_schemas(vocabulary, constants=(0, 1))
    second = discover_exposure_schemas(vocabulary, constants=(1, 0, 1))
    assert first == second
    assert tuple((row.abstraction_id, row.target_param_index, row.fixed_params) for row in first) == tuple(
        sorted((row.abstraction_id, row.target_param_index, row.fixed_params) for row in first)
    )


def test_exposure_schemas_reject_redundant_controls():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    schemas = discover_exposure_schemas(vocabulary, constants=(0, 1))
    # normalize(x, 0, 1) -> x and lerp(0, t, 1) -> t are the two
    # non-degenerate identity exposures in the learned R2.57 vocabulary.
    assert len(schemas) == 2
    assert all(len(row.fixed_params) == 2 for row in schemas)

import math

from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r257_vocabulary import evaluate_with_vocabulary
from cogcoder.r257_vocabulary_synthesis import synthesize_with_vocabulary
from cogcoder.r258_active_probe import ProbeBudget, discover_verified_subgoal


def _opaque_linearstep_fixture(prefix='f'):
    fields = (f'{prefix}7', f'{prefix}2', f'{prefix}9', f'{prefix}4', f'{prefix}1')
    x, a, b, fa, fb = fields

    def oracle(context):
        xv = float(context[x]); av = float(context[a]); bv = float(context[b])
        fav = float(context[fa]); fbv = float(context[fb])
        t = min(max((xv - av) / (bv - av), 0.0), 1.0)
        return fav + t * (fbv - fav)

    raw_train = (
        (-4.0, 0.0, 8.0, 2.0, 10.0), (0.0, 0.0, 8.0, 2.0, 10.0),
        (2.0, 0.0, 8.0, 2.0, 10.0), (4.0, 0.0, 8.0, 2.0, 10.0),
        (6.0, 0.0, 8.0, 2.0, 10.0), (8.0, 0.0, 8.0, 2.0, 10.0),
        (12.0, 0.0, 8.0, 2.0, 10.0), (0.0, -4.0, 4.0, -2.0, 6.0),
    )
    raw_challenge = (
        (-6.0, -4.0, 4.0, -2.0, 6.0), (-4.0, -4.0, 4.0, -2.0, 6.0),
        (-2.0, -4.0, 4.0, -2.0, 6.0), (2.0, -4.0, 4.0, -2.0, 6.0),
        (4.0, -4.0, 4.0, -2.0, 6.0), (8.0, -4.0, 4.0, -2.0, 6.0),
        (4.0, 2.0, 10.0, -4.0, 4.0), (8.0, 2.0, 10.0, -4.0, 4.0),
    )

    def context(row):
        return dict(zip(fields, row))

    train = tuple(OperatorExample(f'train:{i}', context(row), oracle(context(row))) for i, row in enumerate(raw_train))
    challenge_contexts = tuple(context(row) for row in raw_challenge)
    need = OperatorInventionNeed(
        'opaque full target', fields, f'{prefix}:out', constants=(0, 1), max_depth=3, max_candidates=1000,
    )
    return fields, oracle, train, challenge_contexts, need


def test_active_planner_discovers_verified_subgoal_without_named_endpoint_probe():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    fields, oracle, train, challenge_contexts, need = _opaque_linearstep_fixture('q')

    harness_free = synthesize_with_vocabulary(need, train, vocabulary)
    assert not harness_free.passed

    receipt = discover_verified_subgoal(
        need,
        train,
        challenge_contexts,
        vocabulary,
        oracle,
        budget=ProbeBudget(max_oracle_calls=900, max_interventions=40, subgoal_max_depth=2, subgoal_max_candidates=12000),
    )
    assert receipt.passed
    assert receipt.subgoal_expression is not None
    assert receipt.full_expression is not None
    assert len(receipt.fixed_fields) == 2
    assert receipt.oracle_calls <= 900
    assert receipt.challenge_exact == len(challenge_contexts)

    x, a, b, _fa, _fb = fields
    for xv, av, bv in ((-4, 0, 8), (2, 0, 8), (6, -4, 4), (12, 2, 10)):
        actual = float(evaluate_with_vocabulary(receipt.subgoal_expression, {x: xv, a: av, b: bv}, vocabulary))
        expected = min(max((xv - av) / (bv - av), 0.0), 1.0)
        assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


def test_probe_budget_exhaustion_fails_closed_without_seed():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    _fields, oracle, train, challenge_contexts, need = _opaque_linearstep_fixture('b')
    receipt = discover_verified_subgoal(
        need,
        train,
        challenge_contexts,
        vocabulary,
        oracle,
        budget=ProbeBudget(max_oracle_calls=3, max_interventions=40, subgoal_max_depth=2, subgoal_max_candidates=12000),
    )
    assert not receipt.passed
    assert receipt.subgoal_expression is None
    assert receipt.full_expression is None
    assert receipt.oracle_calls <= 3
    assert receipt.reason == 'oracle_budget_exhausted'


def test_nonfinite_oracle_output_fails_closed():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    _fields, _oracle, train, challenge_contexts, need = _opaque_linearstep_fixture('n')
    receipt = discover_verified_subgoal(
        need,
        train,
        challenge_contexts,
        vocabulary,
        lambda _context: float('nan'),
        budget=ProbeBudget(max_oracle_calls=100, max_interventions=4, subgoal_max_depth=2, subgoal_max_candidates=200),
    )
    assert not receipt.passed
    assert receipt.subgoal_expression is None
    assert receipt.reason == 'invalid_oracle_output'


def test_active_probe_is_field_renaming_invariant_on_observation_profiles():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    _fields_a, oracle_a, train_a, challenge_a, need_a = _opaque_linearstep_fixture('alpha')
    _fields_b, oracle_b, train_b, challenge_b, need_b = _opaque_linearstep_fixture('omega')
    budget = ProbeBudget(max_oracle_calls=900, max_interventions=40, subgoal_max_depth=2, subgoal_max_candidates=12000)

    first = discover_verified_subgoal(need_a, train_a, challenge_a, vocabulary, oracle_a, budget=budget)
    second = discover_verified_subgoal(need_b, train_b, challenge_b, vocabulary, oracle_b, budget=budget)

    assert first.passed and second.passed
    assert first.abstraction_id == second.abstraction_id
    assert first.target_param_index == second.target_param_index
    assert first.fixed_field_profile_ids == second.fixed_field_profile_ids
    assert first.oracle_calls == second.oracle_calls
    assert first.interventions_considered == second.interventions_considered
    assert first.challenge_exact == second.challenge_exact
