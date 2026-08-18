from __future__ import annotations

from typing import Mapping

from cogcoder.r256_operator_dsl import evaluate_expr
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import synthesize_three_probe_causal_program


ROLES = ('a', 'b', 'c', 'd', 'e', 'f')
CONFIGS = (
    (-7, -13, 4, -3, -10, -13), (7, 5, -12, 10, -6, 9),
    (-13, 8, 8, -12, 6, -9), (12, 7, 4, 2, -13, -3),
    (-3, -11, 7, 11, 10, -3), (-10, 5, 4, 9, -6, 6),
    (8, -3, 5, 2, -10, 3), (-11, -7, -3, -13, -7, -13),
    (11, 5, -5, -2, 8, 2), (5, -5, 9, 7, -6, -3),
    (12, -5, 11, -4, -2, 10), (-7, 9, 9, -9, -8, -7),
    (11, -10, -5, 11, -9, 4), (13, -8, 2, -6, -5, -12),
    (-5, 8, 11, 8, -9, 13), (10, -10, -9, 6, 12, -2),
    (6, -9, 4, 2, 9, -7), (8, -11, -13, -4, -11, -4),
    (-4, 9, -12, 13, -12, -5), (-10, -13, 10, 11, -10, -7),
    (4, 9, 2, -2, 4, 13), (13, 9, 6, -6, 4, 12),
    (13, -5, -6, 3, -11, 9), (-6, 11, 13, -9, -3, -10),
    (9, -6, -11, -7, -6, -8), (8, 11, 11, 10, -11, 10),
    (9, -11, 12, 4, -2, -10), (4, -11, -5, 10, 13, 6),
    (3, 6, 3, -6, 2, 13), (5, 4, 7, -2, -7, 3),
)


def _role_rows() -> tuple[dict[str, float], ...]:
    return tuple(
        {role: float(value) for role, value in zip(ROLES, values, strict=True)}
        for values in CONFIGS
    )


def _tri_bilinear(row: Mapping[str, object]) -> float:
    return (
        float(row['a']) * float(row['b'])
        + float(row['c']) * float(row['d'])
        + float(row['e']) * float(row['f'])
    )


def _case(ordered_fields: tuple[str, ...], field_to_role: Mapping[str, str]) -> dict[str, object]:
    role_to_field = {role: field for field, role in field_to_role.items()}
    if set(role_to_field) != set(ROLES):
        raise ValueError('each semantic role must occur exactly once')

    def encode(row: Mapping[str, float]) -> dict[str, float]:
        return {role_to_field[role]: float(row[role]) for role in ROLES}

    def oracle(row: Mapping[str, object]) -> float:
        semantic = {role: row[role_to_field[role]] for role in ROLES}
        return _tri_bilinear(semantic)

    rows = tuple(encode(row) for row in _role_rows())
    discovery, validation, terminal, heldout = rows[:12], rows[12:18], rows[18:24], rows[24:30]
    need = OperatorInventionNeed(
        'R2.67 authored three-probe causal composition',
        ordered_fields,
        'out',
        constants=(0.0, 2.0),
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
        composition_constants=(0.0, 2.0),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=35_000,
        max_composition_candidates_total=70_000,
        ablation_max_candidates=20_000,
        composition_beam_width=192,
        probe_constants=(0.0,),
        probe_max_depth=2,
        probe_max_candidates=30_000,
        probe_beam_width=160,
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

    return {
        'passed': bool(receipt.passed and heldout_exact == len(heldout)),
        'program_id': program_id,
        'selected_semantic_profile_ids': selected_semantic_ids,
        'selected_roles': selected_roles,
        'semantic_profile_count': receipt.structure.semantic_profiles,
        'all_three_probes_used': all_three_used,
        'no_smuggling': no_smuggling,
        'all_singleton_ablations_fail': singleton_ablations_fail,
        'all_pair_ablations_fail': pair_ablations_fail,
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

    renamed_fields = ('u0', 'u1', 'u2', 'u3', 'u4', 'u5')
    renamed = _case(renamed_fields, dict(zip(renamed_fields, ROLES, strict=True)))

    permutation = ('f', 'a', 'd', 'c', 'b', 'e')
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
        and all(case['all_three_probes_used'] for case in cases)
        and all(case['no_smuggling'] for case in cases)
        and all(case['all_singleton_ablations_fail'] for case in cases)
        and all(case['all_pair_ablations_fail'] for case in cases)
        and all(case['false_accepts'] == 0 for case in cases)
        and all(case['trainable_parameter_count'] == 0 for case in cases)
        and semantic_invariant
    )
    return {
        'milestone': 'R2.67',
        'capability': 'verified-three-probe-causal-composition',
        'all_gates_pass': all_gates_pass,
        'semantic_profile_invariant': semantic_invariant,
        'base': base,
        'renamed': renamed,
        'permuted': permuted,
        'false_accepts': sum(int(case['false_accepts']) for case in cases),
        'trainable_parameter_count': 0,
    }
