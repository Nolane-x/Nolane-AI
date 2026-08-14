from __future__ import annotations

from cogcoder.arc_grid import Grid
from cogcoder.r26_firewall import validate_family
from cogcoder.r26_ops import apply_program
from cogcoder.r26_path_trim import programs


def g(rows):
    return Grid.from_rows(rows)


def make_pair(bg: int, gate: int, path: int, marker: int):
    rows = [[bg for _ in range(8)] for _ in range(8)]
    # Gate: same role color on opposite sides of the start path cell.
    rows[0][0] = gate
    rows[0][1] = path
    rows[0][2] = gate
    # Simple path leaves the gate perpendicularly, turns, and meets marker.
    for r, c in ((1,1),(2,1),(3,1),(3,2),(3,3),(3,4)):
        rows[r][c] = path
    rows[3][5] = marker
    # Second path has only a diagonal marker and must remain untouched.
    rows[5][0] = gate
    rows[5][1] = path
    rows[5][2] = gate
    rows[6][1] = path
    rows[7][1] = path
    rows[6][2] = marker
    inp = g(rows)

    out = [row[:] for row in rows]
    out[1][1] = marker
    for r, c in ((2,1),(3,1),(3,2),(3,3),(3,4),(3,5)):
        out[r][c] = bg
    return inp, g(out)


def test_trims_only_path_with_orthogonally_adjacent_marker() -> None:
    pair = make_pair(7, 0, 3, 5)
    fitted = programs((pair,))
    selected = [p for p in fitted if p.steps[0].op == 'gate_path_trim']
    assert selected
    assert apply_program(selected[0], pair[0]) == pair[1]


def test_path_trim_survives_loeo_color_flip_and_rotation() -> None:
    pairs = (
        make_pair(7, 0, 3, 5),
        make_pair(9, 2, 4, 8),
        make_pair(6, 1, 7, 3),
    )
    evidence = validate_family(programs, pairs)
    assert evidence.loeo_total == 3 and evidence.loeo_passed == 3
    assert evidence.meta_total >= 2 and evidence.meta_passed == evidence.meta_total


def main() -> None:
    test_trims_only_path_with_orthogonally_adjacent_marker()
    test_path_trim_survives_loeo_color_flip_and_rotation()
    print('R2.6 path trim tests PASS')


if __name__ == '__main__':
    main()
