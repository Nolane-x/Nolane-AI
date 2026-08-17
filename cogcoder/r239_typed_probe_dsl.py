from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class ProbeType(str, Enum):
    TRIT = 'trit'
    BOOL = 'bool'


_COMMUTATIVE = frozenset({'add3', 'eq', 'neq', 'xor', 'equiv', 'and', 'or'})
_TRIT_BINARY = frozenset({'add3', 'sub3'})
_BOOL_BINARY = frozenset({'xor', 'equiv', 'and', 'or'})


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:24]


@dataclass(frozen=True, order=True)
class TypedProbe:
    probe_id: str
    op: str
    output_type: ProbeType
    atom_id: str | None = None
    const_value: int | bool | None = None
    left: 'TypedProbe | None' = None
    right: 'TypedProbe | None' = None

    @property
    def children(self) -> tuple['TypedProbe', ...]:
        return tuple(v for v in (self.left, self.right) if v is not None)

    @property
    def node_count(self) -> int:
        return 1 + sum(c.node_count for c in self.children)

    @property
    def leaf_count(self) -> int:
        if not self.children:
            return 1
        return sum(c.leaf_count for c in self.children)

    @property
    def depth(self) -> int:
        if not self.children:
            return 1
        return 1 + max(c.depth for c in self.children)

    @property
    def mdl_cost(self) -> int:
        return self.node_count

    @property
    def execution_cost(self) -> float:
        return 1.0 + 0.20 * (self.node_count - 1)


def _atom(atom_id: str, output_type: ProbeType) -> TypedProbe:
    atom_id = str(atom_id).strip().lower()
    if not atom_id:
        raise ValueError('atom_id must be non-empty')
    payload = f'{output_type.value}:atom:{atom_id}'
    return TypedProbe('tp:' + _digest(payload), 'atom', output_type, atom_id=atom_id)


def trit_atom(atom_id: str) -> TypedProbe:
    return _atom(atom_id, ProbeType.TRIT)


def bool_atom(atom_id: str) -> TypedProbe:
    return _atom(atom_id, ProbeType.BOOL)


def const3(value: int) -> TypedProbe:
    value = int(value)
    if value not in (0, 1, 2):
        raise ValueError('trit constant must be 0, 1 or 2')
    return TypedProbe('tp:' + _digest(f'trit:const:{value}'), 'const3', ProbeType.TRIT, const_value=value)


def _binary(op: str, left: TypedProbe, right: TypedProbe, child_type: ProbeType, output_type: ProbeType) -> TypedProbe:
    if not isinstance(left, TypedProbe) or not isinstance(right, TypedProbe):
        raise TypeError('probe children must be TypedProbe instances')
    if left.output_type is not child_type or right.output_type is not child_type:
        raise TypeError(f'{op} requires {child_type.value} children')
    a, b = left, right
    if op in _COMMUTATIVE and b.probe_id < a.probe_id:
        a, b = b, a
    payload = f'{op}({a.probe_id},{b.probe_id})'
    return TypedProbe('tp:' + _digest(payload), op, output_type, left=a, right=b)


def add3(left: TypedProbe, right: TypedProbe) -> TypedProbe:
    return _binary('add3', left, right, ProbeType.TRIT, ProbeType.TRIT)


def sub3(left: TypedProbe, right: TypedProbe) -> TypedProbe:
    return _binary('sub3', left, right, ProbeType.TRIT, ProbeType.TRIT)


def eq_probe(left: TypedProbe, right: TypedProbe) -> TypedProbe:
    return _binary('eq', left, right, ProbeType.TRIT, ProbeType.BOOL)


def neq_probe(left: TypedProbe, right: TypedProbe) -> TypedProbe:
    return _binary('neq', left, right, ProbeType.TRIT, ProbeType.BOOL)


def xor_probe(left: TypedProbe, right: TypedProbe) -> TypedProbe:
    return _binary('xor', left, right, ProbeType.BOOL, ProbeType.BOOL)


def equiv_probe(left: TypedProbe, right: TypedProbe) -> TypedProbe:
    return _binary('equiv', left, right, ProbeType.BOOL, ProbeType.BOOL)


def and_probe(left: TypedProbe, right: TypedProbe) -> TypedProbe:
    return _binary('and', left, right, ProbeType.BOOL, ProbeType.BOOL)


def or_probe(left: TypedProbe, right: TypedProbe) -> TypedProbe:
    return _binary('or', left, right, ProbeType.BOOL, ProbeType.BOOL)


def not_probe(child: TypedProbe) -> TypedProbe:
    if not isinstance(child, TypedProbe) or child.output_type is not ProbeType.BOOL:
        raise TypeError('not requires a bool child')
    return TypedProbe('tp:' + _digest(f'not({child.probe_id})'), 'not', ProbeType.BOOL, left=child)


def evaluate_typed_probe(program: TypedProbe, atom_values: Mapping[str, int | bool]) -> int | bool:
    if program.op == 'atom':
        if program.atom_id not in atom_values:
            raise KeyError(program.atom_id)
        value = atom_values[program.atom_id]
        if program.output_type is ProbeType.TRIT:
            value = int(value)
            if value not in (0, 1, 2):
                raise ValueError('trit atom value must be 0, 1 or 2')
            return value
        return bool(value)
    if program.op == 'const3':
        return int(program.const_value)
    if program.left is None:
        raise ValueError('malformed probe')
    a = evaluate_typed_probe(program.left, atom_values)
    if program.op == 'not':
        return not bool(a)
    if program.right is None:
        raise ValueError('malformed binary probe')
    b = evaluate_typed_probe(program.right, atom_values)
    if program.op == 'add3':
        return (int(a) + int(b)) % 3
    if program.op == 'sub3':
        return (int(a) - int(b)) % 3
    if program.op == 'eq':
        return int(a) == int(b)
    if program.op == 'neq':
        return int(a) != int(b)
    if program.op == 'xor':
        return bool(a) ^ bool(b)
    if program.op == 'equiv':
        return bool(a) == bool(b)
    if program.op == 'and':
        return bool(a) and bool(b)
    if program.op == 'or':
        return bool(a) or bool(b)
    raise ValueError('unknown typed probe operator')


def typed_prediction_row(
    program: TypedProbe,
    atom_values_by_hypothesis: Mapping[str, Mapping[str, int | bool]],
) -> dict[str, bool]:
    if program.output_type is not ProbeType.BOOL:
        raise TypeError('verifier prediction row requires a bool-root probe')
    return {
        str(hid): bool(evaluate_typed_probe(program, values))
        for hid, values in atom_values_by_hypothesis.items()
    }
