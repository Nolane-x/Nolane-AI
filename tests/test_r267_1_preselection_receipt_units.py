from __future__ import annotations

from collections.abc import Mapping

from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import synthesize_three_probe_causal_program


FIELDS = ('x', 'y')
DISCOVERY = (
    {'x': 1.0, 'y': 2.0},
    {'x': 2.0, 'y': 3.0},
    {'x': 3.0, 'y': 5.0},
    {'x': 5.0, 'y': 8.0},
)
VALIDATION = (
    {'x': 8.0, 'y': 13.0},
    {'x': 13.0, 'y': 21.0},
)
TERMINAL = (
    {'x': 21.0, 'y': 34.0},
    {'x': 34.0, 'y': 55.0},
)


def _oracle(row: Mapping[str, object]) -> float:
    return float(row['x']) + float(row['y'])


def test_structure_failure_reports_zero_probe_observation_cases() -> None:
    """Before a triplet exists, no probe-validation observations exist.

    ``probe_validation_cases`` is an observation-count ledger.  Reporting the
    validation-context count here would mix context units with probe-observation
    units and make failed receipts incomparable with post-selection receipts.
    """
    need = OperatorInventionNeed(
        'R2.67.1 preselection receipt units',
        FIELDS,
        'out',
        constants=(0.0,),
        max_depth=3,
        max_candidates=10_000,
    )
    receipt = synthesize_three_probe_causal_program(
        _oracle,
        FIELDS,
        need,
        DISCOVERY,
        VALIDATION,
        terminal_contexts=TERMINAL,
        intervention_anchor_values=(0.0,),
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=2,
        composition_max_candidates_per_triplet=2_000,
        max_composition_candidates_total=4_000,
        ablation_max_candidates=2_000,
        composition_beam_width=32,
        probe_constants=(0.0,),
        probe_max_depth=2,
        probe_max_candidates=2_000,
        probe_beam_width=32,
    )

    assert receipt.passed is False
    assert receipt.structure.selected is None
    assert receipt.reason == 'structure_discovery_failed'
    assert receipt.probe_expressions == ()
    assert receipt.probe_validation_exact == 0
    assert receipt.probe_validation_cases == 0
