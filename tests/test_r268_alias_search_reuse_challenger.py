from __future__ import annotations

import cogcoder._r268_runtime as runtime
from cogcoder._r268_search import ExpressionSearchReceipt


FIELDS = ('a', 'b')
DISCOVERY = (
    {'a': -2.0, 'b': -2.0},
    {'a': -2.0, 'b': -1.0},
    {'a': -1.0, 'b': -2.0},
    {'a': 1.0, 'b': 3.0},
    {'a': 4.0, 'b': -2.0},
    {'a': 5.0, 'b': 7.0},
)
VALIDATION = (
    {'a': 2.0, 'b': 5.0},
    {'a': -3.0, 'b': 6.0},
    {'a': 8.0, 'b': -4.0},
)


def _oracle(row) -> float:
    return abs(float(row['a'])) + abs(float(row['b']))


def test_discovery_equivalent_aliases_search_each_proposal_class_once(monkeypatch) -> None:
    calls = 0

    def forced_miss(field_names, required_probe_fields, constants, examples, **kwargs):
        nonlocal calls
        calls += 1
        return ExpressionSearchReceipt(False, None, 1, 1, 1, 'synthetic_search_miss')

    monkeypatch.setattr(runtime, 'synthesize_variable_expression', forced_miss)

    def run(anchors: tuple[float, ...]):
        nonlocal calls
        calls = 0
        receipt = runtime.discover_adaptive_causal_basis(
            _oracle,
            FIELDS,
            anchors,
            DISCOVERY,
            VALIDATION,
            intervention_arity=1,
            max_basis_size=2,
            composition_constants=(0.0, 2.0),
            composition_max_depth=5,
            composition_max_candidates_per_basis=64,
            max_composition_candidates_total=64,
            composition_beam_width=128,
        )
        return calls, receipt

    control_calls, control = run((-1.0,))
    aliased_calls, aliased = run((-1.0, 1.0))

    # Adding an authority-distinct anchor whose discovery behavior is identical
    # must enlarge the proof universe, not the number of proposal searches.
    assert control.legal_interventions == 2
    assert aliased.legal_interventions == 4
    assert aliased.semantic_profiles == 4
    assert control_calls > 0
    assert aliased_calls == control_calls
    assert aliased.composition_candidates_considered == control.composition_candidates_considered
