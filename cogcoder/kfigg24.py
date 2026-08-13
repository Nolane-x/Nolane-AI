from __future__ import annotations

from typing import Iterable

from .sequence_refresh import run_observation_sequence, run_snapshot_sequence
from .longhorizon_world import make_longhorizon_world


def evaluate_kfigg24(*, seeds: Iterable[int], max_steps: int = 48, retry_budget: int = 2):
    cases = baseline_solved = candidate_solved = 0
    baseline_steps = candidate_steps = 0
    requirement_cases = requirement_recovered = 0
    transient_cases = transient_recovered = 0
    candidate_blocked = 0
    for seed in seeds:
        seed = int(seed)
        baseline = run_snapshot_sequence(make_longhorizon_world(seed=seed, max_steps=max_steps), retry_budget=retry_budget)
        candidate = run_observation_sequence(make_longhorizon_world(seed=seed, max_steps=max_steps), retry_budget=retry_budget)
        cases += 1
        baseline_solved += int(baseline.solved)
        candidate_solved += int(candidate.solved)
        if baseline.solved:
            baseline_steps += baseline.steps
        if candidate.solved:
            candidate_steps += candidate.steps
        if candidate.requirement_change_seen:
            requirement_cases += 1
            requirement_recovered += int(candidate.recovered_requirement_change)
        if candidate.transient_seen:
            transient_cases += 1
            transient_recovered += int(candidate.recovered_transient)
        candidate_blocked += candidate.blocked_attempts
    denom = max(1, cases)
    return {
        'cases': cases,
        'baseline_episode_count': cases,
        'candidate_episode_count': cases,
        'baseline_solved': baseline_solved,
        'candidate_solved': candidate_solved,
        'baseline_solve_rate': baseline_solved / denom,
        'candidate_solve_rate': candidate_solved / denom,
        'gain_pp': 100.0 * (candidate_solved - baseline_solved) / denom,
        'baseline_mean_steps_solved': baseline_steps / max(1, baseline_solved),
        'candidate_mean_steps_solved': candidate_steps / max(1, candidate_solved),
        'requirement_change_cases': requirement_cases,
        'requirement_change_recovery': requirement_recovered / max(1, requirement_cases),
        'transient_cases': transient_cases,
        'transient_recovery': transient_recovered / max(1, transient_cases),
        'candidate_blocked_attempts': candidate_blocked,
        'protocol': {'max_steps': int(max_steps), 'retry_budget': int(retry_budget)},
    }
