from __future__ import annotations

from dataclasses import dataclass

from benchmarks.kfigg.r257_verified_vocabulary_growth import build_promoted_vocabulary
from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r257_vocabulary import evaluate_with_vocabulary
from cogcoder.r258_intervention_discovery import PositionalSchema, discover_causal_intervention


_ROLES = ('x', 'a', 'b', 'fa', 'fb')

_PROBE_TRAIN_CASES = (
    (-4.0, 0.0, 8.0, 2.0, 10.0),
    (0.0, 0.0, 8.0, -3.0, 5.0),
    (2.0, 0.0, 8.0, 7.0, 15.0),
    (4.0, 0.0, 8.0, -8.0, 4.0),
    (6.0, 0.0, 8.0, 9.0, 17.0),
    (8.0, 0.0, 8.0, -1.0, 3.0),
    (12.0, 0.0, 8.0, 11.0, 19.0),
    (-6.0, -4.0, 4.0, -2.0, 6.0),
    (0.0, -4.0, 4.0, 3.0, 11.0),
    (6.0, -4.0, 4.0, -5.0, 7.0),
)

_PROBE_VALID_CASES = (
    (-6.0, -4.0, 4.0, 3.0, 9.0),
    (-2.0, -4.0, 4.0, -7.0, 13.0),
    (2.0, -4.0, 4.0, 5.0, 21.0),
    (8.0, -4.0, 4.0, 2.0, 12.0),
)

_DOWNSTREAM_TRAIN_CASES = (
    (-4.0, 0.0, 8.0, 2.0, 10.0), (0.0, 0.0, 8.0, 2.0, 10.0),
    (2.0, 0.0, 8.0, 2.0, 10.0), (4.0, 0.0, 8.0, 2.0, 10.0),
    (6.0, 0.0, 8.0, 2.0, 10.0), (8.0, 0.0, 8.0, 2.0, 10.0),
    (12.0, 0.0, 8.0, 2.0, 10.0), (0.0, -4.0, 4.0, -2.0, 6.0),
)


@dataclass(frozen=True, slots=True)
class _OpaqueConfiguration:
    name: str
    field_names: tuple[str, ...]
    role_order: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.field_names) != len(_ROLES) or len(set(self.field_names)) != len(_ROLES):
            raise ValueError('configuration must contain five distinct field names')
        if set(self.role_order) != set(_ROLES) or len(self.role_order) != len(_ROLES):
            raise ValueError('role_order must be a permutation of the five latent roles')

    @property
    def role_to_field(self) -> dict[str, str]:
        return {role: field for field, role in zip(self.field_names, self.role_order, strict=True)}

    @property
    def endpoint_positions(self) -> frozenset[int]:
        return frozenset(index for index, role in enumerate(self.role_order) if role in {'fa', 'fb'})


def _linearstep(values: dict[str, float]) -> float:
    x = float(values['x'])
    a = float(values['a'])
    b = float(values['b'])
    fa = float(values['fa'])
    fb = float(values['fb'])
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return fa + t * (fb - fa)


def _context(config: _OpaqueConfiguration, case: tuple[float, float, float, float, float]) -> dict[str, float]:
    role_values = dict(zip(_ROLES, case, strict=True))
    return {field: float(role_values[role]) for field, role in zip(config.field_names, config.role_order, strict=True)}


def _oracle(config: _OpaqueConfiguration):
    role_to_field = config.role_to_field

    def call(context):
        values = {role: float(context[field]) for role, field in role_to_field.items()}
        return _linearstep(values)

    return call


def _downstream_examples(config: _OpaqueConfiguration) -> tuple[OperatorExample, ...]:
    oracle = _oracle(config)
    return tuple(
        OperatorExample(f'{config.name}:downstream:{index}', _context(config, case), oracle(_context(config, case)))
        for index, case in enumerate(_DOWNSTREAM_TRAIN_CASES)
    )


def _run_configuration(config: _OpaqueConfiguration):
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    downstream_need = OperatorInventionNeed(
        f'{config.name}:opaque-full',
        config.field_names,
        'out',
        constants=(0, 1),
        max_depth=3,
        max_candidates=1000,
    )
    receipt = discover_causal_intervention(
        _oracle(config),
        config.field_names,
        (0.0, 1.0),
        tuple(_context(config, case) for case in _PROBE_TRAIN_CASES),
        tuple(_context(config, case) for case in _PROBE_VALID_CASES),
        vocabulary,
        downstream_need,
        _downstream_examples(config),
        probe_max_depth=2,
        probe_max_candidates=4200,
    )
    return receipt


