from cogcoder.arc_grid import Grid
from cogcoder.arc_ops import apply_program
from cogcoder.arc_pair import fit_pair_programs


def g(rows):
    return Grid.from_rows(rows)


def test_learns_d4_union_without_color_memorization():
    pairs=(
        (g([[1,0,0],[1,0,0],[0,0,0]]),g([[1,0,1],[1,0,1],[0,0,0]])),
        (g([[2,0,0],[0,0,0],[2,0,0]]),g([[2,0,2],[0,0,0],[2,0,2]])),
    )
    programs=fit_pair_programs(pairs)
    assert programs
    assert all(all(apply_program(p,x)==y for x,y in pairs) for p in programs)
    test_input=g([[3,0,0],[0,0,0],[0,0,0]])
    expected=g([[3,0,3],[0,0,0],[0,0,0]])
    assert any(apply_program(p,test_input)==expected for p in programs)


if __name__=='__main__':
    test_learns_d4_union_without_color_memorization()
    print('R2.5 pair relation test PASS')
