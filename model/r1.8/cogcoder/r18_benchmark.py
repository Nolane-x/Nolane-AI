from __future__ import annotations

import copy
import hashlib
import json
import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

R18_BENCHMARK_VERSION = "nolane-figg18-v1"
R18_FAMILIES = (
    "conditional_regimes",
    "regime_switch",
    "implicit_goal_regimes",
    "causal_prerequisites",
)
R18_SPLIT_BASE_SEEDS = {
    "train": 18_100_000,
    "dev": 18_200_000,
    "fresh": 18_900_000,
}


@dataclass(frozen=True)
class R18StepResult:
    observation: dict[str, Any]
    progress: float
    progress_delta: float
    information_gain: float
    failed: bool
    done: bool
    solved: bool


def _stable_seed(split: str, family: str, index: int) -> int:
    if split not in R18_SPLIT_BASE_SEEDS:
        raise ValueError(f"unknown split: {split}")
    if family not in R18_FAMILIES:
        raise ValueError(f"unknown family: {family}")
    if index < 0:
        raise ValueError("index must be non-negative")
    return R18_SPLIT_BASE_SEEDS[split] + R18_FAMILIES.index(family) * 200_003 + index * 1009 + 83


def _forward_distance(value: int, target: int, modulus: int) -> int:
    return (int(target) - int(value)) % int(modulus)


