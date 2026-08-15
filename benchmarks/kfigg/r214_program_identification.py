from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Callable, Iterable

from cogcoder.epistemic_program import Instruction
from cogcoder.r214_active_synthesis import ActiveProgramIdentifier, VersionSpace
from cogcoder.skill_synthesis import BoundedSkillSynthesizer, Demonstration, _apply_instruction

PROBE_DOMAIN = tuple(range(32))
SEARCH_CONFIG = {
    'max_depth': 2,
    'max_candidates': 100_000,
    'max_abs_value': 10**6,
    'add_limit': 8,
    'mul_limit': 4,
    'xor_limit': 15,
    'mod_limit': 17,
}


@dataclass(frozen=True)
class ProgramTask:
    task_id: str
    family: str
    target_path: tuple[Instruction, ...]
    target_signature: tuple[int, ...]
    initial_demos: tuple[Demonstration, ...]
    initial_space: VersionSpace
    oracle: Callable[[int], int]
    identifier: ActiveProgramIdentifier


@dataclass(frozen=True)
class EvaluationRow:
    task_id: str
    family: str
    mode: str
    correct: bool
    resolved: bool
    abstained: bool
    false_resolved_accept: bool
    oracle_calls: int
    initial_demonstrations: tuple[tuple[int, int], ...]
    observations: tuple[tuple[int, int], ...]
    surviving_classes: int
    reason: str


def execute_path(path: Iterable[Instruction], value: int) -> int:
    current = int(value)
    for instruction in path:
        current = _apply_instruction(current, instruction)
    return int(current)


def signature_for(path: Iterable[Instruction], domain: tuple[int, ...] = PROBE_DOMAIN) -> tuple[int, ...]:
    path = tuple(path)
    return tuple(execute_path(path, x) for x in domain)


def _task_id(seed: int, family: str, index: int, path: tuple[Instruction, ...], demo_inputs: tuple[int, ...]) -> str:
    payload = {
        'seed': int(seed), 'family': family, 'index': int(index),
        'path': [(i.op, int(i.arg)) for i in path], 'demo_inputs': list(demo_inputs),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:12]
    return f'r214-{family}-{seed}-{index}-{digest}'


def _identifier() -> ActiveProgramIdentifier:
    return ActiveProgramIdentifier(probe_domain=PROBE_DOMAIN, **SEARCH_CONFIG)


def _make_task(seed: int, family: str, index: int, path: tuple[Instruction, ...], demo_inputs: tuple[int, ...]) -> ProgramTask:
    identifier = _identifier()
    target_signature = signature_for(path)
    oracle = lambda x, _path=path: execute_path(_path, x)
    demos = tuple(Demonstration(x, oracle(x)) for x in sorted(demo_inputs))
    space = identifier.build_version_space(demos)
    return ProgramTask(
        _task_id(seed, family, index, path, tuple(sorted(demo_inputs))), family, path,
        target_signature, demos, space, oracle, identifier,
    )


def _family_path(rng: random.Random, family: str) -> tuple[Instruction, ...]:
    if family == 'xor_add_alias':
        mask = rng.choice((4, 8))
        bias = rng.choice((-3, -2, -1, 1, 2, 3))
        return (Instruction('XOR', mask), Instruction('ADD', bias))
    if family == 'add_mod_wrap':
        add = rng.randint(3, 7)
        valid_mods = [m for m in range(9, 18) if add + 3 < m]
        mod = rng.choice(valid_mods)
        return (Instruction('ADD', add), Instruction('MOD', mod))
    if family == 'mul_mod_wrap':
        mul = rng.randint(2, 4)
        valid_mods = [m for m in range(9, 18) if mul * 3 < m]
        if not valid_mods:
            mul = 2
            valid_mods = [m for m in range(9, 18) if mul * 3 < m]
        mod = rng.choice(valid_mods)
        return (Instruction('MUL', mul), Instruction('MOD', mod))
    if family == 'xor_mod_wrap':
        mask = rng.choice((4, 8))
        low_max = max(x ^ mask for x in range(4))
        valid_mods = [m for m in range(9, 18) if low_max < m]
        mod = rng.choice(valid_mods)
        return (Instruction('XOR', mask), Instruction('MOD', mod))
    raise KeyError(family)


