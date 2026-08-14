from __future__ import annotations

from cogcoder.arc_grid import Grid
from cogcoder.r26_meta import inverse_kind, permute_colors, transform_pair


def g(rows):
    return Grid.from_rows(rows)


def test_color_permutation_round_trip() -> None:
    grid = g([[0, 1, 2], [2, 1, 0]])
    mapping = ((1, 2), (2, 1))
    assert permute_colors(permute_colors(grid, mapping), mapping) == grid


def test_flip_pair_round_trip() -> None:
    pair = (g([[1, 0, 2], [0, 3, 0]]), g([[4, 0, 5], [0, 6, 0]]))
    once = transform_pair(pair, 'flip_h')
    twice = transform_pair(once, inverse_kind('flip_h'))
    assert twice == pair


def test_square_rotation_round_trip() -> None:
    pair = (g([[1, 2], [3, 4]]), g([[4, 3], [2, 1]]))
    out = pair
    for _ in range(4):
        out = transform_pair(out, 'rot90')
    assert out == pair
    assert inverse_kind('rot90') == 'rot270'


def main() -> None:
    test_color_permutation_round_trip()
    test_flip_pair_round_trip()
    test_square_rotation_round_trip()
    print('R2.6 metamorphic tests PASS')


if __name__ == '__main__':
    main()
