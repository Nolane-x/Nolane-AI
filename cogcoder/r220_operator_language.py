from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass


def _bits(state):
    out = tuple(int(v) for v in tuple(state))
    if not out or any(v not in (0, 1) for v in out):
        raise ValueError('state must be a non-empty binary tuple')
    return out


@dataclass(frozen=True)
class OperatorProgram:
    op: str
    args: tuple = ()
    children: tuple['OperatorProgram', ...] = ()

    @staticmethod
    def identity():
        return OperatorProgram('identity')

    @staticmethod
    def xor_mask(mask):
        mask = tuple(int(v) for v in tuple(mask))
        if not mask or any(v not in (0, 1) for v in mask):
            raise ValueError('mask must be non-empty binary tuple')
        return OperatorProgram('xor_mask', (mask,))

    @staticmethod
    def rotate(amount: int):
        return OperatorProgram('rotate', (int(amount),))

    @staticmethod
    def permute(permutation):
        p = tuple(int(v) for v in tuple(permutation))
        if not p or sorted(p) != list(range(len(p))):
            raise ValueError('permutation must be a bijection')
        return OperatorProgram('permute', (p,))

    @staticmethod
    def shear_xor(target: int, source: int):
        target, source = int(target), int(source)
        if target < 0 or source < 0 or target == source:
            raise ValueError('shear indices must be distinct non-negative indices')
        return OperatorProgram('shear_xor', (target, source))

    @staticmethod
    def compose(*programs):
        flat = []
        for p in programs:
            if not isinstance(p, OperatorProgram):
                raise TypeError('compose expects OperatorProgram values')
            if p.op == 'compose':
                flat.extend(p.children)
            elif p.op != 'identity':
                flat.append(p)
        if not flat:
            return OperatorProgram.identity()
        if len(flat) == 1:
            return flat[0]
        return OperatorProgram('compose', (), tuple(flat))


def apply_operator(program: OperatorProgram, state):
    state = _bits(state)
    n = len(state)
    if program.op == 'identity':
        return state
    if program.op == 'xor_mask':
        mask = program.args[0]
        if len(mask) != n:
            raise ValueError('xor mask width mismatch')
        return tuple(a ^ b for a, b in zip(state, mask))
    if program.op == 'rotate':
        k = program.args[0] % n
        return state[-k:] + state[:-k] if k else state
    if program.op == 'permute':
        p = program.args[0]
        if len(p) != n:
            raise ValueError('permutation width mismatch')
        return tuple(state[i] for i in p)
    if program.op == 'shear_xor':
        target, source = program.args
        if target >= n or source >= n:
            raise ValueError('shear index width mismatch')
        out = list(state)
        out[target] ^= state[source]
        return tuple(out)
    if program.op == 'compose':
        out = state
        for child in program.children:
            out = apply_operator(child, out)
        return out
    raise ValueError(f'unknown operator {program.op}')


def operator_cost(program: OperatorProgram) -> int:
    if program.op == 'identity':
        return 0
    if program.op == 'compose':
        return sum(operator_cost(c) for c in program.children)
    return 1


def operator_signature(program: OperatorProgram, width: int):
    width = int(width)
    if width <= 0:
        raise ValueError('width must be positive')
    return tuple(apply_operator(program, state) for state in itertools.product((0, 1), repeat=width))


def canonical_operator_id(program: OperatorProgram, width: int) -> str:
    sig = operator_signature(program, width)
    payload = ';'.join(''.join(map(str, row)) for row in sig)
    return 'op:' + hashlib.sha256(payload.encode()).hexdigest()[:20]