def build_suite(*, seed: int, cases_per_family: int = 24) -> tuple[ProgramTask, ...]:
    rng = random.Random(int(seed))
    families = ('xor_add_alias', 'add_mod_wrap', 'mul_mod_wrap', 'xor_mod_wrap')
    tasks: list[ProgramTask] = []
    for family in families:
        built = 0
        attempts = 0
        while built < int(cases_per_family):
            attempts += 1
            if attempts > 10_000:
                raise RuntimeError(f'could not construct ambiguous tasks for {family}')
            path = _family_path(rng, family)
            demo_inputs = tuple(sorted(rng.sample(range(4), 2)))
            task = _make_task(int(seed), family, built, path, demo_inputs)
            signatures = {row.signature for row in task.initial_space.classes}
            if task.target_signature not in signatures or len(signatures) < 2:
                continue
            tasks.append(task)
            built += 1
    return tuple(tasks)


def build_old_regime_suite(*, seed: int, count: int = 40) -> tuple[ProgramTask, ...]:
    rng = random.Random(int(seed))
    operations = ('ADD', 'MUL', 'XOR', 'MOD')
    tasks: list[ProgramTask] = []
    attempts = 0
    while len(tasks) < int(count):
        attempts += 1
        if attempts > 10_000:
            raise RuntimeError('could not construct old-regime tasks')
        op = operations[len(tasks) % len(operations)]
        if op == 'ADD':
            arg = rng.choice(tuple(x for x in range(-8, 9) if x))
        elif op == 'MUL':
            arg = rng.choice((-4, -3, -2, -1, 2, 3, 4))
        elif op == 'XOR':
            arg = rng.randint(1, 15)
        else:
            arg = rng.randint(2, 17)
        path = (Instruction(op, arg),)
        demo_inputs = tuple(sorted(rng.sample(PROBE_DOMAIN, 4)))
        task = _make_task(int(seed), 'old_regime', len(tasks), path, demo_inputs)
        if task.target_signature not in {row.signature for row in task.initial_space.classes}:
            continue
        tasks.append(task)
    return tuple(tasks)


def build_out_of_class_suite(*, seed: int, count: int = 24) -> tuple[ProgramTask, ...]:
    rng = random.Random(int(seed))
    tasks: list[ProgramTask] = []
    for index in range(int(count)):
        add = rng.randint(1, 8)
        base_path = (Instruction('ADD', add),)
        identifier = _identifier()
        demo_inputs = tuple(sorted(rng.sample(range(4), 2)))
        demo_set = set(demo_inputs)

        def oracle(x: int, _add=add, _demo=frozenset(demo_set)) -> int:
            base = int(x) + int(_add)
            return base if int(x) in _demo else base + 1000

        target_signature = tuple(oracle(x) for x in PROBE_DOMAIN)
        demos = tuple(Demonstration(x, oracle(x)) for x in demo_inputs)
        space = identifier.build_version_space(demos)
        task_id = _task_id(int(seed), 'out_of_class', index, base_path, demo_inputs)
        tasks.append(ProgramTask(task_id, 'out_of_class', base_path, target_signature, demos, space, oracle, identifier))
    return tuple(tasks)


def _row(task: ProgramTask, mode: str, *, resolved: bool, signature: tuple[int, ...] | None,
         oracle_calls: int, observations: tuple[tuple[int, int], ...], surviving: int, reason: str) -> EvaluationRow:
    correct = bool(resolved and signature == task.target_signature)
    false_accept = bool(resolved and signature != task.target_signature)
    return EvaluationRow(
        task.task_id, task.family, mode, correct, bool(resolved), not bool(resolved), false_accept,
        int(oracle_calls), tuple((d.input_value, d.output_value) for d in task.initial_demos),
        observations, int(surviving), str(reason),
    )


