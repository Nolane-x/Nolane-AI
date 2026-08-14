from __future__ import annotations

from cogcoder.arc_grid import Grid
from cogcoder.arc_ops_view import Program, Step, apply_program
from cogcoder.r26_firewall import Evidence, validate_family


def g(rows):
    return Grid.from_rows(rows)


def infer_d4(pairs):
    kinds = ('identity', 'rot90', 'rot180', 'rot270', 'flip_h', 'flip_v', 'transpose', 'anti_transpose')
    out = []
    for kind in kinds:
        p = Program((Step('transform', (kind,)),), 1)
        try:
            exact = all(apply_program(p, x) == y for x, y in pairs)
        except ValueError:
            exact = False
        if exact:
            out.append(p)
    return tuple(out)


def infer_identity(_pairs):
    return (Program((Step('transform', ('identity',)),), 1),)


def infer_raw_color(_pairs):
    table = ((0, 0), (1, 2), (2, 2))
    return (Program((Step('color_map', (table,)),), 2),)


def test_loeo_rewards_transfer_and_rejects_nontransfer() -> None:
    pairs = (
        (g([[1, 0, 0], [0, 0, 2]]), g([[0, 0, 1], [2, 0, 0]])),
        (g([[3, 0, 4], [0, 0, 0]]), g([[4, 0, 3], [0, 0, 0]])),
        (g([[5, 0, 0], [6, 0, 0]]), g([[0, 0, 5], [0, 0, 6]])),
    )
    good = validate_family(infer_d4, pairs, meta_kinds=())
    bad = validate_family(infer_identity, pairs, meta_kinds=())
    assert good.loeo_total == 3 and good.loeo_passed == 3
    assert bad.loeo_total == 3 and bad.loeo_passed == 0


def test_color_metamorphism_detects_raw_id_dependency() -> None:
    pairs = (
        (g([[0, 1, 0], [0, 0, 0]]), g([[0, 2, 0], [0, 0, 0]])),
        (g([[0, 0, 0], [1, 0, 0]]), g([[0, 0, 0], [2, 0, 0]])),
    )
    evidence = validate_family(infer_raw_color, pairs, meta_kinds=('color',))
    assert isinstance(evidence, Evidence)
    assert evidence.meta_total == 1
    assert evidence.meta_passed == 0


def test_d4_family_is_flip_equivariant() -> None:
    pairs = (
        (g([[1, 0, 0], [0, 0, 2]]), g([[0, 0, 1], [2, 0, 0]])),
        (g([[3, 0, 4], [0, 0, 0]]), g([[4, 0, 3], [0, 0, 0]])),
        (g([[5, 0, 0], [6, 0, 0]]), g([[0, 0, 5], [0, 0, 6]])),
    )
    evidence = validate_family(infer_d4, pairs, meta_kinds=('flip_h',))
    assert evidence.meta_total == 1
    assert evidence.meta_passed == 1


def main() -> None:
    test_loeo_rewards_transfer_and_rejects_nontransfer()
    test_color_metamorphism_detects_raw_id_dependency()
    test_d4_family_is_flip_equivariant()
    print('R2.6 firewall tests PASS')


if __name__ == '__main__':
    main()
