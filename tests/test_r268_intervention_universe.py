from __future__ import annotations

import cogcoder._r268_runtime as runtime


def test_finite_evidence_equivalent_interventions_remain_distinct_authority_actions() -> None:
    fields=('a','b')
    def ctx(rows): return tuple(dict(zip(fields,row,strict=True)) for row in rows)
    def oracle(row): return float(row['a'])+float(row['b'])

    receipt=runtime.discover_adaptive_causal_basis(
        oracle,fields,(0.0,),
        ctx(((1,1),(2,2),(3,3))),
        ctx(((4,4),(5,5))),
        intervention_arity=1,max_basis_size=1,
        composition_constants=(0.0,2.0),composition_max_depth=3,
        composition_max_candidates_per_basis=5000,max_composition_candidates_total=10000,
        composition_beam_width=64,
    )

    assert receipt.legal_interventions==2
    assert receipt.semantic_profiles==2
