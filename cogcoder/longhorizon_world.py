from __future__ import annotations

import random
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class PublicGoal:
    goal_id: str
    dependencies: tuple[str, ...]
    required: bool
    terminal: bool = False


@dataclass(frozen=True)
class PublicAction:
    action_id: str
    goal_id: str


@dataclass(frozen=True)
class PublicObservation:
    step_count: int
    max_steps: int
    goals: tuple[PublicGoal, ...]
    actions: tuple[PublicAction, ...]
    completed: tuple[str, ...]
    events: tuple[str, ...]
    last_outcome: str | None
    solved: bool


class LongHorizonWorld:
    def __init__(self, *, seed: int, incident: str, max_steps: int = 40):
        allowed = {'none', 'add_requirement', 'invalidate', 'transient', 'mixed', 'double_change'}
        if incident not in allowed:
            raise ValueError('unknown incident')
        self._seed = int(seed)
        self._incident = incident
        self._max_steps = int(max_steps)
        rng = random.Random(self._seed)
        self._n = rng.randint(16, 24)
        self._terminal = f'G{self._n - 1}'
        self._goals: dict[str, PublicGoal] = {}
        for i in range(self._n):
            gid = f'G{i}'
            if i == 0:
                deps: tuple[str, ...] = ()
            elif i == self._n - 1:
                deps = tuple(f'G{j}' for j in range(i))
            else:
                deps = (f'G{i-1}',)
            self._goals[gid] = PublicGoal(gid, deps, True, i == self._n - 1)
        self._goals['SUPPORT'] = PublicGoal('SUPPORT', ('G0',), False, False)
        self._goals['SUPPORT2'] = PublicGoal('SUPPORT2', ('G1',), False, False)
        self._actions = tuple(PublicAction(f'do:{gid}', gid) for gid in sorted(self._goals))
        self._completed: set[str] = set()
        self._events: list[str] = []
        self._step_count = 0
        self._last_outcome: str | None = None
        self._max_core_completed = 0
        self._schedule_index = 0
        self._invalidated_goal = f'G{max(1, self._n // 5)}'
        self._transient_goal = f'G{max(2, self._n // 2)}'
        self._transient_consumed = False
        self._schedule = self._make_schedule()

    def _make_schedule(self) -> tuple[tuple[int, str], ...]:
        n = self._n
        if self._incident == 'add_requirement':
            return ((max(3, n // 3), 'add1'),)
        if self._incident == 'invalidate':
            return ((max(4, n // 2), 'invalidate'),)
        if self._incident == 'mixed':
            return ((max(3, n // 3), 'add1'), (max(6, (2 * n) // 3), 'invalidate'))
        if self._incident == 'double_change':
            return (
                (max(3, n // 4), 'add1'),
                (max(6, n // 2), 'add2'),
                (max(9, (3 * n) // 4), 'invalidate'),
            )
        return ()

    def observe(self) -> PublicObservation:
        return PublicObservation(
            self._step_count,
            self._max_steps,
            tuple(self._goals[k] for k in sorted(self._goals)),
            self._actions,
            tuple(sorted(self._completed)),
            tuple(self._events),
            self._last_outcome,
            self._is_solved(),
        )

    def _is_solved(self) -> bool:
        required = {g.goal_id for g in self._goals.values() if g.required}
        return self._terminal in self._completed and required.issubset(self._completed)

    def _add_support_requirement(self, support_id: str) -> None:
        support = self._goals[support_id]
        self._goals[support_id] = replace(support, required=True)
        final = self._goals[self._terminal]
        if support_id not in final.dependencies:
            self._goals[self._terminal] = replace(final, dependencies=tuple(final.dependencies) + (support_id,))
        self._events.append(f'requirement-added:{support_id}->{self._terminal}')

    def _apply_change(self, kind: str) -> None:
        if kind == 'add1':
            self._add_support_requirement('SUPPORT')
        elif kind == 'add2':
            self._add_support_requirement('SUPPORT2')
        elif kind == 'invalidate':
            self._completed.discard(self._invalidated_goal)
            self._events.append(f'requirement-invalidated:{self._invalidated_goal}')
        else:
            raise ValueError(kind)

    def _maybe_fire_changes(self) -> None:
        while self._schedule_index < len(self._schedule):
            threshold, kind = self._schedule[self._schedule_index]
            if self._max_core_completed < threshold:
                break
            self._schedule_index += 1
            self._apply_change(kind)

    def _uses_transient(self) -> bool:
        return self._incident in {'transient', 'mixed', 'double_change'}

    def step(self, action_id: str) -> PublicObservation:
        if self._step_count >= self._max_steps:
            self._last_outcome = 'budget_exhausted'
            return self.observe()
        action = next((a for a in self._actions if a.action_id == action_id), None)
        if action is None:
            raise ValueError('unknown action')
        self._step_count += 1
        goal = self._goals[action.goal_id]
        if action.goal_id in self._completed:
            self._last_outcome = 'already_completed'
            return self.observe()
        if not goal.required:
            self._last_outcome = 'inactive_goal'
            return self.observe()
        if not all(dep in self._completed for dep in goal.dependencies):
            self._last_outcome = 'blocked_precondition'
            return self.observe()
        if self._uses_transient() and action.goal_id == self._transient_goal and not self._transient_consumed:
            self._transient_consumed = True
            self._last_outcome = 'transient_failure'
            self._events.append(f'transient-failure:{action.goal_id}')
            return self.observe()
        self._completed.add(action.goal_id)
        self._last_outcome = 'completed'
        if action.goal_id.startswith('G'):
            self._max_core_completed = max(
                self._max_core_completed,
                sum(1 for g in self._completed if g.startswith('G')),
            )
        self._maybe_fire_changes()
        return self.observe()


class PublicProjectProxy:
    def __init__(self, world: LongHorizonWorld):
        self.__world = world

    def observe(self) -> PublicObservation:
        return self.__world.observe()

    def step(self, action_id: str) -> PublicObservation:
        return self.__world.step(action_id)


def make_longhorizon_world(*, seed: int, incident: str | None = None, max_steps: int = 40) -> LongHorizonWorld:
    if incident is None:
        incident = ('none', 'add_requirement', 'invalidate', 'transient', 'mixed', 'double_change')[int(seed) % 6]
    return LongHorizonWorld(seed=int(seed), incident=str(incident), max_steps=int(max_steps))
