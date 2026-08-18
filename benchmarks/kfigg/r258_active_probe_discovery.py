from __future__ import annotations

from dataclasses import dataclass

from benchmarks.kfigg.r257_verified_vocabulary_growth import build_promoted_vocabulary
from cogcoder.r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary
from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r257_vocabulary import AbstractionCall, evaluate_with_vocabulary
from cogcoder.r257_vocabulary_synthesis import synthesize_with_vocabulary
from cogcoder.r258_active_probe import ProbeBudget, discover_verified_subgoal


_BASE_TRAIN = (
    (-4.0, 0.0, 8.0, 2.0, 10.0), (0.0, 0.0, 8.0, 2.0, 10.0),
    (2.0, 0.0, 8.0, 2.0, 10.0), (4.0, 0.0, 8.0, 2.0, 10.0),
    (6.0, 0.0, 8.0, 2.0, 10.0), (8.0, 0.0, 8.0, 2.0, 10.0),
    (12.0, 0.0, 8.0, 2.0, 10.0), (0.0, -4.0, 4.0, -2.0, 6.0),
)
_BASE_CHALLENGE = (
    (-6.0, -4.0, 4.0, -2.0, 6.0), (-4.0, -4.0, 4.0, -2.0, 6.0),
    (-2.0, -4.0, 4.0, -2.0, 6.0), (2.0, -4.0, 4.0, -2.0, 6.0),
    (4.0, -4.0, 4.0, -2.0, 6.0), (8.0, -4.0, 4.0, -2.0, 6.0),
    (4.0, 2.0, 10.0, -4.0, 4.0), (8.0, 2.0, 10.0, -4.0, 4.0),
)


@dataclass(frozen=True, slots=True)
class Episode:
    name: str
    fields: tuple[str, str, str, str, str]
    x_scale: float
    x_shift: float
    y_scale: float
    y_shift: float
    pair_id: str


def _episodes() -> tuple[Episode, ...]:
    return (
        Episode('a0', ('k7', 'k2', 'k9', 'k4', 'k1'), 1.0, 0.0, 1.0, 0.0, 'pair-a'),
        Episode('a1', ('z5', 'z0', 'z7', 'z2', 'z9'), 1.0, 0.0, 1.0, 0.0, 'pair-a'),
        Episode('b0', ('m4', 'm8', 'm1', 'm6', 'm3'), 1.5, -3.0, 0.75, 2.0, 'pair-b'),
        Episode('b1', ('p9', 'p5', 'p2', 'p7', 'p0'), 1.5, -3.0, 0.75, 2.0, 'pair-b'),
        Episode('c0', ('r6', 'r3', 'r8', 'r1', 'r4'), 0.5, 5.0, 2.0, -7.0, 'pair-c'),
        Episode('c1', ('u1', 'u9', 'u4', 'u7', 'u2'), 0.5, 5.0, 2.0, -7.0, 'pair-c'),
    )


def _transform(ep: Episode, row: tuple[float, float, float, float, float]) -> tuple[float, float, float, float, float]:
    x, a, b, fa, fb = row
    return (
        ep.x_scale * x + ep.x_shift,
        ep.x_scale * a + ep.x_shift,
        ep.x_scale * b + ep.x_shift,
        ep.y_scale * fa + ep.y_shift,
        ep.y_scale * fb + ep.y_shift,
    )


def _context(ep: Episode, row: tuple[float, float, float, float, float]) -> dict[str, float]:
    return dict(zip(ep.fields, _transform(ep, row)))


def _oracle(ep: Episode, context: dict[str, object]) -> float:
    x, a, b, fa, fb = ep.fields
    xv = float(context[x]); av = float(context[a]); bv = float(context[b])
    fav = float(context[fa]); fbv = float(context[fb])
    t = min(max((xv - av) / (bv - av), 0.0), 1.0)
    return fav + t * (fbv - fav)


def _rows(ep: Episode, raw: tuple[tuple[float, float, float, float, float], ...], prefix: str) -> tuple[OperatorExample, ...]:
    rows = []
    for index, row in enumerate(raw):
        context = _context(ep, row)
        rows.append(OperatorExample(f'{ep.name}:{prefix}:{index}', context, _oracle(ep, context)))
    return tuple(rows)


