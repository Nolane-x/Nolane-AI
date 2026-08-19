from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping, Sequence

from cogcoder.r256_operator_dsl import evaluate_expr
from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import synthesize_three_probe_causal_program


FIELDS = ('a', 'b', 'c')
ROWS = (
    # Discovery: explicit pair and singleton collision witnesses.
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
    (8.0, 3.0, 5.0), (-6.0, 4.0, 7.0),
    (9.0, -2.0, 6.0), (3.0, 8.0, -5.0),
    (-7.0, -4.0, 2.0), (5.0, -9.0, -3.0),
    # Challenge.
    (11.0, 2.0, 7.0), (-8.0, 5.0, 4.0),
    (6.0, -7.0, 3.0), (4.0, 9.0, -6.0),
    (-5.0, -3.0, 10.0), (12.0, -4.0, -2.0),
    # Heldout.
    (13.0, 5.0, 8.0), (-9.0, 6.0, 2.0),
    (7.0, -8.0, 4.0), (5.0, 11.0, -7.0),
    (-6.0, -5.0, 9.0), (14.0, 3.0, -4.0),
)


def _rows() -> tuple[dict[str, float], ...]:
    return tuple(dict(zip(FIELDS, values, strict=True)) for values in ROWS)


class _CountingDotOracle:
    def __init__(self, dot_callable: Callable[[object, object], object]) -> None:
        if not callable(dot_callable):
            raise TypeError('dot_callable must be callable')
        self._dot = dot_callable
        self.calls = 0

    def __call__(self, row: Mapping[str, object]) -> float:
        self.calls += 1
        a = float(row['a'])
        b = float(row['b'])
        c = float(row['c'])
        return float(self._dot([a, b, c], [b, c, a]))


def _probe(oracle: Callable[[Mapping[str, object]], object], field: str, row: Mapping[str, object]) -> float:
    changed = dict(row)
    changed[field] = 0.0
    return float(oracle(changed))


def _has_collision(keys: Sequence[tuple[float, ...]], targets: Sequence[float]) -> bool:
    seen: dict[tuple[float, ...], float] = {}
    for key, target in zip(keys, targets, strict=True):
        previous = seen.get(key)
        if previous is not None and previous != float(target):
            return True
        seen[key] = float(target)
    return False


def _collision_certificate_counts(
    oracle: Callable[[Mapping[str, object]], object],
    rows: Sequence[Mapping[str, object]],
) -> tuple[int, int]:
    targets = tuple(float(oracle(row)) for row in rows)
    probes = {
        field: tuple(_probe(oracle, field, row) for row in rows)
        for field in FIELDS
    }

    singleton = 0
    for intervention in FIELDS:
        free = tuple(field for field in FIELDS if field != intervention)
        keys = tuple(
            (probes[intervention][index], *(float(row[field]) for field in free))
            for index, row in enumerate(rows)
        )
        singleton += int(_has_collision(keys, targets))

    pair = 0
    for left, right in itertools.combinations(FIELDS, 2):
        free = next(field for field in FIELDS if field not in {left, right})
        keys = tuple(
            (probes[left][index], probes[right][index], float(row[free]))
            for index, row in enumerate(rows)
        )
        pair += int(_has_collision(keys, targets))
    return singleton, pair


def run_external_transfer(
    dot_callable: Callable[[object, object], object],
    *,
    source_id: str,
    source_version: str,
) -> dict[str, object]:
    oracle = _CountingDotOracle(dot_callable)
    rows = _rows()
    discovery, validation = rows[:12], rows[12:18]
    terminal, challenge, heldout = rows[18:24], rows[24:30], rows[30:36]

    need = OperatorInventionNeed(
        'R2.67.1 external cyclic dot three-probe necessity',
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
    engine_calls = oracle.calls
    engine_accounting_exact = engine_calls == receipt.oracle_calls_total

    cert_before = oracle.calls
    singleton_certs, pair_certs = _collision_certificate_counts(oracle, rows[:18])
    certificate_calls = oracle.calls - cert_before

    challenge_before = oracle.calls
    challenge_exact = 0
    if receipt.passed and receipt.expression is not None:
        challenge_exact = sum(
            int(float(evaluate_expr(receipt.expression, row)) == float(oracle(row)))
            for row in challenge
        )
    challenge_calls = oracle.calls - challenge_before

    heldout_before = oracle.calls
    heldout_exact = 0
    if receipt.passed and receipt.expression is not None:
        heldout_exact = sum(
            int(float(evaluate_expr(receipt.expression, row)) == float(oracle(row)))
            for row in heldout
        )
    heldout_calls = oracle.calls - heldout_before

    selected_roles = sorted(
        FIELDS[spec.bindings[0][0]]
        for spec in selected.interventions
    ) if selected is not None else []
    all_singletons_fail = bool(
        selected is not None and selected.singleton_ablation_passed == (False, False, False)
    )
    all_pairs_fail = bool(
        selected is not None and selected.pair_ablation_passed == (False, False, False)
    )
    all_three_used = bool(
        selected is not None and {'__p0', '__p1', '__p2'} <= set(selected.used_fields)
    )
    probe_units_ok = (
        receipt.probe_validation_cases == len(validation) * 3
        and receipt.probe_validation_exact == receipt.probe_validation_cases
        and receipt.terminal_probe_validation_cases == len(terminal) * 3
        and receipt.terminal_probe_validation_exact == receipt.terminal_probe_validation_cases
    )
    total_accounted = engine_calls + certificate_calls + challenge_calls + heldout_calls
    oracle_accounting_exact = engine_accounting_exact and oracle.calls == total_accounted

    passed = bool(
        receipt.passed
        and selected is not None
        and selected_roles == list(FIELDS)
        and singleton_certs == 3
        and pair_certs == 3
        and all_three_used
        and all_singletons_fail
        and all_pairs_fail
        and probe_units_ok
        and receipt.final_validation_exact == len(terminal)
        and challenge_exact == len(challenge)
        and heldout_exact == len(heldout)
        and receipt.structure.false_accepts == 0
        and receipt.trainable_parameter_count == 0
        and oracle_accounting_exact
    )
    return {
        'milestone': 'R2.67.1',
        'capability': 'genuine-three-probe-causal-necessity',
        'source_id': str(source_id),
        'source_version': str(source_version),
        'source_exposure': 'io_only',
        'host_selected_intervention': False,
        'passed': passed,
        'selected_roles': selected_roles,
        'semantic_profile_count': receipt.structure.semantic_profiles,
        'selected_semantic_profile_ids': list(selected.semantic_profile_ids) if selected is not None else [],
        'all_three_probes_used': all_three_used,
        'all_singleton_ablations_fail': all_singletons_fail,
        'all_pair_ablations_fail': all_pairs_fail,
        'singleton_collision_certificates': singleton_certs,
        'pair_collision_certificates': pair_certs,
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
        'oracle_calls_learning_terminal': engine_calls,
        'oracle_calls_collision_certificates': certificate_calls,
        'oracle_calls_challenge': challenge_calls,
        'oracle_calls_heldout': heldout_calls,
        'oracle_calls_total': oracle.calls,
        'oracle_accounting_exact': oracle_accounting_exact,
        'false_accepts': receipt.structure.false_accepts,
        'trainable_parameter_count': receipt.trainable_parameter_count,
    }
