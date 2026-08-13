from cogcoder.arc_local import fit_local_programs
from cogcoder.arc_grid import Grid
from cogcoder.arc_ops_view import apply_program


def g(rows):
    return Grid.from_rows(rows)


def test_distant_row_marker_context():
    pairs=(
        (
            g([[0,0,0,0,0],[0,1,0,0,4],[0,0,0,0,0]]),
            g([[0,0,0,0,0],[0,2,0,0,4],[0,0,0,0,0]]),
        ),
        (
            g([[0,0,0,0,0],[0,1,0,0,0],[0,0,0,0,4]]),
            g([[0,0,0,0,0],[0,1,0,0,0],[0,0,0,0,4]]),
        ),
    )
    programs=fit_local_programs(pairs,max_rules=8)
    axis=[p for p in programs if p.steps and str(p.steps[0].args[0]) in ('axis_set','axis_counts')]
    assert axis
    test_input=g([[0,0,0,0,0],[4,0,0,1,0],[0,0,0,0,0]])
    expected=g([[0,0,0,0,0],[4,0,0,2,0],[0,0,0,0,0]])
    assert any(apply_program(p,test_input)==expected for p in axis)


if __name__=='__main__':
    test_distant_row_marker_context()
    print('R2.5 grid context test PASS')
