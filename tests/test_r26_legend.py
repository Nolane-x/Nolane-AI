from __future__ import annotations

from cogcoder.arc_grid import Grid
from cogcoder.r26_firewall import validate_family
from cogcoder.r26_legend import programs
from cogcoder.r26_ops import apply_program


def g(rows):
    return Grid.from_rows(rows)


def make_pair(a: int, b: int, c: int, d: int):
    inp = g([
        [a, b, 0, 0, 0, 0],
        [c, d, 0, a, c, 0],
        [0, 0, b, d, a, 0],
        [0, c, d, 0, b, 0],
        [0, a, 0, c, 0, d],
        [0, 0, 0, 0, 0, 0],
    ])
    mapping = {a: b, b: a, c: d, d: c}
    rows = []
    for r, row in enumerate(inp.rows):
        out = []
        for col, value in enumerate(row):
            if r < 2 and col < 2:
                out.append(value)
            else:
                out.append(mapping.get(value, value))
        rows.append(out)
    return inp, g(rows)


def test_corner_legend_swaps_color_pairs_but_preserves_key() -> None:
    pair = make_pair(1, 3, 2, 8)
    fitted = programs((pair,))
    legend = [p for p in fitted if p.steps[0].op == 'legend_swap']
    assert legend
    assert apply_program(legend[0], pair[0]) == pair[1]


def test_legend_family_survives_loeo_and_full_metamorphic_firewall() -> None:
    pairs = (
        make_pair(1, 3, 2, 8),
        make_pair(4, 2, 3, 7),
        make_pair(9, 4, 7, 6),
    )
    evidence = validate_family(programs, pairs)
    assert evidence.loeo_total == 3 and evidence.loeo_passed == 3
    assert evidence.meta_total >= 2 and evidence.meta_passed == evidence.meta_total


def main() -> None:
    test_corner_legend_swaps_color_pairs_but_preserves_key()
    test_legend_family_survives_loeo_and_full_metamorphic_firewall()
    print('R2.6 legend tests PASS')


if __name__ == '__main__':
    main()
