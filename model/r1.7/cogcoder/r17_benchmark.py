from __future__ import annotations

import copy
import hashlib
import json
import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

R17_BENCHMARK_VERSION = "nolane-figg17-v1"
R17_FAMILIES = (
    "causal_laws",
    "causal_switch",
    "goal_inference",
    "composition_holdout",
)
R17_SPLIT_BASE_SEEDS = {
    "train": 17_100_000,
    "dev": 17_200_000,
    "fresh": 17_900_000,
}


@dataclass(frozen=True)
class R17StepResult:
    observation: dict[str, Any]
    progress: float
    progress_delta: float
    information_gain: float
    failed: bool
    done: bool
    solved: bool


def _stable_seed(split: str, family: str, index: int) -> int:
    if split not in R17_SPLIT_BASE_SEEDS:
        raise ValueError(f"unknown split: {split}")
    if family not in R17_FAMILIES:
        raise ValueError(f"unknown family: {family}")
    if index < 0:
        raise ValueError("index must be non-negative")
    family_index = R17_FAMILIES.index(family)
    return R17_SPLIT_BASE_SEEDS[split] + family_index * 100_003 + index * 997 + 71


def _mod_forward_distance(value: int, target: int, modulus: int) -> int:
    return (int(target) - int(value)) % int(modulus)


def _apply_rule(values: Sequence[int], op: str) -> tuple[int, ...]:
    row = tuple(int(v) for v in values)
    if op == "rotate_left":
        return row[1:] + row[:1]
    if op == "reverse":
        return tuple(reversed(row))
    if op == "add_one":
        return tuple((v + 1) % 7 for v in row)
    if op == "swap_pairs":
        if len(row) != 4:
            raise ValueError("swap_pairs requires length four")
        return (row[1], row[0], row[3], row[2])
    if op == "double_mod":
        return tuple((2 * v) % 7 for v in row)
    raise ValueError(op)


def _run_program(values: Sequence[int], program: Sequence[str]) -> tuple[int, ...]:
    out = tuple(int(v) for v in values)
    for op in program:
        out = _apply_rule(out, op)
    return out


TRAIN_PROGRAMS: tuple[tuple[str, ...], ...] = (
    ("rotate_left", "add_one"),
    ("reverse", "add_one"),
    ("swap_pairs", "reverse"),
    ("add_one", "rotate_left"),
    ("double_mod", "reverse"),
    ("rotate_left", "double_mod"),
    ("add_one", "swap_pairs"),
    ("double_mod", "add_one"),
)
DEV_PROGRAMS: tuple[tuple[str, ...], ...] = (
    ("reverse", "rotate_left", "add_one"),
    ("swap_pairs", "add_one", "rotate_left"),
    ("double_mod", "swap_pairs", "reverse"),
    ("add_one", "double_mod", "rotate_left"),
    ("rotate_left", "swap_pairs", "double_mod"),
    ("reverse", "double_mod", "add_one"),
)
FRESH_PROGRAMS: tuple[tuple[str, ...], ...] = (
    ("double_mod", "rotate_left", "add_one", "reverse"),
    ("swap_pairs", "double_mod", "add_one", "rotate_left"),
    ("reverse", "add_one", "swap_pairs", "double_mod"),
    ("rotate_left", "reverse", "double_mod", "add_one"),
    ("add_one", "rotate_left", "swap_pairs", "reverse"),
    ("double_mod", "reverse", "rotate_left", "swap_pairs"),
)
PROGRAMS_BY_SPLIT = {
    "train": TRAIN_PROGRAMS,
    "dev": DEV_PROGRAMS,
    "fresh": FRESH_PROGRAMS,
}


