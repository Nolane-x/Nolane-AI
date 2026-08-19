from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping, Sequence

from cogcoder.r256_operator_dsl import evaluate_expr
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import synthesize_three_probe_causal_program


ROLES = ('a', 'b', 'c')
CONFIGS = (
    # Pair-collision witnesses.
    (1.0, 2.0, 0.0), (2.0, 3.0, 0.0),
    (1.0, 0.0, 2.0), (2.0, 0.0, 3.0),
    (0.0, 1.0, 2.0), (0.0, 2.0, 3.0),
    # Singleton-collision witnesses.
    (1.0, 2.0, 3.0), (4.0, 2.0, 3.0),
    (2.0, 1.0, 3.0), (2.0, 4.0, 3.0),
    (2.0, 3.0, 1.0), (2.0, 3.0, 4.0),
    # Independent validation rows.
    (-2.0, 5.0, 3.0), (4.0, -3.0, 2.0),
    (5.0, 2.0, -4.0), (-3.0, -2.0, 6.0),
    (7.0, -1.0, -5.0), (-4.0, 6.0, -2.0),
    # Independent terminal rows.  Each base row and each zero-intervention
    # variant is disjoint from every learning query and from the other terminal
    # evidence keys.
    (101.0, 103.0, 107.0), (-109.0, 113.0, 127.0),
    (131.0, -137.0, 139.0), (149.0, 151.0, -157.0),
    (-163.0, -167.0, 173.0), (179.0, -181.0, -191.0),
    # Heldout rows never used for learning or terminal authority.
    (11.0, 2.0, 7.0), (-8.0, 5.0, 4.0),
    (6.0, -7.0, 3.0), (4.0, 9.0, -6.0),
    (-5.0, -3.0, 10.0), (12.0, -4.0, -2.0),
)


def _role_rows() -> tuple[dict[str, float], ...]:
    return tuple(dict(zip(ROLES, values, strict=True)) for values in CONFIGS)


def _cyclic(row: Mapping[str, object]) -> float:
    a = float(row['a'])
    b = float(row['b'])
    c = float(row['c'])
    return a * b + b * c + c * a


def _probe(
    oracle: Callable[[Mapping[str, object]], object],
    field: str,
    row: Mapping[str, object],
) -> float:
    changed = dict(row)
    changed[field] = 0.0
    return float(oracle(changed))


def _has_collision(keys: Sequence[tuple[object, ...]], targets: Sequence[float]) -> bool:
    seen: dict[tuple[object, ...], float] = {}
    for key, target in zip(keys, targets, strict=True):
        previous = seen.get(key)
        if previous is not None and previous != float(target):
            return True
        seen[key] = float(target)
    return False


def _collision_certificate_counts(
    rows: Sequence[Mapping[str, object]],
    oracle: Callable[[Mapping[str, object]], object],
) -> tuple[int, int]:
    targets = tuple(float(oracle(row)) for row in rows)
    probe_values = {
        field: tuple(_probe(oracle, field, row) for row in rows)
        for field in ROLES
    }

    singleton = 0
    for intervention in ROLES:
        free = tuple(field for field in ROLES if field != intervention)
        keys = tuple(
            (probe_values[intervention][index], *(float(row[field]) for field in free))
            for index, row in enumerate(rows)
        )
        singleton += int(_has_collision(keys, targets))

    pair = 0
    for left, right in itertools.combinations(ROLES, 2):
        free = next(field for field in ROLES if field not in {left, right})
        keys = tuple(
            (probe_values[left][index], probe_values[right][index], float(row[free]))
            for index, row in enumerate(rows)
        )
        pair += int(_has_collision(keys, targets))
    return singleton, pair


