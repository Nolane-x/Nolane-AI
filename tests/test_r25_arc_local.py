from cogcoder.arc_grid import Grid
from cogcoder.arc_local import fit_local_programs
from cogcoder.arc_ops_view import apply_program


def g(rows):
    return Grid.from_rows(rows)


def test_learns_sparse_marker_neighbor_rewrite():
    pairs = (
        (
            g([[0, 4, 0], [1, 1, 1], [0, 0, 0]]),
            g([[0, 4, 0], [1, 2, 1], [0, 0, 0]]),
        ),
        (
            g([[0, 0, 0], [4, 1, 0], [0, 1, 0]]),
            g([[0, 0, 0], [4, 2, 0], [0, 1, 0]]),
        ),
    )
    programs = fit_local_programs(pairs, max_rules=8)
    assert programs
    assert all(all(apply_program(p, x) == y for x, y in pairs) for p in programs)
    test_input = g([[0, 1, 0], [0, 1, 4], [0, 1, 0]])
    expected = g([[0, 1, 0], [0, 2, 4], [0, 1, 0]])
    assert any(apply_program(p, test_input) == expected for p in programs)


if __name__ == '__main__':
    test_learns_sparse_marker_neighbor_rewrite()
    print('R2.5 local rewrite test PASS')
