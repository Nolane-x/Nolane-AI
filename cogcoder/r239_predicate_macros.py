from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r239_typed_probe_dsl import (
    ProbeType,
    TypedProbe,
    add3,
    and_probe,
    bool_atom,
    const3,
    eq_probe,
    equiv_probe,
    neq_probe,
    not_probe,
    or_probe,
    sub3,
    trit_atom,
    xor_probe,
)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:24]


@dataclass(frozen=True, order=True)
class ProbeMacro:
    macro_id: str
    template: TypedProbe
    parameter_types: tuple[ProbeType, ...]
    support: int
    compression_gain: float
    raw_mdl_cost: int
    call_mdl_cost: int = 2

    @property
    def arity(self) -> int:
        return len(self.parameter_types)


def _rebuild(op: str, left: TypedProbe | None, right: TypedProbe | None, const_value=None) -> TypedProbe:
    if op == 'const3':
        return const3(int(const_value))
    if op == 'add3':
        return add3(left, right)
    if op == 'sub3':
        return sub3(left, right)
    if op == 'eq':
        return eq_probe(left, right)
    if op == 'neq':
        return neq_probe(left, right)
    if op == 'xor':
        return xor_probe(left, right)
    if op == 'equiv':
        return equiv_probe(left, right)
    if op == 'and':
        return and_probe(left, right)
    if op == 'or':
        return or_probe(left, right)
    if op == 'not':
        return not_probe(left)
    raise ValueError(f'unsupported macro operator: {op}')


def abstract_macro_template(program: TypedProbe) -> tuple[TypedProbe, tuple[ProbeType, ...]]:
    if not isinstance(program, TypedProbe):
        raise TypeError('program must be a TypedProbe')
    mapping: dict[tuple[ProbeType, str], int] = {}
    parameter_types: list[ProbeType] = []
    commutative = {'add3', 'eq', 'neq', 'xor', 'equiv', 'and', 'or'}

    def shape(node: TypedProbe) -> str:
        if node.op == 'atom':
            return f'atom:{node.output_type.value}'
        if node.op == 'const3':
            return f'const3:{int(node.const_value)}'
        children = [c for c in (node.left, node.right) if c is not None]
        parts = [shape(c) for c in children]
        if node.op in commutative:
            parts.sort()
        return f'{node.op}:{node.output_type.value}(' + ','.join(parts) + ')'

    def ordered_children(node: TypedProbe) -> tuple[TypedProbe | None, TypedProbe | None]:
        left, right = node.left, node.right
        if node.op in commutative and left is not None and right is not None:
            if (shape(right), right.probe_id) < (shape(left), left.probe_id):
                left, right = right, left
        return left, right

    def visit(node: TypedProbe) -> TypedProbe:
        if node.op == 'atom':
            key = (node.output_type, str(node.atom_id))
            if key not in mapping:
                mapping[key] = len(parameter_types)
                parameter_types.append(node.output_type)
            idx = mapping[key]
            placeholder = f'$p{idx}'
            return trit_atom(placeholder) if node.output_type is ProbeType.TRIT else bool_atom(placeholder)
        if node.op == 'const3':
            return const3(int(node.const_value))
        left_node, right_node = ordered_children(node)
        left = visit(left_node) if left_node is not None else None
        right = visit(right_node) if right_node is not None else None
        return _rebuild(node.op, left, right, node.const_value)

    return visit(program), tuple(parameter_types)


def _subtrees(program: TypedProbe):
    yield program
    if program.left is not None:
        yield from _subtrees(program.left)
    if program.right is not None:
        yield from _subtrees(program.right)


def induce_probe_macros(
    episode_programs: Mapping[str, Sequence[TypedProbe]],
    *,
    min_support: int = 2,
    max_macros: int = 8,
) -> tuple[ProbeMacro, ...]:
    min_support = int(min_support)
    max_macros = int(max_macros)
    if min_support < 2:
        raise ValueError('min_support must be at least 2')
    if max_macros <= 0:
        raise ValueError('max_macros must be positive')

    records: dict[tuple[str, tuple[ProbeType, ...]], tuple[TypedProbe, set[str]]] = {}
    for episode_id in sorted(map(str, episode_programs)):
        seen_this_episode: set[tuple[str, tuple[ProbeType, ...]]] = set()
        for program in episode_programs[episode_id]:
            for subtree in _subtrees(program):
                if subtree.output_type is not ProbeType.BOOL or subtree.depth < 3 or subtree.node_count < 5:
                    continue
                template, types = abstract_macro_template(subtree)
                if not 2 <= len(types) <= 4:
                    continue
                key = (template.probe_id, types)
                if key in seen_this_episode:
                    continue
                seen_this_episode.add(key)
                if key not in records:
                    records[key] = (template, set())
                records[key][1].add(episode_id)

    macros: list[ProbeMacro] = []
    for (template_id, types), (template, episodes) in records.items():
        support = len(episodes)
        if support < min_support:
            continue
        raw = int(template.mdl_cost)
        call = 2
        definition = raw
        gain = float(support * (raw - call) - definition)
        if gain <= 0:
            continue
        payload = f'{template_id}|types={",".join(t.value for t in types)}'
        macros.append(ProbeMacro(
            macro_id='pm:' + _digest(payload),
            template=template,
            parameter_types=types,
            support=support,
            compression_gain=gain,
            raw_mdl_cost=raw,
            call_mdl_cost=call,
        ))
    return tuple(sorted(macros, key=lambda m: (-m.compression_gain, -m.support, m.macro_id))[:max_macros])


def instantiate_macro(macro: ProbeMacro, arguments: Sequence[TypedProbe]) -> TypedProbe:
    args = tuple(arguments)
    if len(args) != macro.arity:
        raise ValueError('macro argument arity mismatch')
    for arg, expected in zip(args, macro.parameter_types):
        if not isinstance(arg, TypedProbe) or arg.output_type is not expected:
            raise TypeError('macro argument type mismatch')

    def visit(node: TypedProbe) -> TypedProbe:
        if node.op == 'atom' and str(node.atom_id).startswith('$p'):
            idx = int(str(node.atom_id)[2:])
            return args[idx]
        if node.op == 'atom':
            return trit_atom(node.atom_id) if node.output_type is ProbeType.TRIT else bool_atom(node.atom_id)
        if node.op == 'const3':
            return const3(int(node.const_value))
        left = visit(node.left) if node.left is not None else None
        right = visit(node.right) if node.right is not None else None
        return _rebuild(node.op, left, right, node.const_value)

    return visit(macro.template)
