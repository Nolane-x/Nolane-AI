from cogcoder.arc_grid import Grid
from cogcoder.arc_candidate_region import program_set
from cogcoder.arc_ops_view import apply_program


def g(rows): return Grid.from_rows(rows)


def test_internal_region_projection():
    pairs=(
        (g([[1,1,1],[1,0,1],[1,1,1]]),g([[1,1,1],[1,2,1],[1,1,1]])),
        (g([[3,3,3,3],[3,0,0,3],[3,3,3,3]]),g([[3,3,3,3],[3,2,2,3],[3,3,3,3]])),
    )
    fitted=program_set(pairs,limit=64)
    region=[p for p in fitted if p.steps and p.steps[0].op=='region_project']
    assert region
    x=g([[4,4,4,4],[4,0,0,4],[4,0,0,4],[4,4,4,4]])
    y=g([[4,4,4,4],[4,2,2,4],[4,2,2,4],[4,4,4,4]])
    assert any(apply_program(p,x)==y for p in region)


if __name__=='__main__':
    test_internal_region_projection()
    print('R2.5 region test PASS')