class R18Task:
    """Procedural causal world with a strict public/private boundary."""

    def __init__(self, family: str, split: str, index: int) -> None:
        if family not in R18_FAMILIES:
            raise ValueError(f"unknown family: {family}")
        if split not in R18_SPLIT_BASE_SEEDS:
            raise ValueError(f"unknown split: {split}")
        self.family = family
        self.split = split
        self.index = int(index)
        self.seed = _stable_seed(split, family, index)
        self.task_id = f"{R18_BENCHMARK_VERSION}:{split}:{family}:{self.seed}"
        self._rng = random.Random(self.seed ^ 0x18CC5A1)
        self._step_count = 0
        self._done = False
        self._solved = False
        self._last_event = "episode started"
        self._seen_context_actions: set[tuple[str, int]] = set()
        self._modulus = 5
        self._state = [0, 0, 0]
        self._resource = 0
        self._gate = 0
        self._context_names = self._make_context_names(3)

        if family == "conditional_regimes":
            self._init_conditional_regimes()
        elif family == "regime_switch":
            self._init_regime_switch()
        elif family == "implicit_goal_regimes":
            self._init_implicit_goal_regimes()
        else:
            self._init_prerequisites()

    @property
    def solved(self) -> bool:
        return bool(self._solved)

    @property
    def done(self) -> bool:
        return bool(self._done)

    @property
    def step_count(self) -> int:
        return int(self._step_count)

    @property
    def budget_remaining(self) -> int:
        return max(0, int(self._budget - self._step_count))

    @property
    def action_descriptions(self) -> tuple[str, ...]:
        return self._action_descriptions

    def _make_context_names(self, count: int) -> tuple[str, ...]:
        pool = ["amber", "violet", "cobalt", "ivory", "sable", "mint", "coral", "silver"]
        self._rng.shuffle(pool)
        return tuple(pool[:count])

    def _opaque_labels(self, count: int) -> list[str]:
        pool = ["Nox", "Vela", "Iri", "Kest", "Pru", "Senn", "Tavi", "Orn"]
        self._rng.shuffle(pool)
        return [f"{pool[i]}-{(self.seed + i * 17) % 101:02d}" for i in range(count)]

    def _shuffle_actions(self, kinds: Sequence[str]) -> None:
        labels = self._opaque_labels(sum(kind != "submit" for kind in kinds))
        label_iter = iter(labels)
        rows: list[tuple[str, str]] = []
        for kind in kinds:
            if kind == "submit":
                rows.append((kind, "submit current hypothesis"))
            else:
                rows.append((kind, f"opaque actuator {next(label_iter)}"))
        self._rng.shuffle(rows)
        self._action_kinds = tuple(kind for kind, _ in rows)
        self._action_descriptions = tuple(desc for _, desc in rows)

    def _build_regime_maps(self, regimes: int, actuators: int = 3) -> tuple[tuple[tuple[int, int, int, int], ...], ...]:
        maps: list[tuple[tuple[int, int, int, int], ...]] = []
        for regime in range(regimes):
            dims = list(range(3))
            self._rng.shuffle(dims)
            rows = []
            for actuator in range(actuators):
                target_dim = dims[actuator % 3]
                condition_dim = (target_dim + 1 + regime + actuator) % 3
                even_delta = 1 + self._rng.randrange(2)
                odd_delta = 3 - even_delta
                rows.append((target_dim, condition_dim, even_delta, odd_delta))
            maps.append(tuple(rows))
        return tuple(maps)

    def _init_conditional_regimes(self) -> None:
        self._regime_schedule = (0,)
        self._regime_maps = self._build_regime_maps(3)
        self._static_regime = self._rng.randrange(3)
        self._shuffle_actions(("act:0", "act:1", "act:2", "submit"))
        self._budget = 32
        self._goal = self._witness_goal(10 + self._rng.randrange(5), allow_regime_step=False)

    def _init_regime_switch(self) -> None:
        self._regime_maps = self._build_regime_maps(3)
        self._switch_points = (3, 6, 9)
        self._regime_schedule = (0, 1, 2, 0)
        self._shuffle_actions(("act:0", "act:1", "act:2", "submit"))
        self._budget = 30
        self._goal = self._witness_goal(12 + self._rng.randrange(4), allow_regime_step=True)

    def _init_implicit_goal_regimes(self) -> None:
        self._regime_maps = self._build_regime_maps(2)
        self._static_regime = self._rng.randrange(2)
        self._regime_schedule = (self._static_regime,)
        self._shuffle_actions(("act:0", "act:1", "act:2", "submit"))
        self._budget = 32
        self._goal = self._witness_goal(9 + self._rng.randrange(5), allow_regime_step=False)

    def _init_prerequisites(self) -> None:
        self._modulus = 4
        self._regime_schedule = (0,)
        self._prereq_dims = [0, 1, 2]
        self._rng.shuffle(self._prereq_dims)
        self._shuffle_actions(("charge", "unlock", "move:0", "move:1", "move:2", "submit"))
        self._budget = 28
        witness = (0, 0, 0)
        resource = 0
        gate = 0
        steps = 0
        for kind in ("charge", "charge", "unlock", "move:0", "move:1", "move:2", "move:0"):
            witness, resource, gate = self._transition_snapshot(witness, resource, gate, kind, steps)
            steps += 1
        extra = ["move:0", "move:1", "move:2", "charge"]
        for _ in range(self._rng.randrange(4)):
            kind = self._rng.choice(extra)
            witness, resource, gate = self._transition_snapshot(witness, resource, gate, kind, steps)
            steps += 1
        self._goal = tuple(witness)

    def _context_index(self, step_count: int | None = None) -> int:
        count = self._step_count if step_count is None else int(step_count)
        if self.family == "regime_switch":
            if count < self._switch_points[0]:
                return 0
            if count < self._switch_points[1]:
                return 1
            if count < self._switch_points[2]:
                return 2
            return 0
        if self.family in ("conditional_regimes", "implicit_goal_regimes"):
            return int(self._static_regime)
        return 0

    def _public_regime(self, step_count: int | None = None) -> str:
        return self._context_names[self._context_index(step_count)]

    def _conditional_delta(self, kind: str, state: Sequence[int], regime: int) -> tuple[int, int]:
        actuator = int(kind.split(":", 1)[1])
        target_dim, condition_dim, even_delta, odd_delta = self._regime_maps[regime][actuator]
        delta = even_delta if int(state[condition_dim]) % 2 == 0 else odd_delta
        return int(target_dim), int(delta)

    def _transition_snapshot(self, state: tuple[int, ...], resource: int, gate: int, kind: str, step_count: int) -> tuple[tuple[int, ...], int, int]:
        if kind == "submit":
            return state, resource, gate
        row = list(state)
        if self.family in ("conditional_regimes", "regime_switch", "implicit_goal_regimes"):
            regime = self._context_index(step_count)
            dim, delta = self._conditional_delta(kind, state, regime)
            row[dim] = (row[dim] + delta) % self._modulus
            return tuple(row), resource, gate
        if kind == "charge":
            return tuple(row), min(3, resource + 1), gate
        if kind == "unlock":
            if resource >= 2:
                return tuple(row), resource - 2, 1
            return tuple(row), resource, gate
        move_index = int(kind.split(":", 1)[1])
        dim = self._prereq_dims[move_index]
        if gate:
            row[dim] = (row[dim] + 1) % self._modulus
        return tuple(row), resource, gate

    def _witness_goal(self, steps: int, *, allow_regime_step: bool) -> tuple[int, ...]:
        state = (0, 0, 0)
        resource = 0
        gate = 0
        kinds = ("act:0", "act:1", "act:2")
        for step in range(steps):
            kind = kinds[self._rng.randrange(len(kinds))]
            state, resource, gate = self._transition_snapshot(state, resource, gate, kind, step if allow_regime_step else 0)
        if state == (0, 0, 0):
            for kind in kinds:
                state, resource, gate = self._transition_snapshot(state, resource, gate, kind, 0)
                if state != (0, 0, 0):
                    break
        return tuple(state)

    def _progress_for(self, state: Sequence[int]) -> float:
        distance = sum(_forward_distance(v, g, self._modulus) for v, g in zip(state, self._goal))
        return 1.0 - distance / (3 * (self._modulus - 1))

    def _progress(self) -> float:
        return self._progress_for(self._state)

    def observe(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "benchmark": R18_BENCHMARK_VERSION,
            "task_id": self.task_id,
            "step": self._step_count,
            "budget_remaining": self.budget_remaining,
            "last_event": self._last_event,
            "actions": list(self._action_descriptions),
            "state": list(self._state),
            "progress_signal": round(float(self._progress()), 6),
        }
        if self.family != "causal_prerequisites":
            base["regime"] = self._public_regime()
            base["rule_hint"] = "action effects can depend on observable state and public regime"
        if self.family != "implicit_goal_regimes":
            base["target"] = list(self._goal)
        else:
            base["feedback_hint"] = "infer the desired configuration from progress feedback"
        if self.family == "causal_prerequisites":
            base["resources"] = {"charge_level": int(self._resource), "gate_open": int(self._gate)}
            base["rule_hint"] = "some action effects require observable prerequisites"
        return base

    def render_observation(self) -> str:
        return json.dumps(self.observe(), sort_keys=True, separators=(",", ":"))

    def step(self, action_index: int) -> R18StepResult:
        if self._done:
            raise RuntimeError("task is already done")
        action_index = int(action_index)
        if not 0 <= action_index < len(self._action_kinds):
            raise ValueError("action index out of range")
        kind = self._action_kinds[action_index]
        before_progress = self._progress()
        context_before = self._public_regime() if self.family != "causal_prerequisites" else "prereq"
        first_in_context = (context_before, action_index) not in self._seen_context_actions
        self._seen_context_actions.add((context_before, action_index))
        failed = False
        information = 0.0
        if kind == "submit":
            self._done = True
            self._solved = tuple(self._state) == tuple(self._goal)
            failed = not self._solved
            self._last_event = "accepted" if self._solved else "submission rejected"
        else:
            old_state = tuple(self._state)
            old_resource = self._resource
            old_gate = self._gate
            nxt, resource, gate = self._transition_snapshot(old_state, old_resource, old_gate, kind, self._step_count)
            self._state = list(nxt)
            self._resource = int(resource)
            self._gate = int(gate)
            information = 1.0 if first_in_context else 0.0
            changed = nxt != old_state or resource != old_resource or gate != old_gate
            self._last_event = "observable transition changed state" if changed else "observable transition produced no effect"
        self._step_count += 1
        if not self._done and self.family == "regime_switch":
            after_context = self._public_regime()
            if after_context != context_before:
                self._last_event = "public regime changed after transition"
                information = max(information, 1.0)
        if not self._done and self._step_count >= self._budget:
            self._done = True
            self._solved = False
            failed = True
            self._last_event = "action budget exhausted"
        after_progress = self._progress()
        delta = max(-1.0, min(1.0, after_progress - before_progress))
        if self.family == "implicit_goal_regimes" and kind != "submit" and abs(delta) > 1e-9:
            information = max(information, 0.5)
        return R18StepResult(observation=self.observe(), progress=float(after_progress), progress_delta=float(delta), information_gain=float(information), failed=bool(failed), done=bool(self._done), solved=bool(self._solved))


