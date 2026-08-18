from __future__ import annotations

from collections.abc import Mapping

from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r267_three_probe_causal_composition import (
    ThreeProbeCompositionReceipt,
    discover_three_probe_structure,
    synthesize_three_probe_causal_program,
)


FIELDS = ('a', 'b', 'c', 'd', 'e', 'f')


def tri_bilinear(row: Mapping[str, object]) -> float:
    return (
        float(row['a']) * float(row['b'])
        + float(row['c']) * float(row['d'])
        + float(row['e']) * float(row['f'])
    )


def test_r267_public_three_probe_api_exists_on_exact_r266_parent() -> None:
    assert callable(discover_three_probe_structure)
    assert callable(synthesize_three_probe_causal_program)
    assert ThreeProbeCompositionReceipt.__name__ == 'ThreeProbeCompositionReceipt'
    need = OperatorInventionNeed(
        'R2.67 tri-bilinear three-probe program',
        FIELDS,
        'out',
        constants=(0.0, 2.0),
        max_depth=4,
        max_candidates=50_000,
    )
    assert need.field_names == FIELDS
