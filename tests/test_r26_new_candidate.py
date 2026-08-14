from __future__ import annotations

from cogcoder.arc_grid import Grid
from cogcoder.r26_candidate import program_set


def g(rows):
    return Grid.from_rows(rows)


def map_pair(base: int, sep: int, rows: int, cols: int):
    bh = bw = 2
    h = rows * bh + rows - 1
    w = cols * bw + cols - 1
    data = []
    for r in range(h):
        if (r + 1) % 3 == 0:
            data.append([sep] * w)
        else:
            data.append([sep if (c + 1) % 3 == 0 else base for c in range(w)])
    return g(data), Grid.from_rows([[base] * cols for _ in range(rows)])


def test_new_structural_family_can_enter_candidate_pool() -> None:
    pairs = (
        map_pair(2, 9, 2, 2),
        map_pair(4, 7, 3, 2),
        map_pair(6, 1, 2, 3),
    )
    candidates = program_set(pairs, limit=64)
    structural = [c for c in candidates if c.family == 'structural' and not c.legacy]
    assert structural, 'expected a firewall-approved R2.6 structural candidate'
    assert any(c.program.steps[0].op == 'separator_map' for c in structural)
    assert all(c.evidence.loeo_passed == c.evidence.loeo_total for c in structural)
    assert all(c.evidence.meta_passed == c.evidence.meta_total for c in structural)


def main() -> None:
    test_new_structural_family_can_enter_candidate_pool()
    print('R2.6 new-candidate tests PASS')


if __name__ == '__main__':
    main()
