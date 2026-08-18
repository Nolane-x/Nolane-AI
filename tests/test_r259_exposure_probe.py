from __future__ import annotations

from benchmarks.kfigg.r257_verified_vocabulary_growth import build_promoted_vocabulary
from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r259_exposure_probe import ProbeBudget, discover_exposure_schemas, discover_verified_subgoal


def _fixture(prefix: str = 'e'):
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
    def ctx(row): return dict(zip(fields, row))
    train = tuple(OperatorExample(f't:{i}', ctx(row), oracle(ctx(row))) for i, row in enumerate(raw_train))
    challenge = tuple(ctx(row) for row in raw_challenge)
    need = OperatorInventionNeed('exposure-control', fields, f'{prefix}:out', constants=(0, 1), max_depth=3, max_candidates=1000)
    return fields, oracle, train, challenge, need


def test_exposure_schema_discovery_rejects_redundant_controls():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    schemas = discover_exposure_schemas(vocabulary, constants=(0, 1))
    assert len(schemas) == 2
    assert all(len(row.fixed_params) == 2 for row in schemas)
    assert all(row.validation_cases >= 7 for row in schemas)


def test_exposure_probe_solves_opaque_target_without_manual_probe_rows():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    _fields, oracle, train, challenge, need = _fixture('opaque')
    receipt = discover_verified_subgoal(
        need, train, challenge, vocabulary, oracle,
        budget=ProbeBudget(max_oracle_calls=900, max_interventions=40, subgoal_max_depth=2, subgoal_max_candidates=12000),
    )
    assert receipt.passed
    assert receipt.full_expression is not None
    assert receipt.challenge_exact == len(challenge)
    assert receipt.oracle_calls <= 900


def test_exposure_oracle_budget_exhaustion_fails_closed():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    _fields, oracle, train, challenge, need = _fixture('budget')
    receipt = discover_verified_subgoal(
        need, train, challenge, vocabulary, oracle,
        budget=ProbeBudget(max_oracle_calls=3, max_interventions=40, subgoal_max_depth=2, subgoal_max_candidates=12000),
    )
    assert not receipt.passed
    assert receipt.full_expression is None
    assert receipt.oracle_calls <= 3
    assert receipt.reason == 'oracle_budget_exhausted'


def test_exposure_invalid_oracle_output_fails_closed():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    _fields, _oracle, train, challenge, need = _fixture('invalid')
    receipt = discover_verified_subgoal(
        need, train, challenge, vocabulary, lambda _context: float('nan'),
        budget=ProbeBudget(max_oracle_calls=100, max_interventions=4, subgoal_max_depth=2, subgoal_max_candidates=200),
    )
    assert not receipt.passed
    assert receipt.full_expression is None
    assert receipt.reason == 'invalid_oracle_output'


def test_exposure_field_rename_preserves_structural_decision():
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    _fa, oa, ta, ca, na = _fixture('left')
    _fb, ob, tb, cb, nb = _fixture('right')
    budget = ProbeBudget(max_oracle_calls=900, max_interventions=40, subgoal_max_depth=2, subgoal_max_candidates=12000)
    first = discover_verified_subgoal(na, ta, ca, vocabulary, oa, budget=budget)
    second = discover_verified_subgoal(nb, tb, cb, vocabulary, ob, budget=budget)
    assert first.passed and second.passed
    assert first.abstraction_id == second.abstraction_id
    assert first.target_param_index == second.target_param_index
    assert first.oracle_calls == second.oracle_calls
    assert first.interventions_considered == second.interventions_considered
