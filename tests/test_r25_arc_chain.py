from cogcoder.arc_grid import Grid
from cogcoder.arc_current import program_set
from cogcoder.arc_ops import apply_program


def g(rows):
    return Grid.from_rows(rows)


def test_composes_panel_overlay_then_rotation():
    pairs = (
        (
            g([[1, 0], [0, 0], [5, 5], [0, 0], [2, 0]]),
            g([[2, 1], [0, 0]]),
        ),
        (
            g([[0, 3], [0, 0], [5, 5], [0, 0], [0, 4]]),
            g([[0, 0], [4, 3]]),
        ),
    )
    programs = program_set(pairs, limit=64)
    fitting = [p for p in programs if all(apply_program(p, x) == y for x, y in pairs)]
    assert fitting, 'expected a composition that fits both demonstrations'
    assert any(
        [step.op for step in p.steps][:2] == ['panel_overlay', 'transform']
        for p in fitting
    ), 'expected panel_overlay followed by a geometric transform'


if __name__ == '__main__':
    test_composes_panel_overlay_then_rotation()
    print('R2.5 chain composition test PASS')
