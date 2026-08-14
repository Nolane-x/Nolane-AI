from __future__ import annotations

from .arc_eval import ParsedTask, TaskScore
from .arc_ops_view import apply_program
from .r26_candidate import Candidate, program_set, rank_candidates


def score_with_candidates(
    task: ParsedTask,
    candidates,
    *,
    max_attempts: int = 2,
    max_programs: int = 64,
) -> TaskScore:
    if max_attempts not in (1, 2):
        raise ValueError('R2.6 max_attempts must be 1 or 2')
    if max_programs < 1 or max_programs > 64:
        raise ValueError('R2.6 max_programs must be in 1..64')
    ranked = rank_candidates(tuple(candidates), limit=max_programs)
    correct = 0
    attempts = 0
    for inp, target in zip(task.test_inputs, task.test_outputs):
        seen = set()
        predictions = []
        for candidate in ranked:
            try:
                out = apply_program(candidate.program, inp)
            except (ValueError, ArithmeticError, OverflowError, StopIteration, TypeError):
                continue
            if out.rows in seen:
                continue
            seen.add(out.rows)
            predictions.append(out)
            attempts += 1
            if len(predictions) >= max_attempts:
                break
        if target is not None and any(out == target for out in predictions):
            correct += 1
    return TaskScore(
        bool(task.test_inputs) and correct == len(task.test_inputs),
        len(task.test_inputs),
        correct,
        len(ranked),
        attempts,
    )


def score(task: ParsedTask, *, max_attempts: int = 2, max_programs: int = 64) -> TaskScore:
    if max_attempts != 2:
        raise ValueError('Frozen R2.6 protocol uses exactly two attempts')
    if max_programs != 64:
        raise ValueError('Frozen R2.6 protocol uses exactly 64 programs')
    candidates = program_set(task.train_pairs, limit=max_programs)
    return score_with_candidates(
        task,
        candidates,
        max_attempts=max_attempts,
        max_programs=max_programs,
    )