def _rename_expr(expr: Expr, mapping: dict[str, str]) -> Expr:
    if isinstance(expr, Field):
        return Field(mapping.get(expr.name, expr.name))
    if isinstance(expr, Const):
        return expr
    if isinstance(expr, Unary):
        return Unary(expr.op, _rename_expr(expr.arg, mapping))
    if isinstance(expr, Binary):
        return Binary(expr.op, _rename_expr(expr.left, mapping), _rename_expr(expr.right, mapping))
    if isinstance(expr, IfElse):
        return IfElse(
            _rename_expr(expr.condition, mapping),
            _rename_expr(expr.when_true, mapping),
            _rename_expr(expr.when_false, mapping),
        )
    if isinstance(expr, AbstractionCall):
        return AbstractionCall(expr.abstraction_id, tuple(_rename_expr(arg, mapping) for arg in expr.args))
    raise TypeError(f'unsupported expression node: {type(expr).__name__}')


def run_benchmark() -> dict[str, object]:
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    budget = ProbeBudget(
        max_oracle_calls=900,
        max_interventions=40,
        subgoal_max_depth=2,
        subgoal_max_candidates=8000,
        max_cegis_rounds=2,
    )

    episodes = _episodes()
    base_episodes = {pair: next(ep for ep in episodes if ep.pair_id == pair) for pair in ('pair-a', 'pair-b', 'pair-c')}
    twin_episodes = {
        pair: next(ep for ep in episodes if ep.pair_id == pair and ep.name != base_episodes[pair].name)
        for pair in base_episodes
    }

    receipts: list[dict[str, object]] = []
    pair_receipts: dict[str, list[dict[str, object]]] = {}
    discoveries: dict[str, object] = {}
    base_exact = 0
    active_exact = 0
    false_accepts = 0

    # Three genuinely separate active-discovery worlds use different affine regimes.
    for pair_id, ep in base_episodes.items():
        train = _rows(ep, _BASE_TRAIN, 'train')
        challenge = tuple(_context(ep, row) for row in _BASE_CHALLENGE)
        need = OperatorInventionNeed(
            f'{ep.name}:opaque-full-target', ep.fields, f'{ep.name}:out',
            constants=(0, 1), max_depth=3, max_candidates=1000,
        )
        base = synthesize_with_vocabulary(need, train, vocabulary)
        active = discover_verified_subgoal(
            need, train, challenge, vocabulary,
            lambda context, episode=ep: _oracle(episode, dict(context)),
            budget=budget,
        )
        base_exact += int(base.passed)
        accepted = bool(active.passed and active.challenge_exact == len(challenge))
        active_exact += int(accepted)
        false_accepts += int(active.passed and not accepted)
        row = {
            'episode': ep.name,
            'pair_id': pair_id,
            'mode': 'active_discovery',
            'harness_free_passed': bool(base.passed),
            'active_passed': bool(active.passed),
            'challenge_exact': active.challenge_exact,
            'challenge_cases': len(challenge),
            'oracle_calls': active.oracle_calls,
            'interventions_considered': active.interventions_considered,
            'exposure_abstraction_id': active.abstraction_id,
            'exposure_target_param_index': active.target_param_index,
            'fixed_field_profile_ids': [list(item) for item in active.fixed_field_profile_ids],
            'fixed_values': [value for _field, value in active.fixed_field_values],
            'reason': active.reason,
        }
        receipts.append(row)
        pair_receipts.setdefault(pair_id, []).append(row)
        discoveries[pair_id] = active

    # Each discovery is then transported through a pure field-renaming metamorphism
    # into a second opaque world. This checks the learned intervention/program itself
    # contains no field-name semantics without paying for another identical 8k search.
    for pair_id, twin in twin_episodes.items():
        base_ep = base_episodes[pair_id]
        active = discoveries[pair_id]
        train = _rows(twin, _BASE_TRAIN, 'train')
        challenge = tuple(_context(twin, row) for row in _BASE_CHALLENGE)
        need = OperatorInventionNeed(
            f'{twin.name}:opaque-full-target', twin.fields, f'{twin.name}:out',
            constants=(0, 1), max_depth=3, max_candidates=1000,
        )
        baseline = synthesize_with_vocabulary(need, train, vocabulary)
        base_exact += int(baseline.passed)
        field_map = dict(zip(base_ep.fields, twin.fields))
        full_expr = _rename_expr(active.full_expression, field_map) if active.full_expression is not None else None
        subgoal_expr = _rename_expr(active.subgoal_expression, field_map) if active.subgoal_expression is not None else None
        fixed_values = tuple((field_map[field], value) for field, value in active.fixed_field_values)
        fixed_map = dict(fixed_values)

        challenge_exact = 0
        subgoal_exact = 0
        if full_expr is not None and subgoal_expr is not None:
            for context in challenge:
                expected = _oracle(twin, dict(context))
                actual = evaluate_with_vocabulary(full_expr, context, vocabulary)
                challenge_exact += int(abs(float(actual) - float(expected)) <= 1e-12)
                intervened = dict(context); intervened.update(fixed_map)
                sub_actual = evaluate_with_vocabulary(subgoal_expr, intervened, vocabulary)
                sub_expected = _oracle(twin, intervened)
                subgoal_exact += int(abs(float(sub_actual) - float(sub_expected)) <= 1e-12)
        accepted = bool(challenge_exact == len(challenge) and subgoal_exact == len(challenge))
        active_exact += int(accepted)
        false_accepts += int(full_expr is not None and not accepted)
        row = {
            'episode': twin.name,
            'pair_id': pair_id,
            'mode': 'metamorphic_rename_replay',
            'harness_free_passed': bool(baseline.passed),
            'active_passed': accepted,
            'challenge_exact': challenge_exact,
            'challenge_cases': len(challenge),
            'subgoal_intervention_exact': subgoal_exact,
            'oracle_calls': active.oracle_calls,
            'interventions_considered': active.interventions_considered,
            'exposure_abstraction_id': active.abstraction_id,
            'exposure_target_param_index': active.target_param_index,
            'fixed_field_profile_ids': [list(item) for item in active.fixed_field_profile_ids],
            'fixed_values': [value for _field, value in active.fixed_field_values],
            'reason': 'metamorphic_rename_exact' if accepted else 'metamorphic_rename_failed',
        }
        receipts.append(row)
        pair_receipts.setdefault(pair_id, []).append(row)

    renaming_invariance = True
    for rows in pair_receipts.values():
        if len(rows) != 2:
            renaming_invariance = False
            continue
        active_row = next(row for row in rows if row['mode'] == 'active_discovery')
        twin_row = next(row for row in rows if row['mode'] == 'metamorphic_rename_replay')
        renaming_invariance &= bool(
            active_row['active_passed'] == twin_row['active_passed']
            and active_row['challenge_exact'] == twin_row['challenge_exact']
            and active_row['exposure_abstraction_id'] == twin_row['exposure_abstraction_id']
            and active_row['exposure_target_param_index'] == twin_row['exposure_target_param_index']
            and active_row['fixed_field_profile_ids'] == twin_row['fixed_field_profile_ids']
            and active_row['fixed_values'] == twin_row['fixed_values']
        )

    return {
        'milestone': 'R2.58',
        'capability': 'active-probe-subgoal-discovery',
        'episodes': len(receipts),
        'active_discovery_runs': len(base_episodes),
        'metamorphic_rename_replays': len(twin_episodes),
        'r257_harness_free_exact': base_exact,
        'r258_active_exact': active_exact,
        'false_accepts': false_accepts,
        'renaming_invariance': bool(renaming_invariance),
        'max_oracle_calls': max((int(row['oracle_calls']) for row in receipts), default=0),
        'max_interventions_considered': max((int(row['interventions_considered']) for row in receipts), default=0),
        'trainable_parameter_count': 0,
        'claim_boundary': (
            'Three bounded active-discovery affine worlds plus three field-renaming metamorphic replays over the '
            'finite pure R2.56/R2.57 evaluator; not open-ended experiment design, effectful tool invention, '
            'or general program synthesis.'
        ),
        'episode_receipts': sorted(receipts, key=lambda row: str(row['episode'])),
    }


if __name__ == '__main__':
    import json
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