def make_r18_task(family: str, split: str, index: int) -> R18Task:
    return R18Task(family, split, index)


def _kind_index(task: R18Task, kind: str) -> int:
    return task._action_kinds.index(kind)


def _oracle_signature(task: R18Task, state: tuple[int, ...], resource: int, gate: int, steps: int) -> tuple[Any, ...]:
    if task.family == "regime_switch":
        return state, resource, gate, task._context_index(steps)
    return state, resource, gate


def oracle_plan(task: R18Task) -> list[int]:
    start = tuple(int(v) for v in task._state)
    goal = tuple(int(v) for v in task._goal)
    non_submit = tuple(kind for kind in task._action_kinds if kind != "submit")
    max_depth = task._budget - task._step_count - 1
    queue: deque[tuple[tuple[int, ...], int, int, int, tuple[str, ...]]] = deque([(start, int(task._resource), int(task._gate), int(task._step_count), ())])
    seen = {_oracle_signature(task, start, task._resource, task._gate, task._step_count)}
    while queue:
        state, resource, gate, steps, path = queue.popleft()
        if state == goal:
            return [_kind_index(task, kind) for kind in path] + [_kind_index(task, "submit")]
        if len(path) >= max_depth:
            continue
        for kind in non_submit:
            nxt, next_resource, next_gate = task._transition_snapshot(state, resource, gate, kind, steps)
            next_steps = steps + 1
            signature = _oracle_signature(task, nxt, next_resource, next_gate, next_steps)
            if signature in seen:
                continue
            seen.add(signature)
            queue.append((nxt, next_resource, next_gate, next_steps, path + (kind,)))
    raise RuntimeError(f"oracle could not solve {task.task_id} within budget")


def lock_r18_tasks(tasks: Iterable[R18Task]) -> dict[str, Any]:
    rows = [{"task_id": task.task_id, "family": task.family, "split": task.split, "index": task.index, "seed": task.seed, "actions": list(task.action_descriptions)} for task in tasks]
    payload = {"benchmark": R18_BENCHMARK_VERSION, "tasks": rows}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**payload, "sha256": hashlib.sha256(raw).hexdigest()}