class R17Task:
    """Interactive procedural task with an explicit public/private boundary."""

    def __init__(self, family: str, split: str, index: int) -> None:
        if family not in R17_FAMILIES:
            raise ValueError(f"unknown family: {family}")
        if split not in R17_SPLIT_BASE_SEEDS:
            raise ValueError(f"unknown split: {split}")
        self.family = family
        self.split = split
        self.index = int(index)
        self.seed = _stable_seed(split, family, index)
        self.task_id = f"{R17_BENCHMARK_VERSION}:{split}:{family}:{self.seed}"
        self._rng = random.Random(self.seed ^ 0x17C0A51)
        self._step_count = 0
        self._done = False
        self._solved = False
        self._last_event = "episode started"
        self._seen_actions: set[int] = set()

        if family == "causal_laws":
            self._init_causal_laws()
        elif family == "causal_switch":
            self._init_causal_switch()
        elif family == "goal_inference":
            self._init_goal_inference()
        else:
            self._init_composition()

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
    def action_descriptions(self) -> tuple[str, ...]:
        return self._action_descriptions

    @property
    def switch_after(self) -> int:
        if self.family != "causal_switch":
            raise AttributeError("switch_after is only defined for causal_switch")
        return int(self._switch_after)

    @property
    def oracle_program(self) -> tuple[str, ...]:
        if self.family != "composition_holdout":
            raise AttributeError("oracle_program is only defined for composition_holdout")
        return tuple(self._program)

    def _shuffle_actions(self, actions: list[tuple[str, str]]) -> None:
        self._rng.shuffle(actions)
        self._action_kinds = tuple(kind for kind, _ in actions)
        self._action_descriptions = tuple(desc for _, desc in actions)

    def _opaque_labels(self, count: int) -> list[str]:
        syllables = ["Nox", "Vela", "Iri", "Kest", "Pru", "Senn", "Tavi", "Orn"]
        self._rng.shuffle(syllables)
        return [f"{syllables[i]}-{(self.seed + i * 13) % 97:02d}" for i in range(count)]

    def _init_causal_laws(self) -> None:
        self._modulus = 5
        self._state = [0, 0, 0]
        goal = [self._rng.randrange(self._modulus) for _ in range(3)]
        while goal == [0, 0, 0] or sum(goal) < 4:
            goal = [self._rng.randrange(self._modulus) for _ in range(3)]
        self._goal = tuple(goal)
        dimensions = [0, 1, 2]
        self._rng.shuffle(dimensions)
        labels = self._opaque_labels(3)
        self._laws: dict[str, tuple[int, int, int]] = {}
        actions: list[tuple[str, str]] = []
        for actuator_index, (label, dimension) in enumerate(zip(labels, dimensions)):
            condition_dim = (dimension + 1 + actuator_index) % 3
            even_delta = 1 + self._rng.randrange(2)
            odd_delta = 3 - even_delta
            kind = f"act:{actuator_index}"
            self._laws[kind] = (dimension, condition_dim, even_delta * 10 + odd_delta)
            actions.append((kind, f"opaque actuator {label}"))
        actions.append(("submit", "submit current hypothesis"))
        self._shuffle_actions(actions)
        self._budget = 30

    def _init_causal_switch(self) -> None:
        self._modulus = 4
        self._state = [0, 0, 0]
        goal = [self._rng.randrange(self._modulus) for _ in range(3)]
        while sum(goal) < 5:
            goal = [self._rng.randrange(self._modulus) for _ in range(3)]
        self._goal = tuple(goal)
        self._switch_after = 4
        self._context_names = ("amber", "violet")
        base = [0, 1, 2]
        p0 = base[:]
        p1 = base[:]
        self._rng.shuffle(p0)
        self._rng.shuffle(p1)
        while p1 == p0:
            self._rng.shuffle(p1)
        self._switch_maps = (tuple(p0), tuple(p1))
        labels = self._opaque_labels(3)
        actions = [(f"act:{i}", f"opaque actuator {label}") for i, label in enumerate(labels)]
        actions.append(("submit", "submit current hypothesis"))
        self._shuffle_actions(actions)
        self._budget = 24

    def _init_goal_inference(self) -> None:
        self._modulus = 4
        self._state = [0, 0, 0]
        goal = [self._rng.randrange(self._modulus) for _ in range(3)]
        while goal == [0, 0, 0] or sum(goal) < 3:
            goal = [self._rng.randrange(self._modulus) for _ in range(3)]
        self._goal = tuple(goal)
        dimensions = [0, 1, 2]
        self._rng.shuffle(dimensions)
        self._goal_map = tuple(dimensions)
        labels = self._opaque_labels(3)
        actions = [(f"act:{i}", f"opaque actuator {label}") for i, label in enumerate(labels)]
        actions.append(("submit", "submit current hypothesis"))
        self._shuffle_actions(actions)
        self._budget = 24

    def _init_composition(self) -> None:
        programs = PROGRAMS_BY_SPLIT[self.split]
        self._program = tuple(programs[self.index % len(programs)])
        ops = ["rotate_left", "reverse", "add_one", "swap_pairs", "double_mod"]
        descriptions = {
            "rotate_left": "rotate vector one cell left",
            "reverse": "reverse vector order",
            "add_one": "add one modulo seven to each value",
            "swap_pairs": "swap adjacent pairs",
            "double_mod": "double each value modulo seven",
        }
        demos: list[dict[str, list[int]]] = []
        for _ in range(4):
            row = tuple(self._rng.randrange(7) for _ in range(4))
            demos.append({"input": list(row), "output": list(_run_program(row, self._program))})
        self._demos = tuple(demos)
        self._state = [self._rng.randrange(7) for _ in range(4)]
        self._goal = _run_program(self._state, self._program)
        actions = [(op, descriptions[op]) for op in ops]
        actions.append(("submit", "submit current hypothesis"))
        self._shuffle_actions(actions)
        self._budget = 12

    def _context_index(self, step_count: int | None = None) -> int:
        if self.family != "causal_switch":
            return 0
        count = self._step_count if step_count is None else int(step_count)
        return 0 if count < self._switch_after else 1

    def _progress(self) -> float:
        if self.family == "composition_holdout":
            matches = sum(int(a == b) for a, b in zip(self._state, self._goal))
            return matches / 4.0
        distance = sum(
            _mod_forward_distance(v, g, self._modulus)
            for v, g in zip(self._state, self._goal)
        )
        return 1.0 - distance / (len(self._state) * (self._modulus - 1))

    def observe(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "benchmark": R17_BENCHMARK_VERSION,
            "family": self.family,
            "task_id": self.task_id,
            "step": self._step_count,
            "budget_remaining": max(0, self._budget - self._step_count),
            "last_event": self._last_event,
            "actions": list(self._action_descriptions),
        }
        if self.family == "causal_laws":
            base.update({"state": list(self._state), "goal": list(self._goal), "rule_hint": "effects may depend on the current observable configuration"})
        elif self.family == "causal_switch":
            base.update({"state": list(self._state), "goal": list(self._goal), "context": self._context_names[self._context_index()], "rule_hint": "the public context can change how actuators affect the state"})
        elif self.family == "goal_inference":
            base.update({"state": list(self._state), "feedback_hint": "infer the desired configuration from progress feedback"})
        else:
            base.update({"demonstrations": [copy.deepcopy(d) for d in self._demos], "test_state": list(self._state), "rule_hint": "infer a transformation consistent with the demonstrations"})
        return base

    def render_observation(self) -> str:
        return json.dumps(self.observe(), sort_keys=True, separators=(",", ":"))

    def _causal_law_delta(self, kind: str, state: Sequence[int]) -> tuple[int, int]:
        dimension, condition_dim, packed = self._laws[kind]
        even_delta, odd_delta = divmod(packed, 10)
        delta = even_delta if int(state[condition_dim]) % 2 == 0 else odd_delta
        return int(dimension), int(delta)

    def _transition_state(self, state: tuple[int, ...], kind: str, step_count: int) -> tuple[int, ...]:
        if kind == "submit":
            return state
        row = list(state)
        if self.family == "causal_laws":
            dim, delta = self._causal_law_delta(kind, state)
            row[dim] = (row[dim] + delta) % self._modulus
        elif self.family == "causal_switch":
            actuator = int(kind.split(":", 1)[1])
            context = 0 if step_count < self._switch_after else 1
            dim = self._switch_maps[context][actuator]
            row[dim] = (row[dim] + 1) % self._modulus
        elif self.family == "goal_inference":
            actuator = int(kind.split(":", 1)[1])
            dim = self._goal_map[actuator]
            row[dim] = (row[dim] + 1) % self._modulus
        else:
            row = list(_apply_rule(row, kind))
        return tuple(row)

    def step(self, action_index: int) -> R17StepResult:
        if self._done:
            raise RuntimeError("task is already done")
        action_index = int(action_index)
        if not 0 <= action_index < len(self._action_kinds):
            raise ValueError("action index out of range")
        before = self._progress()
        kind = self._action_kinds[action_index]
        first_use = action_index not in self._seen_actions
        self._seen_actions.add(action_index)
        failed = False
        information = 0.0
        if kind == "submit":
            self._done = True
            self._solved = tuple(self._state) == tuple(self._goal)
            failed = not self._solved
            self._last_event = "accepted" if self._solved else "submission rejected"
        else:
            prior_context = self._context_index()
            self._state = list(self._transition_state(tuple(self._state), kind, self._step_count))
            information = 1.0 if first_use else 0.0
            self._last_event = "observable state changed"
            if self.family == "goal_inference":
                self._last_event = "observable state changed; progress feedback updated"
            elif self.family == "causal_switch" and prior_context == 0 and self._step_count + 1 >= self._switch_after:
                self._last_event = "public context changed after the action"
        self._step_count += 1
        if not self._done and self._step_count >= self._budget:
            self._done = True
            self._solved = False
            failed = True
            self._last_event = "action budget exhausted"
        after = self._progress()
        delta = max(-1.0, min(1.0, after - before))
        if self.family == "goal_inference" and kind != "submit" and abs(delta) > 1e-9:
            information = max(information, 0.5)
        return R17StepResult(observation=self.observe(), progress=float(after), progress_delta=float(delta), information_gain=float(information), failed=bool(failed), done=bool(self._done), solved=bool(self._solved))