def _evaluate_space_policy(task: ProgramTask, mode: str, oracle_budget: int, random_seed: int) -> EvaluationRow:
    space = task.initial_space
    calls = 0
    rng = random.Random(f'{random_seed}:{task.task_id}:{mode}')
    random_order = list(PROBE_DOMAIN)
    rng.shuffle(random_order)

    while len(space.classes) > 1 and calls < int(oracle_budget):
        observed = {x for x, _ in space.observations}
        if mode == 'passive_fixed':
            candidates = [x for x in PROBE_DOMAIN if x not in observed]
            query = candidates[0] if candidates else None
        elif mode == 'random_budgeted':
            candidates = [x for x in random_order if x not in observed]
            query = candidates[0] if candidates else None
        else:
            raise KeyError(mode)
        if query is None:
            break
        output = task.oracle(query)
        calls += 1
        space = task.identifier._filter_space(space, query, output)
        if not space.classes:
            return _row(task, mode, resolved=False, signature=None, oracle_calls=calls,
                        observations=space.observations, surviving=0, reason='no_consistent_program')

    if len(space.classes) == 1:
        chosen = space.classes[0]
        return _row(task, mode, resolved=True, signature=chosen.signature, oracle_calls=calls,
                    observations=space.observations, surviving=1, reason='resolved_unique_semantics')
    return _row(task, mode, resolved=False, signature=None, oracle_calls=calls,
                observations=space.observations, surviving=len(space.classes), reason='oracle_budget_exhausted')


def evaluate_task(task: ProgramTask, *, mode: str, oracle_budget: int = 3, random_seed: int = 0) -> EvaluationRow:
    if mode == 'active':
        result = task.identifier.identify_from_space(task.initial_space, task.oracle, max_oracle_calls=int(oracle_budget))
        return _row(task, mode, resolved=result.resolved, signature=result.signature,
                    oracle_calls=result.oracle_calls, observations=result.observations,
                    surviving=result.surviving_classes, reason=result.reason)
    if mode in {'passive_fixed', 'random_budgeted'}:
        return _evaluate_space_policy(task, mode, int(oracle_budget), int(random_seed))
    if mode == 'shortest_consistent':
        synth = BoundedSkillSynthesizer(**SEARCH_CONFIG)
        result = synth.synthesize(task.task_id, '1', task.initial_demos)
        if not result.resolved or result.program is None:
            return _row(task, mode, resolved=False, signature=None, oracle_calls=0,
                        observations=tuple((d.input_value, d.output_value) for d in task.initial_demos),
                        surviving=0, reason=result.reason)
        signature = signature_for(result.instructions)
        return _row(task, mode, resolved=True, signature=signature, oracle_calls=0,
                    observations=tuple((d.input_value, d.output_value) for d in task.initial_demos),
                    surviving=1, reason='shortest_consistent')
    raise KeyError(mode)

DEPTH3_SEARCH_CONFIG = {
    'max_depth': 3,
    'max_candidates': 200_000,
    'max_abs_value': 10**6,
    'add_limit': 4,
    'mul_limit': 3,
    'xor_limit': 7,
    'mod_limit': 11,
}


def _make_depth3_task(seed: int, family: str, index: int, path: tuple[Instruction, ...], demo_inputs: tuple[int, ...]) -> ProgramTask:
    identifier = ActiveProgramIdentifier(probe_domain=PROBE_DOMAIN, **DEPTH3_SEARCH_CONFIG)
    target_signature = signature_for(path)
    oracle = lambda x, _path=path: execute_path(_path, x)
    demos = tuple(Demonstration(x, oracle(x)) for x in sorted(demo_inputs))
    space = identifier.build_version_space(demos)
    return ProgramTask(
        _task_id(seed, family, index, path, tuple(sorted(demo_inputs))), family, path,
        target_signature, demos, space, oracle, identifier,
    )


def _depth3_path(rng: random.Random, family: str) -> tuple[Instruction, ...]:
    mod = rng.choice((9, 10, 11))
    if family == 'xor_add_mod_depth3':
        return (Instruction('XOR', 4), Instruction('ADD', rng.choice((1, 2))), Instruction('MOD', mod))
    if family == 'mul_add_mod_depth3':
        return (Instruction('MUL', rng.choice((2, 3))), Instruction('ADD', rng.choice((1, 2))), Instruction('MOD', mod))
    if family == 'add_xor_mod_depth3':
        return (Instruction('ADD', rng.choice((1, 2))), Instruction('XOR', 4), Instruction('MOD', mod))
    if family == 'mul_xor_mod_depth3':
        return (Instruction('MUL', rng.choice((2, 3))), Instruction('XOR', 4), Instruction('MOD', mod))
    raise KeyError(family)


