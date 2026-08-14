from __future__ import annotations

from cogcoder.arc_grid import Grid
from cogcoder.r26_firewall import validate_family
from cogcoder.r26_marker_repeat import programs
from cogcoder.r26_ops import apply_program


def g(rows):
    return Grid.from_rows(rows)


def make_vertical_pair(marker: int, motif: int, length: int, size: int):
    if size < length + 4:
        raise ValueError('size too small')
    rows = [[0 for _ in range(size)] for _ in range(size)]
    # Marker is a unique border bar. The aligned L-row motif varies by row.
    for r in range(length):
        rows[r][0] = marker
        rows[r][2 + (r % 2)] = motif
        if r % 2 == 0:
            rows[r][size - 2] = motif
    # Existing content extends beyond the control bar, leaving a blank tail.
    content_end = length + 1
    rows[length][3] = motif
    rows[content_end][size - 3] = motif
    inp = g(rows)

    out = [row[:] for row in rows]
    template = []
    for r in range(length):
        row = rows[r][:]
        row[0] = 0
        template.append(row)
    for r in range(content_end + 1, size):
        out[r] = template[(r - (content_end + 1)) % length][:]
    return inp, g(out)


def test_border_marker_length_controls_motif_repeat() -> None:
    pair = make_vertical_pair(5, 3, 3, 9)
    fitted = programs((pair,))
    selected = [p for p in fitted if p.steps[0].op == 'border_marker_repeat']
    assert selected
    assert apply_program(selected[0], pair[0]) == pair[1]


def test_marker_repeat_survives_loeo_color_flip_and_rotation() -> None:
    pairs = (
        make_vertical_pair(5, 3, 2, 8),
        make_vertical_pair(7, 4, 3, 9),
        make_vertical_pair(6, 2, 4, 10),
    )
    evidence = validate_family(programs, pairs)
    assert evidence.loeo_total == 3 and evidence.loeo_passed == 3
    assert evidence.meta_total >= 2 and evidence.meta_passed == evidence.meta_total


def main() -> None:
    test_border_marker_length_controls_motif_repeat()
    test_marker_repeat_survives_loeo_color_flip_and_rotation()
    print('R2.6 marker repeat tests PASS')


if __name__ == '__main__':
    main()