def make_r17_task(family: str, split: str, index: int) -> R17Task:
    return R17Task(family, split, index)


def build_r17_split(split: str, *, per_family: int) -> list[R17Task]:
    if per_family < 1:
        raise ValueError("per_family must be positive")
    return [make_r17_task(family, split, index) for family in R17_FAMILIES for index in range(per_family)]


def _kind_index(task: R17Task, kind: str) -> int:
    return task._action_kinds.index(kind)


def _bfs_plan(task: R17Task) -> list[int]:
    start = tuple(int(v) for v in task._state)
    goal = tuple(int(v) for v in task._goal)
    non_submit = [kind for kind in task._action_kinds if kind != "submit"]
    queue: deque[tuple[tuple[int, ...], int, tuple[str, ...]]] = deque([(start, task._step_count, ())])
    seen: set[tuple[tuple[int, ...], int]] = {(start, task._context_index(task._step_count))}
    max_depth = task._budget - task._step_count - 1
    while queue:
        state, steps, path = queue.popleft()
        if state == goal:
            return [_kind_index(task, kind) for kind in path] + [_kind_index(task, "submit")]
        if len(path) >= max_depth:
            continue
        for kind in non_submit:
            nxt = task._transition_state(state, kind, steps)
            next_steps = steps + 1
            signature = (nxt, task._context_index(next_steps))
            if signature in seen:
                continue
            seen.add(signature)
            queue.append((nxt, next_steps, path + (kind,)))
    raise RuntimeError(f"oracle could not solve {task.task_id} within budget")


def oracle_plan(task: R17Task) -> list[int]:
    if task.family == "composition_holdout":
        return [_kind_index(task, op) for op in task._program] + [_kind_index(task, "submit")]
    return _bfs_plan(task)


def evaluate_action_efficiency(*, reference_actions: int, used_actions: int, solved: bool) -> dict[str, float]:
    reference_actions = int(reference_actions)
    used_actions = int(used_actions)
    if reference_actions < 1 or used_actions < 1:
        raise ValueError("action counts must be positive")
    completion = 1.0 if solved else 0.0
    efficiency = min(1.0, reference_actions / used_actions) if solved else 0.0
    return {"completion": completion, "action_efficiency": float(efficiency)}


def lock_r17_tasks(tasks: Iterable[R17Task]) -> dict[str, Any]:
    rows = [{"task_id": task.task_id, "family": task.family, "split": task.split, "index": task.index, "seed": task.seed, "actions": list(task.action_descriptions)} for task in tasks]
    payload = {"benchmark": R17_BENCHMARK_VERSION, "tasks": rows}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**payload, "sha256": hashlib.sha256(raw).hexdigest()}