def build_depth3_stress_suite(*, seed: int, cases_per_family: int = 12) -> tuple[ProgramTask, ...]:
    rng = random.Random(int(seed))
    families = ('xor_add_mod_depth3', 'mul_add_mod_depth3', 'add_xor_mod_depth3', 'mul_xor_mod_depth3')
    tasks: list[ProgramTask] = []
    for family in families:
        built = 0
        attempts = 0
        while built < int(cases_per_family):
            attempts += 1
            if attempts > 10_000:
                raise RuntimeError(f'could not construct depth3 stress tasks for {family}')
            path = _depth3_path(rng, family)
            demo_inputs = tuple(sorted(rng.sample(range(4), 2)))
            task = _make_depth3_task(int(seed), family, built, path, demo_inputs)
            signatures = {row.signature for row in task.initial_space.classes}
            if not task.initial_space.enumeration_complete:
                continue
            if task.target_signature not in signatures or len(signatures) < 2:
                continue
            tasks.append(task)
            built += 1
    return tuple(tasks)


def _accuracy(rows: Iterable[EvaluationRow]) -> float:
    rows = tuple(rows)
    return 0.0 if not rows else sum(int(row.correct) for row in rows) / len(rows)


def measure_seed(
    *,
    seed: int,
    cases_per_family: int = 24,
    depth3_cases_per_family: int = 8,
    old_count: int = 40,
    out_of_class_count: int = 24,
) -> dict:
    main = build_suite(seed=int(seed), cases_per_family=int(cases_per_family))
    depth3 = build_depth3_stress_suite(seed=int(seed) + 10_000, cases_per_family=int(depth3_cases_per_family))
    old = build_old_regime_suite(seed=int(seed) + 20_000, count=int(old_count))
    out_of_class = build_out_of_class_suite(seed=int(seed) + 30_000, count=int(out_of_class_count))

    modes = ('active', 'shortest_consistent', 'passive_fixed', 'random_budgeted')
    main_rows = {
        mode: tuple(evaluate_task(task, mode=mode, oracle_budget=3, random_seed=int(seed) + 41) for task in main)
        for mode in modes
    }
    depth3_rows = {
        mode: tuple(evaluate_task(task, mode=mode, oracle_budget=3, random_seed=int(seed) + 43) for task in depth3)
        for mode in ('active', 'passive_fixed', 'random_budgeted')
    }
    retention_rows = tuple(evaluate_task(task, mode='active', oracle_budget=3, random_seed=int(seed) + 47) for task in old)
    ooc_rows = tuple(evaluate_task(task, mode='active', oracle_budget=3, random_seed=int(seed) + 53) for task in out_of_class)

    budget_curve = {}
    for budget in range(4):
        rows = tuple(evaluate_task(task, mode='active', oracle_budget=budget, random_seed=int(seed) + 59) for task in main)
        budget_curve[str(budget)] = _accuracy(rows)

    invariant = 0
    for task in main:
        original = task.identifier.identify_from_space(task.initial_space, task.oracle, max_oracle_calls=3)
        reversed_space = VersionSpace(
            task.initial_space.probe_domain,
            tuple(reversed(task.initial_space.classes)),
            task.initial_space.observations,
            task.initial_space.candidates_evaluated,
            task.initial_space.enumeration_complete,
        )
        permuted = task.identifier.identify_from_space(reversed_space, task.oracle, max_oracle_calls=3)
        invariant += int(original == permuted)

    all_active_rows = main_rows['active'] + depth3_rows['active'] + retention_rows + ooc_rows
    return {
        'seed': int(seed),
        'main_cases': len(main),
        'depth3_cases': len(depth3),
        'old_regime_cases': len(old),
        'out_of_class_cases': len(out_of_class),
        'main_accuracy': {mode: _accuracy(main_rows[mode]) for mode in modes},
        'depth3_accuracy': {mode: _accuracy(depth3_rows[mode]) for mode in depth3_rows},
        'retention_accuracy': _accuracy(retention_rows),
        'out_of_class_abstention': 0.0 if not ooc_rows else sum(int(row.abstained) for row in ooc_rows) / len(ooc_rows),
        'out_of_class_false_resolved_accepts': sum(int(row.false_resolved_accept) for row in ooc_rows),
        'false_resolved_accepts_all_active': sum(int(row.false_resolved_accept) for row in all_active_rows),
        'max_active_oracle_calls': max((row.oracle_calls for row in all_active_rows), default=0),
        'identity_permutation_invariance': 0.0 if not main else invariant / len(main),
        'budget_curve': budget_curve,
    }
