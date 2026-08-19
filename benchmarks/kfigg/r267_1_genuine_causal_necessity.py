from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping

from cogcoder.r256_operator_dsl import evaluate_expr
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import synthesize_three_probe_causal_program


ROLES = ('a', 'b', 'c')
CYCLIC_ROWS = (
    # Pair-specific zero-field collision witnesses.
    (1.0, 2.0, 0.0), (2.0, 3.0, 0.0),
    (1.0, 0.0, 2.0), (2.0, 0.0, 3.0),
    (0.0, 1.0, 2.0), (0.0, 2.0, 3.0),
    # Singleton collision witnesses.
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
    # Heldout.
    (11.0, -4.0, 8.0), (-8.0, 12.0, 7.0),
    (9.0, 5.0, -13.0), (-14.0, 6.0, 2.0),
    (10.0, -15.0, 4.0), (-16.0, 7.0, 11.0),
)

TRIANGLE_MIN_ROWS = (
    (2.0, 3.0, 1.0), (4.0, 5.0, 1.0),
    (2.0, 1.0, 3.0), (4.0, 1.0, 5.0),
    (1.0, 2.0, 3.0), (1.0, 4.0, 5.0),
    (1.0, 3.0, 5.0), (2.0, 3.0, 5.0),
    (3.0, 1.0, 5.0), (3.0, 2.0, 5.0),
    (3.0, 5.0, 1.0), (3.0, 5.0, 2.0),
    (2.0, 5.0, 4.0), (6.0, 3.0, 2.0),
    (4.0, 7.0, 5.0), (8.0, 2.0, 6.0),
    (5.0, 9.0, 3.0), (7.0, 6.0, 10.0),
    (11.0, 4.0, 8.0), (3.0, 12.0, 7.0),
    (9.0, 5.0, 13.0), (14.0, 6.0, 2.0),
    (10.0, 15.0, 4.0), (16.0, 7.0, 11.0),
)


def _role_rows(values=CYCLIC_ROWS) -> tuple[dict[str, float], ...]:
    return tuple(dict(zip(ROLES, row, strict=True)) for row in values)


def _cyclic(row: Mapping[str, object]) -> float:
    a, b, c = (float(row[name]) for name in ROLES)
    return a * b + b * c + c * a


def _triangle_min(row: Mapping[str, object]) -> float:
    a, b, c = (float(row[name]) for name in ROLES)
    return min(a, b) + min(b, c) + min(c, a)


def _probe(oracle: Callable[[Mapping[str, object]], float], field: str, row: Mapping[str, object]) -> float:
    changed = dict(row)
    changed[field] = 0.0
    return float(oracle(changed))


def _collision_certificates(
    oracle: Callable[[Mapping[str, object]], float],
    rows: tuple[Mapping[str, object], ...],
) -> tuple[tuple[bool, bool, bool], tuple[bool, bool, bool]]:
    singleton: list[bool] = []
    pair: list[bool] = []
    for intervention in ROLES:
        free = tuple(field for field in ROLES if field != intervention)
        buckets: dict[tuple[float, ...], set[float]] = {}
        for row in rows:
            key = (_probe(oracle, intervention, row), *(float(row[field]) for field in free))
            buckets.setdefault(key, set()).add(float(oracle(row)))
        singleton.append(any(len(targets) > 1 for targets in buckets.values()))
    for left, right in itertools.combinations(ROLES, 2):
        free = ({*ROLES} - {left, right}).pop()
        buckets = {}
        for row in rows:
            key = (_probe(oracle, left, row), _probe(oracle, right, row), float(row[free]))
            buckets.setdefault(key, set()).add(float(oracle(row)))
        pair.append(any(len(targets) > 1 for targets in buckets.values()))
    return tuple(singleton), tuple(pair)  # type: ignore[return-value]


