from __future__ import annotations

from collections.abc import Callable, Mapping

from cogcoder.r256_operator_dsl import evaluate_expr
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import synthesize_three_probe_causal_program


FIELDS = ('a', 'b', 'c', 'd', 'e', 'f')


def _nonzero_mod(index: int, multiplier: int, shift: int) -> float:
    value = ((index * multiplier + shift) % 29) - 14
    if value == 0:
        value = 15
    return float(value)


def _rows() -> tuple[dict[str, float], ...]:
    multipliers = (3, 5, 7, 11, 13, 17)
    shifts = (1, 4, 8, 2, 9, 6)
    out: list[dict[str, float]] = []
    for index in range(36):
        out.append({
            field: _nonzero_mod(index + offset * 3, multiplier, shift)
            for offset, (field, multiplier, shift) in enumerate(
                zip(FIELDS, multipliers, shifts, strict=True)
            )
        })
    return tuple(out)


def _oracle_from_dot(dot_callable: Callable[[object, object], object]):
    def oracle(row: Mapping[str, object]) -> float:
        left = [float(row['a']), float(row['c']), float(row['e'])]
        right = [float(row['b']), float(row['d']), float(row['f'])]
        return float(dot_callable(left, right))

    return oracle


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
    need = OperatorInventionNeed(
        'R2.67 external length-three dot composition',
        FIELDS,
        'out',
        constants=(0.0, 2.0),
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

    all_singletons_fail = bool(
        selected is not None and selected.singleton_ablation_passed == (False, False, False)
    )
    all_pairs_fail = bool(
        selected is not None and selected.pair_ablation_passed == (False, False, False)
    )
    all_three_used = bool(
        selected is not None
        and {'__p0', '__p1', '__p2'} <= set(selected.used_fields)
    )
    passed = bool(
        receipt.passed
        and selected is not None
        and all_three_used
        and all_singletons_fail
        and all_pairs_fail
        and challenge_exact == len(challenge)
        and heldout_exact == len(heldout)
        and receipt.structure.false_accepts == 0
        and receipt.trainable_parameter_count == 0
    )
    return {
        'milestone': 'R2.67',
        'capability': 'verified-three-probe-causal-composition',
        'source_id': str(source_id),
        'source_version': str(source_version),
        'source_exposure': 'io_only',
        'host_selected_intervention': False,
        'passed': passed,
        'semantic_profile_count': receipt.structure.semantic_profiles,
        'selected_semantic_profile_ids': list(selected.semantic_profile_ids) if selected is not None else [],
        'all_three_probes_used': all_three_used,
        'all_singleton_ablations_fail': all_singletons_fail,
        'all_pair_ablations_fail': all_pairs_fail,
        'selection_cases': selected.selection_cases if selected is not None else 0,
        'selection_exact': selected.selection_exact if selected is not None else 0,
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
        'composition_candidates': receipt.structure.composition_candidates_considered,
        'singleton_candidates': receipt.structure.singleton_candidates_considered,
        'pair_candidates': receipt.structure.pair_candidates_considered,
        'probe_candidates': list(receipt.probe_candidates_considered),
        'oracle_calls_learning': receipt.structure.oracle_calls,
        'oracle_calls_total': receipt.oracle_calls_total,
        'false_accepts': receipt.structure.false_accepts,
        'trainable_parameter_count': receipt.trainable_parameter_count,
    }
