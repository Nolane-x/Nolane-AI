from __future__ import annotations

from dataclasses import dataclass

from .longhorizon_world import LongHorizonWorld, PublicGoal, PublicObservation, PublicProjectProxy


@dataclass(frozen=True)
class SequenceResult:
    solved: bool
    steps: int
    actions: tuple[str, ...]
    blocked_attempts: int
    retry_count: int
    requirement_change_seen: bool
    transient_seen: bool
    recovered_requirement_change: bool
    recovered_transient: bool


def _action_for(obs: PublicObservation, goal_id: str) -> str:
    return next(a.action_id for a in obs.actions if a.goal_id == goal_id)


def _initial_plan(obs: PublicObservation) -> tuple[str, ...]:
    remaining = {g.goal_id: g for g in obs.goals if g.required}
    completed: set[str] = set(obs.completed)
    plan: list[str] = []
    while remaining:
        ready = [g for g in remaining.values() if all(dep in completed for dep in g.dependencies)]
        if not ready:
            break
        ready.sort(key=lambda g: (g.terminal, len(g.dependencies), g.goal_id))
        goal = ready[0]
        plan.append(_action_for(obs, goal.goal_id))
        completed.add(goal.goal_id)
        remaining.pop(goal.goal_id)
    return tuple(plan)


def _signals(obs: PublicObservation) -> tuple[bool, bool]:
    requirement = any(e.startswith('requirement-added:') or e.startswith('requirement-invalidated:') for e in obs.events)
    transient = any(e.startswith('transient-failure:') for e in obs.events)
    return requirement, transient


def run_snapshot_sequence(world: LongHorizonWorld, *, retry_budget: int = 2) -> SequenceResult:
    proxy = PublicProjectProxy(world)
    obs = proxy.observe()
    plan = _initial_plan(obs)
    actions: list[str] = []
    blocked = retries = 0
    for action_id in plan:
        if obs.solved or obs.step_count >= obs.max_steps:
            break
        obs = proxy.step(action_id); actions.append(action_id)
        if obs.last_outcome == 'transient_failure':
            local = 0
            while local < retry_budget and obs.last_outcome == 'transient_failure' and obs.step_count < obs.max_steps:
                obs = proxy.step(action_id); actions.append(action_id); local += 1; retries += 1
        if obs.last_outcome == 'blocked_precondition':
            blocked += 1
    requirement, transient = _signals(obs)
    return SequenceResult(obs.solved, obs.step_count, tuple(actions), blocked, retries, requirement, transient, requirement and obs.solved, transient and obs.solved)


def _choose_ready(obs: PublicObservation) -> PublicGoal | None:
    completed = set(obs.completed)
    ready = [g for g in obs.goals if g.required and g.goal_id not in completed and all(dep in completed for dep in g.dependencies)]
    if not ready:
        return None
    ready.sort(key=lambda g: (g.terminal, len(g.dependencies), g.goal_id))
    return ready[0]


def run_observation_sequence(world: LongHorizonWorld, *, retry_budget: int = 2) -> SequenceResult:
    proxy = PublicProjectProxy(world)
    obs = proxy.observe()
    actions: list[str] = []
    blocked = retries = 0
    retries_by_action: dict[str, int] = {}
    while not obs.solved and obs.step_count < obs.max_steps:
        goal = _choose_ready(obs)
        if goal is None:
            break
        action_id = _action_for(obs, goal.goal_id)
        obs = proxy.step(action_id); actions.append(action_id)
        if obs.last_outcome == 'blocked_precondition':
            blocked += 1
        if obs.last_outcome == 'transient_failure':
            retries_by_action[action_id] = retries_by_action.get(action_id, 0) + 1
            retries += 1
            if retries_by_action[action_id] > retry_budget:
                break
    requirement, transient = _signals(obs)
    return SequenceResult(obs.solved, obs.step_count, tuple(actions), blocked, retries, requirement, transient, requirement and obs.solved, transient and obs.solved)
