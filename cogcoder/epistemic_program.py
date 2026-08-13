from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable

from .knowledge_types import EvidenceChunk

_HEADER = re.compile(r'^\s*PROGRAM\s+([A-Za-z_][A-Za-z0-9_]*)\s*::\s*(.+?)\s*$')
_INT_OPS = {'ADD', 'MUL', 'MOD', 'XOR', 'MIN', 'MAX'}


@dataclass(frozen=True)
class Instruction:
    op: str
    arg: int | str


@dataclass(frozen=True)
class EpistemicProgram:
    name: str
    instructions: tuple[Instruction, ...]
    evidence_chunk_ids: tuple[str, ...]
    evidence_sha256: tuple[str, ...]
    source_uris: tuple[str, ...]
    versions: tuple[str, ...]


def compile_program_chunk(chunk: EvidenceChunk) -> EpistemicProgram:
    if hashlib.sha256(chunk.text.encode()).hexdigest() != chunk.content_sha256:
        raise ValueError('program evidence content hash mismatch')
    match = _HEADER.match(chunk.text.strip())
    if not match:
        raise ValueError('unsupported program document syntax')
    name = match.group(1)
    instructions = []
    for raw in match.group(2).split('|'):
        parts = raw.strip().split()
        if len(parts) != 2:
            raise ValueError(f'unsupported instruction: {raw.strip()}')
        op, arg_text = parts[0].upper(), parts[1]
        if op == 'CALL':
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', arg_text):
                raise ValueError('invalid CALL target')
            instructions.append(Instruction(op, arg_text))
            continue
        if op not in _INT_OPS:
            raise ValueError(f'unsupported instruction: {op}')
        try:
            arg = int(arg_text)
        except ValueError as exc:
            raise ValueError(f'{op} requires integer argument') from exc
        if op == 'MOD' and arg == 0:
            raise ValueError('MOD by zero')
        instructions.append(Instruction(op, arg))
    if not instructions:
        raise ValueError('program must contain at least one instruction')
    return EpistemicProgram(
        name,
        tuple(instructions),
        (chunk.chunk_id,),
        (chunk.content_sha256,),
        (chunk.source_uri,),
        (chunk.version,),
    )


class ProgramRegistry:
    trainable_parameter_count = 0

    def __init__(self, programs: Iterable[EpistemicProgram] = (), *, max_steps: int = 64, max_abs_value: int = 10**12):
        if max_steps < 1:
            raise ValueError('max_steps must be positive')
        self.max_steps = int(max_steps)
        self.max_abs_value = int(max_abs_value)
        self._programs: dict[str, EpistemicProgram] = {}
        for program in programs:
            self.register(program)

    def register(self, program: EpistemicProgram) -> None:
        previous = self._programs.get(program.name)
        if previous is not None and previous != program:
            raise ValueError(f'program name collision: {program.name}')
        self._programs[program.name] = program

    def has(self, name: str) -> bool:
        return name in self._programs

    def execute(self, name: str, value: int) -> int:
        state = {'steps': 0, 'stack': []}
        return self._execute(name, int(value), state)

    def _execute(self, name: str, value: int, state: dict) -> int:
        if name not in self._programs:
            raise KeyError(name)
        if name in state['stack']:
            raise RuntimeError('program call cycle detected')
        state['stack'].append(name)
        try:
            for instruction in self._programs[name].instructions:
                state['steps'] += 1
                if state['steps'] > self.max_steps:
                    raise RuntimeError('program step budget exhausted')
                if instruction.op == 'CALL':
                    value = self._execute(str(instruction.arg), value, state)
                else:
                    arg = int(instruction.arg)
                    if instruction.op == 'ADD': value += arg
                    elif instruction.op == 'MUL': value *= arg
                    elif instruction.op == 'MOD': value %= arg
                    elif instruction.op == 'XOR': value ^= arg
                    elif instruction.op == 'MIN': value = min(value, arg)
                    elif instruction.op == 'MAX': value = max(value, arg)
                    else: raise RuntimeError('unreachable instruction')
                if abs(value) > self.max_abs_value:
                    raise RuntimeError('program value bound exceeded')
            return int(value)
        finally:
            state['stack'].pop()

    def missing_dependencies(self, name: str) -> tuple[str, ...]:
        if name not in self._programs:
            raise KeyError(name)
        missing = sorted({str(i.arg) for i in self._programs[name].instructions if i.op == 'CALL' and str(i.arg) not in self._programs})
        return tuple(missing)

    def provenance(self, name: str) -> dict[str, tuple[str, ...]]:
        program = self._programs[name]
        return {
            'evidence_chunk_ids': program.evidence_chunk_ids,
            'evidence_sha256': program.evidence_sha256,
            'source_uris': program.source_uris,
            'versions': program.versions,
        }
