from __future__ import annotations

from cogcoder.arc_grid import Grid
from cogcoder.r26_firewall import validate_family
from cogcoder.r26_ops import apply_program
from cogcoder.r26_structural import programs


def g(rows):
    return Grid.from_rows(rows)


def make_case(common: int, unique: int, unique_pos: tuple[int, int]):
    bg = 0
    panels = []
    for pr in range(2):
        row = []
        for pc in range(2):
            color = unique if (pr, pc) == unique_pos else common
            row.append(g([[color, 0, color], [0, color, 0]]))
        panels.append(row)
    rows = []
    for pr, panel_row in enumerate(panels):
        if pr:
            rows.extend([[bg] * 7, [bg] * 7])
        for r in range(2):
            rows.append(list(panel_row[0].rows[r]) + [bg] + list(panel_row[1].rows[r]))
    inp = g(rows)
    target = panels[unique_pos[0]][unique_pos[1]]
    return inp, target


def test_extracts_panel_whose_foreground_color_is_unique() -> None:
    pair = make_case(2, 7, (1, 0))
    fitted = programs((pair,))
    selected = [p for p in fitted if p.steps[0].op == 'unique_foreground_panel']
    assert selected
    assert apply_program(selected[0], pair[0]) == pair[1]


def test_unique_panel_survives_loeo_and_metamorphic_checks() -> None:
    pairs = (
        make_case(2, 7, (1, 0)),
        make_case(8, 3, (0, 1)),
        make_case(4, 6, (1, 1)),
    )
    evidence = validate_family(programs, pairs, meta_kinds=('color', 'flip_h'))
    assert evidence.loeo_total == 3 and evidence.loeo_passed == 3
    assert evidence.meta_total >= 1 and evidence.meta_passed == evidence.meta_total


def main() -> None:
    test_extracts_panel_whose_foreground_color_is_unique()
    test_unique_panel_survives_loeo_and_metamorphic_checks()
    print('R2.6 unique panel tests PASS')


if __name__ == '__main__':
    main()
