from cogcoder.arc_grid import Grid
from cogcoder.region_fit import programs
from cogcoder.arc_ops_view import apply_program


def g(rows): return Grid.from_rows(rows)


def test_internal_region_projection():
    pairs=(
        (g([[1,1,1],[1,0,1],[1,1,1]]),g([[1,1,1],[1,2,1],[1,1,1]])),
        (g([[3,3,3,3],[3,0,0,3],[3,3,3,3]]),g([[3,3,3,3],[3,2,2,3],[3,3,3,3]])),
    )
    fitted=programs(pairs)
    assert fitted
    x=g([[4,4,4,4],[4,0,0,4],[4,0,0,4],[4,4,4,4]])
    y=g([[4,4,4,4],[4,2,2,4],[4,2,2,4],[4,4,4,4]])
    assert any(apply_program(p,x)==y for p in fitted)


if __name__=='__main__':
    test_internal_region_projection()
    print('R2.5 region test PASS')
