from __future__ import annotations

from cogcoder.arc_grid import Grid
from cogcoder.r26_canonical import canonicalize_pairs


def g(rows):
    return Grid.from_rows(rows)


def recolor(grid: Grid, table: dict[int, int]) -> Grid:
    return Grid.from_rows(tuple(table.get(v, v) for v in row) for row in grid.rows)


def test_canonicalization_is_color_permutation_invariant() -> None:
    pairs = (
        (g([[0, 1, 0], [2, 2, 0], [0, 0, 0]]), g([[0, 1, 0], [2, 2, 0], [0, 0, 0]])),
        (g([[0, 0, 1], [2, 2, 2], [0, 0, 0]]), g([[0, 0, 1], [2, 2, 2], [0, 0, 0]])),
    )
    table = {0: 0, 1: 7, 2: 4}
    permuted = tuple((recolor(a, table), recolor(b, table)) for a, b in pairs)
    canon_a, ambiguous_a = canonicalize_pairs(pairs)
    canon_b, ambiguous_b = canonicalize_pairs(permuted)
    assert ambiguous_a is False
    assert ambiguous_b is False
    assert canon_a == canon_b


def test_structurally_indistinguishable_colors_report_ambiguity() -> None:
    pairs = ((g([[1, 2], [2, 1]]), g([[1, 2], [2, 1]])),)
    _, ambiguous = canonicalize_pairs(pairs)
    assert ambiguous is True


def main() -> None:
    test_canonicalization_is_color_permutation_invariant()
    test_structurally_indistinguishable_colors_report_ambiguity()
    print('R2.6 canonicalization tests PASS')


if __name__ == '__main__':
    main()
