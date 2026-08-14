from cogcoder.arc_grid import Grid
from cogcoder.segment_fit import programs
from cogcoder.arc_ops_view import apply_program


def g(rows): return Grid.from_rows(rows)


def test_connects_aligned_markers_with_inferred_color():
    pairs=(
        (
            g([[0,1,0,0,1,0],[0,0,0,0,0,0],[0,0,0,0,0,0]]),
            g([[0,1,2,2,1,0],[0,0,0,0,0,0],[0,0,0,0,0,0]]),
        ),
        (
            g([[0,0,3],[0,0,0],[0,0,0],[0,0,3]]),
            g([[0,0,3],[0,0,2],[0,0,2],[0,0,3]]),
        ),
    )
    fitted=programs(pairs)
    assert fitted
    x=g([[4,0,0],[0,0,0],[0,0,0],[4,0,0]])
    y=g([[4,0,0],[2,0,0],[2,0,0],[4,0,0]])
    assert any(apply_program(p,x)==y for p in fitted)


if __name__=='__main__':
    test_connects_aligned_markers_with_inferred_color()
    print('R2.5 segment test PASS')
