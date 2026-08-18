from __future__ import annotations

import argparse
import json
from collections.abc import Mapping

from cogcoder.r258_intervention_discovery import PositionalSchema
from cogcoder.r267_three_probe_causal_composition import (
    _composition_examples,
    _synthesize_r267_expression,
    discover_three_probe_structure,
)


FIELDS = ('a', 'b', 'c', 'd', 'e', 'f')
CONFIGS = (
    (-7, -13, 4, -3, -10, -13),
    (7, 5, -12, 10, -6, 9),
    (-13, 8, 8, -12, 6, -9),
    (12, 7, 4, 2, -13, -3),
    (-3, -11, 7, 11, 10, -3),
    (-10, 5, 4, 9, -6, 6),
    (8, -3, 5, 2, -10, 3),
    (-11, -7, -3, -13, -7, -13),
    (11, 5, -5, -2, 8, 2),
    (5, -5, 9, 7, -6, -3),
    (12, -5, 11, -4, -2, 10),
    (-7, 9, 9, -9, -8, -7),
    (11, -10, -5, 11, -9, 4),
    (13, -8, 2, -6, -5, -12),
    (-5, 8, 11, 8, -9, 13),
    (10, -10, -9, 6, 12, -2),
    (6, -9, 4, 2, 9, -7),
    (8, -11, -13, -4, -11, -4),
)


def rows() -> tuple[dict[str, float], ...]:
    return tuple(
        {field: float(value) for field, value in zip(FIELDS, values, strict=True)}
        for values in CONFIGS
    )


def tri_bilinear(row: Mapping[str, object]) -> float:
    return (
        float(row['a']) * float(row['b'])
        + float(row['c']) * float(row['d'])
        + float(row['e']) * float(row['f'])
    )


def measure(cap: int) -> dict[str, object]:
    all_rows = rows()
    discovery = all_rows[:12]
    validation = all_rows[12:18]
    # Use the already-working full-triplet path only to identify the semantic
    # witness.  This measurement never authorizes a release or promotion.
    structure = discover_three_probe_structure(
        tri_bilinear,
        FIELDS,
        (0.0,),
        discovery,
        validation,
        intervention_arity=1,
        composition_constants=(0.0, 2.0),
        composition_max_depth=3,
        composition_max_candidates_per_triplet=35_000,
        max_composition_candidates_total=70_000,
        ablation_max_candidates=20_000,
        composition_beam_width=192,
    )
    if not structure.passed or structure.selected is None:
        raise RuntimeError(f'baseline witness unavailable: {structure.reason}')

    selected = structure.selected
    schema = PositionalSchema(FIELDS)
    selection_contexts = discovery + validation
    targets = tuple(tri_bilinear(row) for row in selection_contexts)
    shared_positions = selected.shared_positions

    measurements: list[dict[str, object]] = []
    subsets = ((0,), (1,), (2,), (0, 1), (0, 2), (1, 2))
    for subset in subsets:
        examples = _composition_examples(
            schema,
            selection_contexts,
            targets,
            selected.profiles,
            shared_positions,
            subset,
        )
        local_probe_fields = tuple(f'__p{index}' for index in range(len(subset)))
        fields = local_probe_fields + tuple(
            schema.canonical_fields[index] for index in shared_positions
        )
        receipt = _synthesize_r267_expression(
            fields,
            (0.0, 2.0),
            examples,
            max_depth=3,
            max_candidates=cap,
            beam_width=192,
        )
        measurements.append({
            'subset': list(subset),
            'passed': receipt.passed,
            'reason': receipt.reason,
            'candidates_considered': receipt.candidates_considered,
            'evaluations': receipt.evaluations,
            'semantic_candidates': receipt.semantic_candidates,
            'expression': None if receipt.expression is None else receipt.expression.to_data(),
        })

    return {
        'schema_version': 1,
        'milestone': 'R2.67-ablation-completion-measurement',
        'research_only_no_promotion_authority': True,
        'cap': cap,
        'baseline_structure_reason': structure.reason,
        'baseline_triplets_considered': structure.triplets_considered,
        'baseline_composition_candidates': structure.composition_candidates_considered,
        'semantic_profile_ids': list(selected.semantic_profile_ids),
        'shared_positions': list(shared_positions),
        'measurements': measurements,
        'all_lower_order_searches_conclusive': all(
            row['passed'] or 'budget_exhausted' not in str(row['reason'])
            for row in measurements
        ),
        'any_lower_order_exact': any(bool(row['passed']) for row in measurements),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--cap', type=int, required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.cap < 1:
        raise SystemExit('--cap must be positive')
    result = measure(args.cap)
    payload = json.dumps(result, sort_keys=True, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as handle:
            handle.write(payload + '\n')
    print(payload)


if __name__ == '__main__':
    main()
