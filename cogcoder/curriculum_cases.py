from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Iterable

from .epistemic_program import Instruction
from .skill_synthesis import Demonstration


@dataclass(frozen=True)
class TeachingBatch:
    skill_name: str
    version: str
    demonstrations: tuple[Demonstration, ...]
    source_uri: str


@dataclass(frozen=True)
class SkillQuery:
    query_id: str
    kind: str
    skill_names: tuple[str, ...]
    input_value: int


@dataclass(frozen=True)
class KFIGG23PublicCase:
    seed: int
    initial_teachings: tuple[TeachingBatch, ...]
    intervening_teachings: tuple[TeachingBatch, ...]
    revision_teaching: TeachingBatch
    queries: tuple[SkillQuery, ...]


@dataclass(frozen=True)
class KFIGG23Case:
    public: KFIGG23PublicCase
    expected_answers: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class KFIGG23SolverResult:
    answers: dict[str, int | None]
    demonstrations_observed: int
    integrity_failures: int
    synthesis_failures: int = 0


def _apply(path: tuple[Instruction, ...], value: int) -> int:
    current = int(value)
    for ins in path:
        arg = int(ins.arg)
        if ins.op == 'ADD':
            current += arg
        elif ins.op == 'MUL':
            current *= arg
        elif ins.op == 'XOR':
            current ^= arg
        elif ins.op == 'MOD':
            current %= arg
        else:
            raise ValueError(ins.op)
    return int(current)


def _name(rng: random.Random, index: int) -> str:
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
    return f'S{alphabet[rng.randrange(len(alphabet))]}{rng.randrange(1000, 9999)}_{index}'


def _rule(rng: random.Random) -> tuple[Instruction, ...]:
    template = rng.randrange(5)
    add = rng.choice([x for x in range(-9, 10) if x])
    mul = rng.choice((-4, -3, -2, -1, 2, 3, 4))
    xor = rng.randint(1, 15)
    if template == 0:
        return (Instruction('ADD', add),)
    if template == 1:
        return (Instruction('MUL', mul), Instruction('ADD', add))
    if template == 2:
        return (Instruction('XOR', xor), Instruction('ADD', add))
    if template == 3:
        return (Instruction('ADD', add), Instruction('MUL', mul))
    return (Instruction('MUL', mul), Instruction('XOR', xor))


def _inputs(rng: random.Random, count: int, *, required: int | None = None) -> tuple[int, ...]:
    values: set[int] = set()
    if required is not None:
        values.add(int(required))
    while len(values) < count:
        values.add(rng.randint(-12, 18))
    return tuple(sorted(values))


def _teach(name: str, version: str, rule: tuple[Instruction, ...], xs: tuple[int, ...], seed: int) -> TeachingBatch:
    return TeachingBatch(
        name,
        str(version),
        tuple(Demonstration(x, _apply(rule, x)) for x in xs),
        f'kfigg23://{seed}/{name}/v{version}',
    )


def _query_input(rng: random.Random, teaching: TeachingBatch, seen_probability: float) -> int:
    seen = tuple(d.input_value for d in teaching.demonstrations)
    if rng.random() < seen_probability:
        return int(rng.choice(seen))
    choices = [x for x in range(-24, 25) if x not in set(seen)]
    return int(rng.choice(choices))


def make_kfigg23_case(
    *,
    seed: int,
    seen_probability: float = 0.35,
    composition_seen_probability: float = 0.25,
    demonstrations_per_skill: int = 5,
) -> KFIGG23Case:
    if demonstrations_per_skill < 2:
        raise ValueError('demonstrations_per_skill must be at least 2')
    rng = random.Random(int(seed))
    names = tuple(_name(rng, i) for i in range(3))
    a1, b1, c1 = (_rule(rng) for _ in range(3))
    b2 = _rule(rng)
    while b2 == b1:
        b2 = _rule(rng)

    a_inputs = _inputs(rng, demonstrations_per_skill)
    a = _teach(names[0], '1', a1, a_inputs, int(seed))
    bridge_input = int(rng.choice(a_inputs))
    bridge_value = _apply(a1, bridge_input)
    b = _teach(names[1], '1', b1, _inputs(rng, demonstrations_per_skill), int(seed))
    c = _teach(names[2], '1', c1, _inputs(rng, demonstrations_per_skill, required=bridge_value), int(seed))
    b_new = _teach(names[1], '2', b2, _inputs(rng, demonstrations_per_skill), int(seed))

    induction_input = _query_input(rng, a, seen_probability)
    retention_input = _query_input(rng, a, seen_probability)
    revision_input = _query_input(rng, b_new, seen_probability)
    if rng.random() < composition_seen_probability:
        composition_input = bridge_input
    else:
        c_seen = {d.input_value for d in c.demonstrations}
        choices = [x for x in range(-24, 25) if x not in set(a_inputs) and _apply(a1, x) not in c_seen]
        composition_input = int(rng.choice(choices))

    queries = (
        SkillQuery('induction', 'induction', (names[0],), induction_input),
        SkillQuery('retention', 'retention', (names[0],), retention_input),
        SkillQuery('revision', 'revision', (names[1],), revision_input),
        SkillQuery('composition', 'composition', (names[0], names[2]), composition_input),
    )
    answers = (
        ('induction', _apply(a1, induction_input)),
        ('retention', _apply(a1, retention_input)),
        ('revision', _apply(b2, revision_input)),
        ('composition', _apply(c1, _apply(a1, composition_input))),
    )
    return KFIGG23Case(KFIGG23PublicCase(int(seed), (a,), (b, c), b_new, queries), answers)