def _replay_under_rename(
    source_config: _OpaqueConfiguration,
    target_config: _OpaqueConfiguration,
    source_receipt,
) -> dict[str, object]:
    if not source_receipt.passed or source_receipt.selected is None:
        return {'passed': False, 'probe_exact': 0, 'probe_cases': len(_PROBE_VALID_CASES), 'downstream_exact': 0}
    selected = source_receipt.selected
    if selected.probe_expression is None or selected.seeded_downstream_expression is None:
        return {'passed': False, 'probe_exact': 0, 'probe_cases': len(_PROBE_VALID_CASES), 'downstream_exact': 0}

    source_schema = PositionalSchema(source_config.field_names)
    target_schema = PositionalSchema(target_config.field_names)
    canonical_probe = source_schema.canonicalize_expr(selected.probe_expression)
    canonical_full = source_schema.canonicalize_expr(selected.seeded_downstream_expression)
    target_probe = target_schema.externalize_expr(canonical_probe)
    target_full = target_schema.externalize_expr(canonical_full)
    vocabulary, _lifecycle, _selected = build_promoted_vocabulary()
    oracle = _oracle(target_config)

    probe_exact = 0
    for case in _PROBE_VALID_CASES:
        context = _context(target_config, case)
        applied = selected.intervention.apply(context, target_config.field_names)
        actual = evaluate_with_vocabulary(target_probe, applied, vocabulary)
        expected = oracle(applied)
        probe_exact += int(abs(float(actual) - float(expected)) <= 1e-12)

    downstream = _downstream_examples(target_config)
    downstream_exact = 0
    for row in downstream:
        actual = evaluate_with_vocabulary(target_full, row.context, vocabulary)
        downstream_exact += int(abs(float(actual) - float(row.expected)) <= 1e-12)

    return {
        'passed': bool(probe_exact == len(_PROBE_VALID_CASES) and downstream_exact == len(downstream)),
        'probe_exact': probe_exact,
        'probe_cases': len(_PROBE_VALID_CASES),
        'downstream_exact': downstream_exact,
        'downstream_cases': len(downstream),
        'intervention_id': selected.intervention.intervention_id,
        'position_set': frozenset(position for position, _value in selected.intervention.bindings),
    }


def _candidate_audit(config: _OpaqueConfiguration, receipt) -> tuple[int, int]:
    wrong_role_false_accepts = 0
    noncausal_rejected = 0
    for candidate in receipt.candidates:
        positions = frozenset(position for position, _value in candidate.intervention.bindings)
        if candidate.passed and positions != config.endpoint_positions:
            wrong_role_false_accepts += 1
        if candidate.reason == 'no_causal_downstream_gain':
            noncausal_rejected += 1
    return wrong_role_false_accepts, noncausal_rejected


