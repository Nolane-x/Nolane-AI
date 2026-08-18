from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r265_verified_patch_primitive_induction import (
    PatchPrimitiveGrammar,
    enumerate_patch_macro_hypotheses,
)


def test_r265_hypotheses_preserve_inherited_patchmacro_fields_and_semantic_aliases() -> None:
    source = RepositoryPatchCandidate(
        'caller:source', (), (('main.py', 'def solve(x, y):\n    return x + y\n'),), 0, 0,
    )
    grammar = PatchPrimitiveGrammar(
        allowed_target_values=('FloorDiv', 'Mod', 'Mult'),
        max_hypotheses=3,
    )

    rows = enumerate_patch_macro_hypotheses((source,), grammar)

    assert len(rows) == 3
    assert all(row.support > 0 for row in rows)
    assert [(row.slot, row.kind, row.src, row.dst, row.macro_id) for row in rows] == sorted(
        (row.slot, row.kind, row.src, row.dst, row.macro_id) for row in rows
    )
    assert [(row.operation, row.source_value, row.target_value) for row in rows] == [
        (row.kind, row.src, row.dst) for row in rows
    ]
