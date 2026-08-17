from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping

OPS = frozenset({'xor', 'equiv', 'and', 'or'})


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


@dataclass(frozen=True, order=True)
class ProbeProgram:
    probe_id: str
    op: str
    atom_id: str | None = None
    left: 'ProbeProgram | None' = None
    right: 'ProbeProgram | None' = None
    mdl_cost: int = 1

    @property
    def is_composite(self) -> bool:
        return self.op != 'atom'


def atom_probe(query_id: str) -> ProbeProgram:
    query_id = str(query_id)
    if not query_id:
        raise ValueError('query_id must be non-empty')
    return ProbeProgram('p:atom:' + _digest(query_id), 'atom', atom_id=query_id, mdl_cost=1)


def compose_probe(op: str, left: ProbeProgram, right: ProbeProgram) -> ProbeProgram:
    op = str(op)
    if op not in OPS:
        raise ValueError('unknown compositional probe operator')
    if left.op != 'atom' or right.op != 'atom':
        raise ValueError('Phase A composition requires exactly two atomic leaves')
    if left.atom_id == right.atom_id:
        raise ValueError('composite leaves must be distinct')
    a, b = sorted((left, right), key=lambda p: p.probe_id)
    payload = f'{op}({a.probe_id},{b.probe_id})'
    return ProbeProgram('p:' + _digest(payload), op, left=a, right=b, mdl_cost=3)


def _apply(op: str, a: bool, b: bool) -> bool:
    if op == 'xor':
        return bool(a) ^ bool(b)
    if op == 'equiv':
        return bool(a) == bool(b)
    if op == 'and':
        return bool(a) and bool(b)
    if op == 'or':
        return bool(a) or bool(b)
    raise ValueError('unknown probe operator')


def evaluate_probe(program: ProbeProgram, atom_labels: Mapping[str, bool]) -> bool:
    if program.op == 'atom':
        if program.atom_id not in atom_labels:
            raise KeyError(program.atom_id)
        return bool(atom_labels[program.atom_id])
    if program.left is None or program.right is None:
        raise ValueError('malformed composite probe')
    return _apply(program.op, evaluate_probe(program.left, atom_labels), evaluate_probe(program.right, atom_labels))


def probe_prediction_row(
    program: ProbeProgram,
    atom_predictions: Mapping[str, Mapping[str, bool]],
) -> dict[str, bool]:
    if program.op == 'atom':
        if program.atom_id not in atom_predictions:
            raise KeyError(program.atom_id)
        return {str(k): bool(v) for k, v in atom_predictions[program.atom_id].items()}
    if program.left is None or program.right is None:
        raise ValueError('malformed composite probe')
    left = probe_prediction_row(program.left, atom_predictions)
    right = probe_prediction_row(program.right, atom_predictions)
    if set(left) != set(right):
        raise ValueError('prediction coverage mismatch')
    return {hid: _apply(program.op, left[hid], right[hid]) for hid in left}
