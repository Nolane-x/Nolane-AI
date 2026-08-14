from __future__ import annotations

from cogcoder.arc_eval import ParsedTask
from cogcoder.arc_grid import Grid
from cogcoder.arc_ops_view import Program, Step
from cogcoder.r26_candidate import Candidate, rank_candidates
from cogcoder.r26_firewall import Evidence
from cogcoder.r26_score import score_with_candidates


def g(rows):
    return Grid.from_rows(rows)


def test_robust_candidate_ranks_before_legacy() -> None:
    legacy = Candidate(
        Program((Step('transform', ('identity',)),), 1),
        Evidence(0, 0, 0, 0),
        True,
        'legacy',
    )
    robust = Candidate(
        Program((Step('transform', ('flip_h',)),), 1),
        Evidence(3, 3, 1, 1),
        False,
        'd4',
    )
    ranked = rank_candidates((legacy, robust), limit=64)
    assert ranked[0] == robust


def test_two_attempt_budget_is_hard_cap() -> None:
    task = ParsedTask(
        train_pairs=(),
        test_inputs=(g([[1, 0]]),),
        test_outputs=(g([[0, 1]]),),
    )
    candidates = (
        Candidate(Program((Step('transform', ('identity',)),), 1), Evidence(0, 0, 0, 0), True, 'legacy'),
        Candidate(Program((Step('transform', ('flip_h',)),), 1), Evidence(1, 1, 1, 1), False, 'd4'),
        Candidate(Program((Step('color_map', (((0, 1), (1, 0)),)),), 2), Evidence(1, 1, 1, 1), False, 'color'),
    )
    result = score_with_candidates(task, candidates, max_attempts=2, max_programs=64)
    assert result.solved is True
    assert result.attempts_emitted == 2


def test_budget_rejects_out_of_protocol_values() -> None:
    task = ParsedTask(train_pairs=(), test_inputs=(), test_outputs=())
    try:
        score_with_candidates(task, (), max_attempts=3, max_programs=64)
    except ValueError:
        pass
    else:
        raise AssertionError('expected max_attempts validation')
    try:
        score_with_candidates(task, (), max_attempts=2, max_programs=65)
    except ValueError:
        pass
    else:
        raise AssertionError('expected max_programs validation')


def main() -> None:
    test_robust_candidate_ranks_before_legacy()
    test_two_attempt_budget_is_hard_cap()
    test_budget_rejects_out_of_protocol_values()
    print('R2.6 score tests PASS')


if __name__ == '__main__':
    main()
