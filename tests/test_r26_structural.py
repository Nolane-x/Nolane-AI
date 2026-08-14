from __future__ import annotations

from cogcoder.arc_grid import Grid
from cogcoder.r26_firewall import validate_family
from cogcoder.r26_ops import apply_program
from cogcoder.r26_structural import programs


def g(rows):
    return Grid.from_rows(rows)


def test_separator_region_map() -> None:
    inp = g([
        [2,2,9,2,2,9,2,2],
        [2,2,9,2,2,9,2,2],
        [9,9,9,9,9,9,9,9],
        [2,2,9,2,2,9,2,2],
        [2,2,9,2,2,9,2,2],
    ])
    target = g([[2,2,2],[2,2,2]])
    fitted = programs(((inp, target),))
    assert any(p.steps[0].op == 'separator_map' and apply_program(p, inp) == target for p in fitted)


def test_separator_repack() -> None:
    inp = g([
        [1,1,0,9,0,2,2],
        [1,0,0,9,0,0,2],
        [0,0,0,9,0,0,0],
        [9,9,9,9,9,9,9],
        [3,0,0,9,0,4,0],
        [3,3,0,9,4,4,0],
        [0,0,0,9,0,0,0],
    ])
    target = g([
        [1,1,2,2],
        [1,0,0,2],
        [3,0,0,4],
        [3,3,4,4],
    ])
    fitted = programs(((inp, target),))
    assert any(p.steps[0].op == 'separator_repack' and apply_program(p, inp) == target for p in fitted)


def test_rectangular_frame_inner() -> None:
    inp = g([
        [0,0,0,0,0,0],
        [0,7,7,7,7,0],
        [0,7,1,2,7,0],
        [0,7,3,4,7,0],
        [0,7,7,7,7,0],
        [0,0,0,0,0,0],
    ])
    target = g([[1,2],[3,4]])
    fitted = programs(((inp, target),))
    assert any(p.steps[0].op == 'frame_inner' and apply_program(p, inp) == target for p in fitted)


def _map_pair(base: int, sep: int, rows: int, cols: int):
    block_h = 2
    block_w = 2
    out_h = rows * block_h + rows - 1
    out_w = cols * block_w + cols - 1
    data = []
    for r in range(out_h):
        if (r + 1) % (block_h + 1) == 0:
            data.append([sep] * out_w)
            continue
        row = []
        for c in range(out_w):
            row.append(sep if (c + 1) % (block_w + 1) == 0 else base)
        data.append(row)
    return g(data), Grid.from_rows([[base] * cols for _ in range(rows)])


def test_separator_map_survives_generalization_firewall() -> None:
    pairs = (
        _map_pair(2,9,2,2),
        _map_pair(4,7,3,2),
        _map_pair(6,1,2,3),
    )
    evidence = validate_family(programs, pairs, meta_kinds=('color','flip_h'))
    assert evidence.loeo_total == 3 and evidence.loeo_passed == 3
    assert evidence.meta_total >= 1 and evidence.meta_passed == evidence.meta_total


def main() -> None:
    test_separator_region_map()
    test_separator_repack()
    test_rectangular_frame_inner()
    test_separator_map_survives_generalization_firewall()
    print('R2.6 structural extraction tests PASS')


if __name__ == '__main__':
    main()