def run_benchmark_part(part: str) -> dict[str, object]:
    part = str(part).strip().lower()
    if part == 'rename':
        rename_a = _OpaqueConfiguration('rename-a', ('q7', 'q2', 'q9', 'q4', 'q1'), _ROLES)
        rename_b = _OpaqueConfiguration('rename-b', ('zeta', 'theta', 'mu', 'rho', 'eta'), _ROLES)
        receipt_a = _run_configuration(rename_a)
        replay_b = _replay_under_rename(rename_a, rename_b, receipt_a)
        selected = receipt_a.selected
        wrong, noncausal = _candidate_audit(rename_a, receipt_a)
        selected_id = selected.intervention.intervention_id if selected is not None else ''
        selected_positions = sorted(position for position, _value in selected.intervention.bindings) if selected is not None else []
        replay_positions = sorted(replay_b.get('position_set', frozenset()))
        return {
            'part': 'rename',
            'discovered': int(receipt_a.passed) + int(bool(replay_b.get('passed'))),
            'no_seed_failures': 2 * int(not receipt_a.no_seed_passed),
            'seeded_successes': int(selected is not None and selected.seeded_downstream_passed) + int(bool(replay_b.get('passed'))),
            'probe_validation_exact': (selected.probe_validation_exact if selected is not None else 0) + int(replay_b.get('probe_exact', 0)),
            'probe_validation_cases': (selected.probe_validation_cases if selected is not None else len(_PROBE_VALID_CASES)) + int(replay_b.get('probe_cases', len(_PROBE_VALID_CASES))),
            'position_rename_invariant': bool(
                selected_id
                and selected_id == str(replay_b.get('intervention_id', ''))
                and selected_positions == replay_positions
            ),
            'wrong_role_false_accepts': wrong,
            'noncausal_candidates_rejected': noncausal,
            'selected_intervention_ids': [selected_id, str(replay_b.get('intervention_id', ''))],
            'selected_position_sets': [selected_positions, replay_positions],
            'oracle_calls': receipt_a.oracle_calls + len(_DOWNSTREAM_TRAIN_CASES) + int(replay_b.get('probe_cases', 0)) + int(replay_b.get('downstream_cases', 0)),
            'synthesis_candidates_considered': receipt_a.synthesis_candidates_considered,
        }
    if part == 'reordered':
        reordered = _OpaqueConfiguration('reordered', ('k0', 'k1', 'k2', 'k3', 'k4'), ('fa', 'x', 'fb', 'a', 'b'))
        receipt = _run_configuration(reordered)
        selected = receipt.selected
        selected_positions = sorted(position for position, _value in selected.intervention.bindings) if selected is not None else []
        wrong, noncausal = _candidate_audit(reordered, receipt)
        return {
            'part': 'reordered',
            'discovered': int(receipt.passed),
            'no_seed_failures': int(not receipt.no_seed_passed),
            'seeded_successes': int(selected is not None and selected.seeded_downstream_passed),
            'probe_validation_exact': selected.probe_validation_exact if selected is not None else 0,
            'probe_validation_cases': selected.probe_validation_cases if selected is not None else len(_PROBE_VALID_CASES),
            'argument_permutation_tracks_roles': bool(set(selected_positions) == set(reordered.endpoint_positions)),
            'wrong_role_false_accepts': wrong,
            'noncausal_candidates_rejected': noncausal,
            'selected_intervention_ids': [selected.intervention.intervention_id if selected is not None else ''],
            'selected_position_sets': [selected_positions],
            'oracle_calls': receipt.oracle_calls + len(_DOWNSTREAM_TRAIN_CASES),
            'synthesis_candidates_considered': receipt.synthesis_candidates_considered,
        }
    raise ValueError('benchmark part must be rename or reordered')


def merge_benchmark_parts(rename: dict[str, object], reordered: dict[str, object]) -> dict[str, object]:
    if rename.get('part') != 'rename' or reordered.get('part') != 'reordered':
        raise ValueError('expected rename and reordered benchmark parts')
    return {
        'milestone': 'R2.58',
        'capability': 'autonomous-bounded-intervention-discovery',
        'claim_boundary': 'Bounded pure-input intervention search with causal downstream utility; not open-ended experiment or representation invention.',
        'configurations': 3,
        'full_search_configurations': 2,
        'rename_replay_configurations': 1,
        'discovered': int(rename['discovered']) + int(reordered['discovered']),
        'no_seed_failures': int(rename['no_seed_failures']) + int(reordered['no_seed_failures']),
        'seeded_successes': int(rename['seeded_successes']) + int(reordered['seeded_successes']),
        'probe_validation_exact': int(rename['probe_validation_exact']) + int(reordered['probe_validation_exact']),
        'probe_validation_cases': int(rename['probe_validation_cases']) + int(reordered['probe_validation_cases']),
        'position_rename_invariant': bool(rename['position_rename_invariant']),
        'argument_permutation_tracks_roles': bool(reordered['argument_permutation_tracks_roles']),
        'selected_position_sets': list(rename['selected_position_sets']) + list(reordered['selected_position_sets']),
        'selected_intervention_ids': list(rename['selected_intervention_ids']) + list(reordered['selected_intervention_ids']),
        'wrong_role_false_accepts': int(rename['wrong_role_false_accepts']) + int(reordered['wrong_role_false_accepts']),
        'noncausal_candidates_rejected': int(rename['noncausal_candidates_rejected']) + int(reordered['noncausal_candidates_rejected']),
        'oracle_calls': int(rename['oracle_calls']) + int(reordered['oracle_calls']),
        'synthesis_candidates_considered': int(rename['synthesis_candidates_considered']) + int(reordered['synthesis_candidates_considered']),
        'trainable_parameter_count': 0,
    }


def run_benchmark() -> dict[str, object]:
    return merge_benchmark_parts(run_benchmark_part('rename'), run_benchmark_part('reordered'))


if __name__ == '__main__':
    import json
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
