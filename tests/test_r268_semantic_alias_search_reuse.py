from __future__ import annotations

import cogcoder._r268_runtime as runtime
from cogcoder._r268_search import ExpressionSearchReceipt


def test_discovery_equivalent_authority_aliases_share_one_proposal_search(monkeypatch) -> None:
    calls: list[tuple[tuple[str, ...], tuple[tuple[object, ...], ...]]] = []

    # Isolate proposal scheduling: every authority basis is search-eligible,
    # while synthesis deterministically misses after one charged candidate.
    monkeypatch.setattr(runtime, 'build_basis_collision_certificate', lambda **kwargs: None)

    def failed_search(field_names, required_probe_fields, constants, examples, **kwargs):
        signature = (
            tuple(field_names),
            tuple(tuple(row.context[name] for name in field_names) for row in examples),
        )
        calls.append(signature)
        return ExpressionSearchReceipt(False, None, 1, 1, 0, 'forced_search_miss')

    monkeypatch.setattr(runtime, 'synthesize_variable_expression', failed_search)

    discovery = (
        {'a': -2.0, 'b': -2.0},
        {'a': -2.0, 'b': -1.0},
        {'a': -1.0, 'b': -2.0},
        {'a': 1.0, 'b': 3.0},
        {'a': 4.0, 'b': -2.0},
        {'a': 5.0, 'b': 7.0},
    )
    validation = (
        {'a': 2.0, 'b': 5.0},
        {'a': -3.0, 'b': 6.0},
        {'a': 8.0, 'b': -4.0},
    )

    receipt = runtime.discover_adaptive_causal_basis(
        lambda row: abs(float(row['a'])) + abs(float(row['b'])),
        ('a', 'b'),
        (-1.0, 1.0),
        discovery,
        validation,
        intervention_arity=1,
        max_basis_size=1,
        composition_constants=(0.0, 2.0),
        composition_max_depth=5,
        composition_max_candidates_per_basis=8,
        max_composition_candidates_total=8,
        composition_beam_width=32,
    )

    assert receipt.legal_interventions == 4
    assert receipt.semantic_profiles == 4
    # Two discovery-equivalent proposal classes: intervene on a, intervene on b.
    # Four authority identities remain, but finite synthesis is paid once per
    # discovery-equivalence class, never once per alias identity.
    assert len(calls) == 2
    assert len(set(calls)) == 2
    assert receipt.composition_candidates_considered == 2
