from __future__ import annotations

from cogcoder.r256_operator_invention import OperatorInventionNeed
import cogcoder._r268_runtime as runtime


FIELDS = ('a', 'b')


def _contexts(rows):
    return tuple(dict(zip(FIELDS, row, strict=True)) for row in rows)


def test_composition_candidate_selection_must_not_consume_validation_rows(monkeypatch) -> None:
    """The design promises composition selection followed by disjoint validation.

    This challenger records only synthesis calls that require probe fields, i.e.
    causal-composition candidate selection rather than later probe-expression
    fitting.  Those calls must receive discovery rows only.  Validation rows may
    be used after a composition is selected, but must not influence candidate
    generation/ranking.
    """
    discovery_rows = ((-2, -2), (-2, -1), (-1, -2), (1, 3), (4, -2), (5, 7))
    validation_rows = ((2, 5), (-3, 6), (8, -4))
    terminal_rows = ((101, 103), (-109, 113), (127, -131))

    composition_training_case_counts: list[int] = []
    original = runtime.synthesize_variable_expression

    def recording_synthesizer(field_names, required_probe_fields, constants, examples, **kwargs):
        if tuple(required_probe_fields):
            composition_training_case_counts.append(len(tuple(examples)))
        return original(field_names, required_probe_fields, constants, examples, **kwargs)

    monkeypatch.setattr(runtime, 'synthesize_variable_expression', recording_synthesizer)

    need = OperatorInventionNeed(
        'R2.68 independent composition holdout challenger',
        FIELDS,
        'out',
        constants=(0.0, 2.0),
        max_depth=5,
        max_candidates=120_000,
    )

    def oracle(row):
        return float(row['a']) + float(row['b'])

    receipt = runtime.synthesize_adaptive_causal_basis(
        oracle,
        FIELDS,
        need,
        _contexts(discovery_rows),
        _contexts(validation_rows),
        terminal_contexts=_contexts(terminal_rows),
        intervention_anchor_values=(0.0,),
        intervention_arity=1,
        max_basis_size=2,
        composition_constants=(0.0, 2.0),
        composition_max_depth=5,
        composition_max_candidates_per_basis=30_000,
        max_composition_candidates_total=160_000,
        composition_beam_width=192,
        probe_constants=(0.0, 2.0),
        probe_max_depth=5,
        probe_max_candidates=50_000,
        probe_beam_width=192,
    )

    assert receipt.passed is True
    assert composition_training_case_counts
    assert set(composition_training_case_counts) == {len(discovery_rows)}, (
        'composition candidate selection consumed non-discovery evidence',
        composition_training_case_counts,
        len(discovery_rows),
        len(validation_rows),
    )
