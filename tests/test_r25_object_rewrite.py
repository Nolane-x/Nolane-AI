from cogcoder.arc_grid import Grid
from cogcoder.arc_object_rule import fit_object_programs
from cogcoder.arc_ops_view import apply_program


def g(rows): return Grid.from_rows(rows)


def test_recolors_components_by_generic_area_property():
    pairs=(
        (
            g([[1,0,0,0],[0,0,1,1],[0,0,1,1],[0,0,0,0]]),
            g([[2,0,0,0],[0,0,1,1],[0,0,1,1],[0,0,0,0]]),
        ),
        (
            g([[0,1,1,0],[0,1,1,0],[0,0,0,1],[0,0,0,0]]),
            g([[0,1,1,0],[0,1,1,0],[0,0,0,2],[0,0,0,0]]),
        ),
    )
    programs=fit_object_programs(pairs,max_rules=4)
    assert programs, 'expected an object-property rewrite rule'
    test_input=g([[0,0,0,0],[1,1,0,0],[1,1,0,0],[0,0,1,0]])
    expected=g([[0,0,0,0],[1,1,0,0],[1,1,0,0],[0,0,2,0]])
    assert any(apply_program(p,test_input)==expected for p in programs)


if __name__=='__main__':
    test_recolors_components_by_generic_area_property()
    print('R2.5 object rewrite test PASS')
