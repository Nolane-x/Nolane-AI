from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from .epistemic_program import EpistemicProgram, Instruction

SAFE_SYNTHESIS_OPS = frozenset({'ADD', 'MUL', 'XOR', 'MOD'})


def _path_key(path: tuple[Instruction, ...]) -> tuple[tuple[str, int], ...]:
    return tuple((instruction.op, int(instruction.arg)) for instruction in path)


@dataclass(frozen=True)
class Demonstration:
    input_value: int
    output_value: int


@dataclass(frozen=True)
class SynthesisResult:
    resolved: bool
    reason: str
    instructions: tuple[Instruction, ...]
    program: EpistemicProgram | None
    candidates_evaluated: int
    minimal_depth: int | None


def _apply_instruction(value: int, instruction: Instruction) -> int:
    arg = int(instruction.arg)
    if instruction.op == 'ADD':
        return value + arg
    if instruction.op == 'MUL':
        return value * arg
    if instruction.op == 'XOR':
        return value ^ arg
    if instruction.op == 'MOD':
        return value % arg
    raise ValueError(f'unsupported synthesis opcode: {instruction.op}')


def _demo_digest(name: str, version: str, demos: tuple[Demonstration, ...]) -> str:
    payload = {
        'name': str(name),
        'version': str(version),
        'demonstrations': [(int(d.input_value), int(d.output_value)) for d in demos],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class BoundedSkillSynthesizer:
    trainable_parameter_count = 0

    def __init__(
        self,
        *,
        max_depth: int = 3,
        max_candidates: int = 100_000,
        max_abs_value: int = 10**9,
        add_limit: int = 12,
        mul_limit: int = 5,
        xor_limit: int = 15,
        mod_limit: int = 31,
    ):
        if max_depth < 1:
            raise ValueError('max_depth must be positive')
        if max_candidates < 1:
            raise ValueError('max_candidates must be positive')
        self.max_depth = int(max_depth)
        self.max_candidates = int(max_candidates)
        self.max_abs_value = int(max_abs_value)
        self._instructions = self._make_instruction_space(add_limit, mul_limit, xor_limit, mod_limit)

    @staticmethod
    def _make_instruction_space(add_limit: int, mul_limit: int, xor_limit: int, mod_limit: int) -> tuple[Instruction, ...]:
        rows: list[Instruction] = []
        rows.extend(Instruction('ADD', arg) for arg in range(-int(add_limit), int(add_limit) + 1) if arg != 0)
        rows.extend(Instruction('MUL', arg) for arg in range(-int(mul_limit), int(mul_limit) + 1) if arg not in (0, 1))
        rows.extend(Instruction('XOR', arg) for arg in range(1, int(xor_limit) + 1))
        rows.extend(Instruction('MOD', arg) for arg in range(2, int(mod_limit) + 1))
        return tuple(rows)

    @staticmethod
    def _normalize_demonstrations(demonstrations: Iterable[Demonstration]) -> tuple[Demonstration, ...]:
        by_input: dict[int, int] = {}
        for demo in demonstrations:
            x, y = int(demo.input_value), int(demo.output_value)
            previous = by_input.get(x)
            if previous is not None and previous != y:
                raise ValueError('conflicting demonstrations for the same input')
            by_input[x] = y
        if len(by_input) < 2:
            raise ValueError('at least two distinct demonstrations are required')
        return tuple(Demonstration(x, by_input[x]) for x in sorted(by_input))

    def synthesize(
        self,
        name: str,
        version: str,
        demonstrations: Iterable[Demonstration],
    ) -> SynthesisResult:
        if not str(name):
            raise ValueError('skill name must be non-empty')
        demos = self._normalize_demonstrations(demonstrations)
        start_signature = tuple(d.input_value for d in demos)
        target_signature = tuple(d.output_value for d in demos)
        if start_signature == target_signature:
            return SynthesisResult(False, 'identity_skill_not_installed', (), None, 0, 0)

        frontier: dict[tuple[int, ...], tuple[Instruction, ...]] = {start_signature: ()}
        candidates_evaluated = 0

        for depth in range(1, self.max_depth + 1):
            next_frontier: dict[tuple[int, ...], tuple[Instruction, ...]] = {}
            target_paths: list[tuple[Instruction, ...]] = []
            for signature, path in sorted(frontier.items(), key=lambda item: (_path_key(item[1]), item[0])):
                for instruction in self._instructions:
                    candidates_evaluated += 1
                    if candidates_evaluated > self.max_candidates:
                        return SynthesisResult(False, 'candidate_budget_exhausted', (), None, candidates_evaluated - 1, None)
                    try:
                        out = tuple(_apply_instruction(v, instruction) for v in signature)
                    except (ArithmeticError, ValueError, OverflowError):
                        continue
                    if any(abs(v) > self.max_abs_value for v in out):
                        continue
                    new_path = path + (instruction,)
                    if out == target_signature:
                        target_paths.append(new_path)
                        continue
                    previous = next_frontier.get(out)
                    if previous is None or _path_key(new_path) < _path_key(previous):
                        next_frontier[out] = new_path
            if target_paths:
                target_paths = sorted(set(target_paths), key=_path_key)
                chosen = target_paths[0]
                digest = _demo_digest(str(name), str(version), demos)
                program = EpistemicProgram(
                    str(name),
                    chosen,
                    (f'demo:{digest}',),
                    (digest,),
                    (f'demonstration://{name}',),
                    (str(version),),
                )
                return SynthesisResult(True, 'resolved', chosen, program, candidates_evaluated, depth)
            frontier = next_frontier
            if not frontier:
                break

        return SynthesisResult(False, 'no_consistent_program', (), None, candidates_evaluated, None)
