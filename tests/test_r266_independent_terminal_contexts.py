from cogcoder.r256_operator_invention import OperatorInventionNeed
from cogcoder.r266_learned_contextual_composition import synthesize_contextual_composition_program


def _oracle(row):
    x = float(row['x'])
    lo = float(row['lo'])
    hi = float(row['hi'])
    if x < lo:
        return float(row['left'])
    if x > hi:
        return float(row['right'])
    return float(row['middle'])


def _rows():
    rows = []
    configs = (
        (-3.0, 2.0, -7.0, 4.0, -5.0),
        (-1.0, 4.0, 6.0, -3.0, 9.0),
        (-5.0, 1.0, -8.0, 5.0, 2.0),
        (0.0, 6.0, 3.0, -6.0, -4.0),
        (-4.0, 3.0, 8.0, 2.0, -9.0),
        (-2.0, 5.0, -6.0, -1.0, 7.0),
    )
    for lo, hi, left, middle, right in configs:
        for x in (lo - 3.0, lo, (lo + hi) / 2.0, hi, hi + 3.0):
            rows.append({
                'x': x, 'lo': lo, 'hi': hi,
                'left': left, 'middle': middle, 'right': right,
            })
    return tuple(rows)


def _need():
    return OperatorInventionNeed(
        'R2.66 independent terminal verification contract',
        ('x', 'lo', 'hi', 'left', 'middle', 'right'),
        'out',
        constants=(0.0,),
        max_depth=3,
        max_candidates=25000,
    )


def test_hidden_terminal_contradiction_must_prevent_acceptance():
    rows = _rows()
    discovery = rows[:18]
    validation = rows[18:24]
    terminal = rows[24:]
    hidden = terminal[0]

    def contradicted(row):
        value = _oracle(row)
        if all(float(row[key]) == float(hidden[key]) for key in hidden):
            return value + 101.0
        return value

    result = synthesize_contextual_composition_program(
        contradicted,
        ('x', 'lo', 'hi', 'left', 'middle', 'right'),
        _need(),
        discovery,
        validation,
        terminal_contexts=terminal,
        intervention_arity=1,
        composition_constants=(0.0,),
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
        probe_constants=(0.0,),
        probe_max_depth=3,
        probe_max_candidates=20000,
    )

    assert result.passed is False
    assert result.reason == 'independent_terminal_verification_failed'
    assert result.final_validation_cases == len(terminal)
    assert result.final_validation_exact == len(terminal) - 1
    assert result.structure.false_accepts == 0


def test_clean_terminal_contexts_are_required_for_success_receipt():
    rows = _rows()
    discovery = rows[:18]
    validation = rows[18:24]
    terminal = rows[24:]
    result = synthesize_contextual_composition_program(
        _oracle,
        ('x', 'lo', 'hi', 'left', 'middle', 'right'),
        _need(),
        discovery,
        validation,
        terminal_contexts=terminal,
        composition_max_depth=2,
        composition_max_candidates_per_pair=12000,
        max_composition_candidates_total=120000,
        probe_max_depth=3,
        probe_max_candidates=20000,
    )
    assert result.passed is True
    assert result.final_validation_cases == len(terminal)
    assert result.final_validation_exact == len(terminal)