def _case(ordered_fields: tuple[str, ...], field_to_role: Mapping[str, str]) -> dict[str, object]:
    role_to_field = {role: field for field, role in field_to_role.items()}
    if set(role_to_field) != set(ROLES):
        raise ValueError('each semantic role must occur exactly once')

    def encode(row: Mapping[str, float]) -> dict[str, float]:
        return {role_to_field[role]: float(row[role]) for role in ROLES}

    def oracle(row: Mapping[str, object]) -> float:
        semantic = {role: row[role_to_field[role]] for role in ROLES}
        return _cyclic(semantic)

    semantic_rows = _role_rows()
    rows = tuple(encode(row) for row in semantic_rows)
    discovery, validation, terminal, heldout = rows[:12], rows[12:18], rows[18:24], rows[24:30]
    singleton_certs, pair_certs = _collision_certificate_counts(semantic_rows[:18], _cyclic)

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

    selected_semantic_ids: list[str] = []
    selected_roles: list[str] = []
    all_three_used = False
    no_smuggling = False
    singleton_ablations_fail = False
    pair_ablations_fail = False
    program_id = None
    if selected is not None:
        selected_semantic_ids = list(selected.semantic_profile_ids)
        selected_roles = sorted(
            field_to_role[ordered_fields[spec.bindings[0][0]]]
            for spec in selected.interventions
        )
        used = set(selected.used_fields)
        all_three_used = {'__p0', '__p1', '__p2'} <= used
        fixed_positions = {
            position
            for spec in selected.interventions
            for position, _value in spec.bindings
        }
        canonical_shared = {f'__f{position}' for position in selected.shared_positions}
        used_original = {name for name in used if name.startswith('__f')}
        no_smuggling = (
            used_original <= canonical_shared
            and set(selected.shared_positions).isdisjoint(fixed_positions)
        )
        singleton_ablations_fail = selected.singleton_ablation_passed == (False, False, False)
        pair_ablations_fail = selected.pair_ablation_passed == (False, False, False)
        program_id = selected.program_id

    probe_units_ok = (
        receipt.probe_validation_cases == len(validation) * 3
        and receipt.probe_validation_exact == receipt.probe_validation_cases
        and receipt.terminal_probe_validation_cases == len(terminal) * 3
        and receipt.terminal_probe_validation_exact == receipt.terminal_probe_validation_cases
    )
    passed = bool(
        receipt.passed
        and selected is not None
        and selected_roles == list(ROLES)
        and singleton_certs == 3
        and pair_certs == 3
        and all_three_used
        and no_smuggling
        and singleton_ablations_fail
        and pair_ablations_fail
        and probe_units_ok
        and receipt.final_validation_exact == len(terminal)
        and heldout_exact == len(heldout)
        and receipt.structure.false_accepts == 0
        and receipt.trainable_parameter_count == 0
    )

    return {
        'passed': passed,
        'program_id': program_id,
        'selected_semantic_profile_ids': selected_semantic_ids,
        'selected_roles': selected_roles,
        'semantic_profile_count': receipt.structure.semantic_profiles,
        'all_three_probes_used': all_three_used,
        'no_smuggling': no_smuggling,
        'all_singleton_ablations_fail': singleton_ablations_fail,
        'all_pair_ablations_fail': pair_ablations_fail,
        'singleton_collision_certificates': singleton_certs,
        'pair_collision_certificates': pair_certs,
        'selection_cases': selected.selection_cases if selected is not None else 0,
        'selection_exact': selected.selection_exact if selected is not None else 0,
        'composition_candidates': receipt.structure.composition_candidates_considered,
        'singleton_candidates': receipt.structure.singleton_candidates_considered,
        'pair_candidates': receipt.structure.pair_candidates_considered,
        'probe_candidates': list(receipt.probe_candidates_considered),
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


def run_benchmark() -> dict[str, object]:
    base = _case(ROLES, {role: role for role in ROLES})

    renamed_fields = ('u0', 'u1', 'u2')
    renamed = _case(renamed_fields, dict(zip(renamed_fields, ROLES, strict=True)))

    permutation = ('c', 'a', 'b')
    permuted = _case(permutation, {role: role for role in permutation})
    cases = (base, renamed, permuted)

    semantic_invariant = (
        base['selected_semantic_profile_ids']
        == renamed['selected_semantic_profile_ids']
        == permuted['selected_semantic_profile_ids']
    )
    all_gates_pass = bool(
        all(case['passed'] for case in cases)
        and all(case['semantic_profile_count'] == 3 for case in cases)
        and all(case['singleton_collision_certificates'] == 3 for case in cases)
        and all(case['pair_collision_certificates'] == 3 for case in cases)
        and all(case['false_accepts'] == 0 for case in cases)
        and all(case['trainable_parameter_count'] == 0 for case in cases)
        and semantic_invariant
    )
    return {
        'milestone': 'R2.67.1',
        'capability': 'genuine-three-probe-causal-necessity',
        'all_gates_pass': all_gates_pass,
        'semantic_profile_invariant': semantic_invariant,
        'base': base,
        'renamed': renamed,
        'permuted': permuted,
        'false_accepts': sum(int(case['false_accepts']) for case in cases),
        'trainable_parameter_count': 0,
    }