def _case(ordered_fields: tuple[str, ...], field_to_role: Mapping[str, str]) -> dict[str, object]:
    role_to_field = {role: field for field, role in field_to_role.items()}
    if set(role_to_field) != set(ROLES):
        raise ValueError('each semantic role must occur exactly once')

    def encode(row: Mapping[str, float]) -> dict[str, float]:
        return {role_to_field[role]: float(row[role]) for role in ROLES}

    def oracle(row: Mapping[str, object]) -> float:
        semantic = {role: row[role_to_field[role]] for role in ROLES}
        return _cyclic(semantic)

    rows = tuple(encode(row) for row in _role_rows())
    discovery, validation, terminal, heldout = rows[:12], rows[12:18], rows[18:24], rows[24:30]
    need = OperatorInventionNeed(
        'R2.67.1 genuine three-probe causal necessity',
        ordered_fields,
        'out',
        constants=(0.0,),
        max_depth=4,
        max_candidates=50_000,
    )
    receipt = synthesize_three_probe_causal_program(
        oracle,
        ordered_fields,
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
    heldout_exact = 0
    if receipt.passed and receipt.expression is not None:
        heldout_exact = sum(
            int(float(evaluate_expr(receipt.expression, row)) == float(oracle(row)))
            for row in heldout
        )

    selected_roles: list[str] = []
    selected_semantic_ids: list[str] = []
    all_three_used = False
    no_full_triplet_smuggling = False
    lower_order_fail = False
    if selected is not None:
        selected_roles = sorted(
            field_to_role[ordered_fields[spec.bindings[0][0]]]
            for spec in selected.interventions
        )
        selected_semantic_ids = list(selected.semantic_profile_ids)
        all_three_used = {'__p0', '__p1', '__p2'} <= set(selected.used_fields)
        no_full_triplet_smuggling = selected.shared_positions == () and not {
            name for name in selected.used_fields if name.startswith('__f')
        }
        lower_order_fail = (
            selected.singleton_ablation_passed == (False, False, False)
            and selected.pair_ablation_passed == (False, False, False)
        )

    semantic_learning_rows = tuple(
        {role: float(row[role_to_field[role]]) for role in ROLES}
        for row in discovery + validation
    )
    singleton_collision, pair_collision = _collision_certificates(_cyclic, semantic_learning_rows)

    passed = bool(
        receipt.passed
        and selected is not None
        and selected_roles == list(ROLES)
        and all_three_used
        and no_full_triplet_smuggling
        and lower_order_fail
        and singleton_collision == (True, True, True)
        and pair_collision == (True, True, True)
        and receipt.probe_validation_cases == len(validation) * 3
        and receipt.probe_validation_exact == receipt.probe_validation_cases
        and receipt.terminal_probe_validation_cases == len(terminal) * 3
        and receipt.terminal_probe_validation_exact == receipt.terminal_probe_validation_cases
        and receipt.final_validation_exact == receipt.final_validation_cases == len(terminal)
        and heldout_exact == len(heldout)
        and receipt.structure.false_accepts == 0
        and receipt.trainable_parameter_count == 0
    )
    return {
        'passed': passed,
        'program_id': selected.program_id if selected is not None else None,
        'selected_roles': selected_roles,
        'selected_semantic_profile_ids': selected_semantic_ids,
        'semantic_profile_count': receipt.structure.semantic_profiles,
        'all_three_probes_used': all_three_used,
        'no_full_triplet_smuggling': no_full_triplet_smuggling,
        'singleton_collision_certificates': list(singleton_collision),
        'pair_collision_certificates': list(pair_collision),
        'all_lower_order_ablations_fail': lower_order_fail,
        'probe_validation_cases': receipt.probe_validation_cases,
        'probe_validation_exact': receipt.probe_validation_exact,
        'terminal_probe_validation_cases': receipt.terminal_probe_validation_cases,
        'terminal_probe_validation_exact': receipt.terminal_probe_validation_exact,
        'final_validation_cases': receipt.final_validation_cases,
        'final_validation_exact': receipt.final_validation_exact,
        'heldout_cases': len(heldout),
        'heldout_exact': heldout_exact,
        'oracle_calls_learning': receipt.structure.oracle_calls,
        'oracle_calls_total': receipt.oracle_calls_total,
        'false_accepts': receipt.structure.false_accepts,
        'trainable_parameter_count': receipt.trainable_parameter_count,
    }


def _triangle_min_stress() -> dict[str, object]:
    rows = _role_rows(TRIANGLE_MIN_ROWS)
    discovery, validation, terminal = rows[:12], rows[12:18], rows[18:24]
    singleton_collision, pair_collision = _collision_certificates(_triangle_min, discovery + validation)
    need = OperatorInventionNeed(
        'R2.67.1 triangle-min representation stress',
        ROLES,
        'out',
        constants=(0.0,),
        max_depth=4,
        max_candidates=50_000,
    )
    receipt = synthesize_three_probe_causal_program(
        _triangle_min,
        ROLES,
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
    passed = bool(
        receipt.passed
        and selected is not None
        and {'__p0', '__p1', '__p2'} <= set(selected.used_fields)
        and selected.shared_positions == ()
        and selected.singleton_ablation_passed == (False, False, False)
        and selected.pair_ablation_passed == (False, False, False)
        and singleton_collision == (True, True, True)
        and pair_collision == (True, True, True)
        and receipt.probe_validation_cases == len(validation) * 3
        and receipt.probe_validation_exact == receipt.probe_validation_cases
        and receipt.terminal_probe_validation_cases == len(terminal) * 3
        and receipt.terminal_probe_validation_exact == receipt.terminal_probe_validation_cases
        and receipt.final_validation_exact == receipt.final_validation_cases == len(terminal)
        and receipt.structure.false_accepts == 0
    )
    return {
        'passed': passed,
        'singleton_collision_certificates': list(singleton_collision),
        'pair_collision_certificates': list(pair_collision),
        'probe_validation_cases': receipt.probe_validation_cases,
        'probe_validation_exact': receipt.probe_validation_exact,
        'terminal_probe_validation_cases': receipt.terminal_probe_validation_cases,
        'terminal_probe_validation_exact': receipt.terminal_probe_validation_exact,
        'false_accepts': receipt.structure.false_accepts,
        'trainable_parameter_count': receipt.trainable_parameter_count,
    }


def run_benchmark() -> dict[str, object]:
    base = _case(ROLES, {role: role for role in ROLES})
    renamed_fields = ('u0', 'u1', 'u2')
    renamed = _case(renamed_fields, dict(zip(renamed_fields, ROLES, strict=True)))
    permutation = ('c', 'a', 'b')
    permuted = _case(permutation, {role: role for role in permutation})
    triangle_min = _triangle_min_stress()
    cases = (base, renamed, permuted)
    semantic_invariant = (
        base['selected_semantic_profile_ids']
        == renamed['selected_semantic_profile_ids']
        == permuted['selected_semantic_profile_ids']
    )
    all_gates_pass = bool(
        all(case['passed'] for case in cases)
        and triangle_min['passed']
        and semantic_invariant
        and sum(int(case['false_accepts']) for case in cases) == 0
    )
    return {
        'milestone': 'R2.67.1',
        'capability': 'certified-genuine-three-probe-causal-necessity',
        'all_gates_pass': all_gates_pass,
        'semantic_profile_invariant': semantic_invariant,
        'base': base,
        'renamed': renamed,
        'permuted': permuted,
        'triangle_min_representation_stress': triangle_min,
        'false_accepts': sum(int(case['false_accepts']) for case in cases),
        'trainable_parameter_count': 0,
    }
