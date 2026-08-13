from cogcoder.arc_grid import Grid
from cogcoder.arc_local import fit_local_programs
from cogcoder.arc_ops_view import apply_program


def g(rows): return Grid.from_rows(rows)


def test_directional_context_distinguishes_right_marker():
    pairs=(
        (g([[0,0,0],[0,1,4],[0,0,0]]),g([[0,0,0],[0,2,4],[0,0,0]])),
        (g([[0,0,0],[4,1,0],[0,0,0]]),g([[0,0,0],[4,1,0],[0,0,0]])),
    )
    programs=fit_local_programs(pairs,max_rules=8)
    assert programs, 'expected a directional local rule'
    test_input=g([[0,0,0],[0,1,4],[0,0,0]])
    expected=g([[0,0,0],[0,2,4],[0,0,0]])
    assert any(apply_program(p,test_input)==expected for p in programs)


if __name__=='__main__':
    test_directional_context_distinguishes_right_marker()
    print('R2.5 directional local test PASS')
