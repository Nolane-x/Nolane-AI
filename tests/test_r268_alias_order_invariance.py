from __future__ import annotations

from cogcoder._r268_search import ExpressionSearchReceipt
from cogcoder._r268_types import BasisCollisionCertificate
import cogcoder._r268_runtime as runtime


DISCOVERY = (
    {'a': -2.0, 'b': -2.0},
    {'a': -1.0, 'b': -1.0},
    {'a': 1.0, 'b': 1.0},
    {'a': 2.0, 'b': 2.0},
)
VALIDATION = (
    {'a': 5.0, 'b': 7.0},
    {'a': 7.0, 'b': 11.0},
    {'a': 11.0, 'b': 13.0},
)


def _oracle(row) -> float:
    return float(row['a']) ** 2 + float(row['b']) ** 2


def test_proposal_cache_is_invariant_to_authority_hash_slot_order(monkeypatch) -> None:
    calls: list[tuple[tuple[str, ...], tuple[tuple[object, ...], ...]]] = []

    # Remove singleton search from this scheduler-only challenger while keeping
    # two-probe bases search-eligible. Validation uses a separate value domain
    # so this test isolates proposal-slot/hash ordering rather than holdout reuse.
    def singleton_collision_only(*, semantic_profile_ids, exposed_fields, examples):
        if len(semantic_profile_ids) != 1:
            return None
        return BasisCollisionCertificate(
            semantic_profile_ids=tuple(semantic_profile_ids),
            basis_cardinality=1,
            exposed_fields=tuple(exposed_fields),
            evidence_digest='scheduler-only-evidence',
            proof_kind='public_input_collision',
            witness_digest='scheduler-only-witness',
            witness_rows=(0, 1),
        )

    def forced_miss(field_names, required_probe_fields, constants, examples, **kwargs):
        signature = (
            tuple(field_names),
            tuple(tuple(row.context[name] for name in field_names) for row in examples),
        )
        calls.append(signature)
        return ExpressionSearchReceipt(False, None, 1, 1, 0, 'forced_search_miss')

    monkeypatch.setattr(runtime, 'build_basis_collision_certificate', singleton_collision_only)
    monkeypatch.setattr(runtime, 'synthesize_variable_expression', forced_miss)

    receipt = runtime.discover_adaptive_causal_basis(
        _oracle,
        ('a', 'b'),
        (-3.0, 3.0),
        DISCOVERY,
        VALIDATION,
        intervention_arity=1,
        max_basis_size=2,
        composition_constants=(0.0, 2.0),
        composition_max_depth=5,
        composition_max_candidates_per_basis=20,
        max_composition_candidates_total=20,
        composition_beam_width=32,
    )

    assert receipt.legal_interventions == 4
    assert receipt.semantic_profiles == 4
    assert len(set(calls)) == 3
    assert len(calls) == 3
    assert receipt.composition_candidates_considered == 3
