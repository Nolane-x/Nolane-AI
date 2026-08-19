from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping

from cogcoder.r256_operator_dsl import evaluate_expr
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import synthesize_three_probe_causal_program


FIELDS = ('a', 'b', 'c')
ROWS = (
    # Learning collision witnesses shared with the authored family.
    (1.0, 2.0, 0.0), (2.0, 3.0, 0.0),
    (1.0, 0.0, 2.0), (2.0, 0.0, 3.0),
    (0.0, 1.0, 2.0), (0.0, 2.0, 3.0),
    (1.0, 2.0, 3.0), (4.0, 2.0, 3.0),
    (2.0, 1.0, 3.0), (2.0, 4.0, 3.0),
    (2.0, 3.0, 1.0), (2.0, 3.0, 4.0),
    # Validation.
    (-2.0, 5.0, 3.0), (4.0, -3.0, 2.0),
    (5.0, 2.0, -4.0), (-3.0, -2.0, 6.0),
    (7.0, -1.0, -5.0), (-4.0, 6.0, -2.0),
    # Terminal.
    (3.0, 5.0, -2.0), (-5.0, 4.0, 7.0),
    (6.0, -3.0, -4.0), (-7.0, -2.0, 5.0),
    (8.0, 3.0, -6.0), (-6.0, 9.0, 2.0),
    # Challenge.
    (11.0, -4.0, 8.0), (-8.0, 12.0, 7.0),
    (9.0, 5.0, -13.0), (-14.0, 6.0, 2.0),
    (10.0, -15.0, 4.0), (-16.0, 7.0, 11.0),
    # Heldout.
    (17.0, -9.0, 5.0), (-12.0, 14.0, -8.0),
    (19.0, 6.0, -7.0), (-18.0, -5.0, 13.0),
    (15.0, -11.0, -4.0), (-20.0, 8.0, 9.0),
)


def _rows() -> tuple[dict[str, float], ...]:
    return tuple(dict(zip(FIELDS, row, strict=True)) for row in ROWS)


def _oracle_from_dot(dot_callable: Callable[[object, object], object]):
    def oracle(row: Mapping[str, object]) -> float:
        left = [float(row['a']), float(row['b']), float(row['c'])]
        right = [float(row['b']), float(row['c']), float(row['a'])]
        return float(dot_callable(left, right))
    return oracle


def _probe(oracle, field: str, row: Mapping[str, object]) -> float:
    changed = dict(row)
    changed[field] = 0.0
    return float(oracle(changed))


def _collision_certificates(oracle, rows) -> tuple[tuple[bool, bool, bool], tuple[bool, bool, bool]]:
    singleton: list[bool] = []
    pair: list[bool] = []
    for intervention in FIELDS:
        free = tuple(field for field in FIELDS if field != intervention)
        buckets: dict[tuple[float, ...], set[float]] = {}
        for row in rows:
            key = (_probe(oracle, intervention, row), *(float(row[field]) for field in free))
            buckets.setdefault(key, set()).add(float(oracle(row)))
        singleton.append(any(len(targets) > 1 for targets in buckets.values()))
    for left, right in itertools.combinations(FIELDS, 2):
        free = ({*FIELDS} - {left, right}).pop()
        buckets = {}
        for row in rows:
            key = (_probe(oracle, left, row), _probe(oracle, right, row), float(row[free]))
            buckets.setdefault(key, set()).add(float(oracle(row)))
        pair.append(any(len(targets) > 1 for targets in buckets.values()))
    return tuple(singleton), tuple(pair)  # type: ignore[return-value]


def run_external_transfer(
    dot_callable: Callable[[object, object], object],
    *,
    source_id: str,
    source_version: str,
) -> dict[str, object]:
    if not callable(dot_callable):
        raise TypeError('dot_callable must be callable')
    rows = _rows()
    discovery, validation = rows[:12], rows[12:18]
    terminal, challenge, heldout = rows[18:24], rows[24:30], rows[30:36]
    oracle = _oracle_from_dot(dot_callable)
    singleton_collision, pair_collision = _collision_certificates(oracle, discovery + validation)
    need = OperatorInventionNeed(
        'R2.67.1 external cyclic dot causal necessity',
        FIELDS,
        'out',
        constants=(0.0,),
        max_depth=4,
        max_candidates=50_000,
    )
    receipt = synthesize_three_probe_causal_program(
        oracle,
        FIELDS,
        need,
        discovery,
        validation,
        terminal_contexts=terminal,
        intervention_anchor_values=(0.0,),
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=20_000,
        max_composition_candidates_total=20_000,
        ablation_max_candidates=12_000,
        composition_beam_width=128,
        probe_constants=(0.0,),
        probe_max_depth=2,
        probe_max_candidates=20_000,
        probe_beam_width=128,
    )
    selected = receipt.structure.selected
    challenge_exact = 0
    heldout_exact = 0
    if receipt.passed and receipt.expression is not None:
        challenge_exact = sum(
            int(float(evaluate_expr(receipt.expression, row)) == float(oracle(row)))
            for row in challenge
        )
        heldout_exact = sum(
            int(float(evaluate_expr(receipt.expression, row)) == float(oracle(row)))
            for row in heldout
        )
    all_three_used = bool(
        selected is not None and {'__p0', '__p1', '__p2'} <= set(selected.used_fields)
    )
    lower_order_fail = bool(
        selected is not None
        and selected.singleton_ablation_passed == (False, False, False)
        and selected.pair_ablation_passed == (False, False, False)
    )
    no_smuggling = bool(selected is not None and selected.shared_positions == ())
    passed = bool(
        receipt.passed
        and selected is not None
        and all_three_used
        and lower_order_fail
        and no_smuggling
        and singleton_collision == (True, True, True)
        and pair_collision == (True, True, True)
        and receipt.probe_validation_cases == len(validation) * 3
        and receipt.probe_validation_exact == receipt.probe_validation_cases
        and receipt.terminal_probe_validation_cases == len(terminal) * 3
        and receipt.terminal_probe_validation_exact == receipt.terminal_probe_validation_cases
        and receipt.final_validation_exact == receipt.final_validation_cases == len(terminal)
        and challenge_exact == len(challenge)
        and heldout_exact == len(heldout)
        and receipt.structure.false_accepts == 0
        and receipt.trainable_parameter_count == 0
    )
    return {
        'milestone': 'R2.67.1',
        'capability': 'certified-genuine-three-probe-causal-necessity',
        'source_id': str(source_id),
        'source_version': str(source_version),
        'source_exposure': 'io_only',
        'adapter': 'dot([a,b,c],[b,c,a])',
        'host_selected_intervention': False,
        'passed': passed,
        'semantic_profile_count': receipt.structure.semantic_profiles,
        'selected_semantic_profile_ids': list(selected.semantic_profile_ids) if selected is not None else [],
        'all_three_probes_used': all_three_used,
        'no_full_triplet_smuggling': no_smuggling,
        'singleton_collision_certificates': list(singleton_collision),
        'pair_collision_certificates': list(pair_collision),
        'all_lower_order_ablations_fail': lower_order_fail,
        'probe_validation_cases': receipt.probe_validation_cases,
        'probe_validation_exact': receipt.probe_validation_exact,
        'terminal_probe_validation_cases': receipt.terminal_probe_validation_cases,
        'terminal_probe_validation_exact': receipt.terminal_probe_validation_exact,
        'final_validation_cases': receipt.final_validation_cases,
        'final_validation_exact': receipt.final_validation_exact,
        'challenge_cases': len(challenge),
        'challenge_exact': challenge_exact,
        'heldout_cases': len(heldout),
        'heldout_exact': heldout_exact,
        'oracle_calls_learning': receipt.structure.oracle_calls,
        'oracle_calls_total': receipt.oracle_calls_total,
        'false_accepts': receipt.structure.false_accepts,
        'trainable_parameter_count': receipt.trainable_parameter_count,
    }
