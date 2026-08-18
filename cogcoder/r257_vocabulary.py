from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Mapping

from .r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary, evaluate_expr


@dataclass(frozen=True, slots=True)
class TemplateParam(Expr):
    index: int

    def __post_init__(self) -> None:
        if int(self.index) < 0:
            raise ValueError('parameter index must be non-negative')
        object.__setattr__(self, 'index', int(self.index))

    @property
    def depth(self) -> int:
        return 0

    @property
    def cost(self) -> int:
        return 1

    def to_data(self) -> dict[str, object]:
        return {'param': self.index}


@dataclass(frozen=True, slots=True)
class AbstractionCall(Expr):
    abstraction_id: str
    args: tuple[Expr, ...]

    def __post_init__(self) -> None:
        aid = str(self.abstraction_id).strip()
        if not aid:
            raise ValueError('abstraction_id must be non-empty')
        args = tuple(self.args)
        if not all(isinstance(row, Expr) for row in args):
            raise TypeError('abstraction arguments must be Expr')
        object.__setattr__(self, 'abstraction_id', aid)
        object.__setattr__(self, 'args', args)

    @property
    def depth(self) -> int:
        return 1 + max((arg.depth for arg in self.args), default=0)

    @property
    def cost(self) -> int:
        return 1 + sum(arg.cost for arg in self.args)

    def to_data(self) -> dict[str, object]:
        return {'call': self.abstraction_id, 'args': [arg.to_data() for arg in self.args]}


@dataclass(frozen=True, slots=True)
class LearnedAbstraction:
    abstraction_id: str
    parameter_count: int
    template: Expr
    support_task_ids: tuple[str, ...]
    raw_occurrence_cost: int
    rewritten_cost: int

    def __post_init__(self) -> None:
        aid = str(self.abstraction_id).strip()
        if not aid:
            raise ValueError('abstraction_id must be non-empty')
        if int(self.parameter_count) < 0:
            raise ValueError('parameter_count must be non-negative')
        if not isinstance(self.template, Expr):
            raise TypeError('template must be Expr')
        tasks = tuple(sorted({str(x).strip() for x in self.support_task_ids if str(x).strip()}))
        object.__setattr__(self, 'abstraction_id', aid)
        object.__setattr__(self, 'parameter_count', int(self.parameter_count))
        object.__setattr__(self, 'support_task_ids', tasks)
        object.__setattr__(self, 'raw_occurrence_cost', int(self.raw_occurrence_cost))
        object.__setattr__(self, 'rewritten_cost', int(self.rewritten_cost))

    @property
    def compression_gain(self) -> int:
        return self.raw_occurrence_cost - self.rewritten_cost


def _content_digest(template: Expr, parameter_count: int) -> str:
    payload = {'template': template.to_data(), 'parameter_count': int(parameter_count)}
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def make_abstraction(
    template: Expr,
    *,
    parameter_count: int,
    support_task_ids: Iterable[str],
    raw_occurrence_cost: int,
    rewritten_cost: int,
) -> LearnedAbstraction:
    return LearnedAbstraction(
        abstraction_id=f'abs.{_content_digest(template, parameter_count)}',
        parameter_count=parameter_count,
        template=template,
        support_task_ids=tuple(support_task_ids),
        raw_occurrence_cost=raw_occurrence_cost,
        rewritten_cost=rewritten_cost,
    )


def _call_dependencies(expr: Expr) -> set[str]:
    if isinstance(expr, AbstractionCall):
        out = {expr.abstraction_id}
        for arg in expr.args:
            out.update(_call_dependencies(arg))
        return out
    if isinstance(expr, Unary):
        return _call_dependencies(expr.arg)
    if isinstance(expr, Binary):
        return _call_dependencies(expr.left) | _call_dependencies(expr.right)
    if isinstance(expr, IfElse):
        return _call_dependencies(expr.condition) | _call_dependencies(expr.when_true) | _call_dependencies(expr.when_false)
    return set()


class CognitiveVocabulary:
    def __init__(self, abstractions: Iterable[LearnedAbstraction] = ()) -> None:
        self._items: dict[str, LearnedAbstraction] = {}
        for abstraction in abstractions:
            self.register(abstraction)

    def register(self, abstraction: LearnedAbstraction) -> None:
        if not isinstance(abstraction, LearnedAbstraction):
            raise TypeError('abstraction must be LearnedAbstraction')
        if abstraction.abstraction_id in self._items:
            existing = self._items[abstraction.abstraction_id]
            if existing != abstraction:
                raise ValueError('abstraction digest collision')
            return
        dependencies = _call_dependencies(abstraction.template)
        if abstraction.abstraction_id in dependencies:
            raise ValueError('recursive abstraction cycle')
        unknown = dependencies.difference(self._items)
        if unknown:
            raise ValueError(f'unknown abstraction dependency: {sorted(unknown)}')
        self._items[abstraction.abstraction_id] = abstraction

    def get(self, abstraction_id: str) -> LearnedAbstraction:
        try:
            return self._items[str(abstraction_id)]
        except KeyError:
            raise KeyError(str(abstraction_id)) from None

    def abstractions(self) -> tuple[LearnedAbstraction, ...]:
        return tuple(self._items[k] for k in sorted(self._items))

    def remove(self, abstraction_id: str) -> LearnedAbstraction:
        aid = str(abstraction_id)
        try:
            return self._items.pop(aid)
        except KeyError:
            raise KeyError(aid) from None


def _substitute(expr: Expr, args: tuple[Expr, ...]) -> Expr:
    if isinstance(expr, TemplateParam):
        if expr.index >= len(args):
            raise ValueError('template parameter out of range')
        return args[expr.index]
    if isinstance(expr, Unary):
        return Unary(expr.op, _substitute(expr.arg, args))
    if isinstance(expr, Binary):
        return Binary(expr.op, _substitute(expr.left, args), _substitute(expr.right, args))
    if isinstance(expr, IfElse):
        return IfElse(
            _substitute(expr.condition, args),
            _substitute(expr.when_true, args),
            _substitute(expr.when_false, args),
        )
    if isinstance(expr, AbstractionCall):
        return AbstractionCall(expr.abstraction_id, tuple(_substitute(arg, args) for arg in expr.args))
    return expr


def _node_count(expr: Expr) -> int:
    if isinstance(expr, (Field, Const, TemplateParam)):
        return 1
    if isinstance(expr, Unary):
        return 1 + _node_count(expr.arg)
    if isinstance(expr, Binary):
        return 1 + _node_count(expr.left) + _node_count(expr.right)
    if isinstance(expr, IfElse):
        return 1 + _node_count(expr.condition) + _node_count(expr.when_true) + _node_count(expr.when_false)
    if isinstance(expr, AbstractionCall):
        return 1 + sum(_node_count(arg) for arg in expr.args)
    raise TypeError('unknown expression node')


def expand_expr(
    expr: Expr,
    vocabulary: CognitiveVocabulary,
    *,
    max_expansion_nodes: int = 10000,
    _stack: tuple[str, ...] = (),
) -> Expr:
    if int(max_expansion_nodes) < 1:
        raise ValueError('max_expansion_nodes must be positive')
    if isinstance(expr, AbstractionCall):
        abstraction = vocabulary.get(expr.abstraction_id)
        if expr.abstraction_id in _stack:
            raise ValueError('recursive abstraction expansion cycle')
        if len(expr.args) != abstraction.parameter_count:
            raise ValueError('abstraction argument count mismatch')
        expanded_args = tuple(expand_expr(arg, vocabulary, max_expansion_nodes=max_expansion_nodes, _stack=_stack) for arg in expr.args)
        substituted = _substitute(abstraction.template, expanded_args)
        expanded = expand_expr(substituted, vocabulary, max_expansion_nodes=max_expansion_nodes, _stack=_stack + (expr.abstraction_id,))
    elif isinstance(expr, Unary):
        expanded = Unary(expr.op, expand_expr(expr.arg, vocabulary, max_expansion_nodes=max_expansion_nodes, _stack=_stack))
    elif isinstance(expr, Binary):
        expanded = Binary(
            expr.op,
            expand_expr(expr.left, vocabulary, max_expansion_nodes=max_expansion_nodes, _stack=_stack),
            expand_expr(expr.right, vocabulary, max_expansion_nodes=max_expansion_nodes, _stack=_stack),
        )
    elif isinstance(expr, IfElse):
        expanded = IfElse(
            expand_expr(expr.condition, vocabulary, max_expansion_nodes=max_expansion_nodes, _stack=_stack),
            expand_expr(expr.when_true, vocabulary, max_expansion_nodes=max_expansion_nodes, _stack=_stack),
            expand_expr(expr.when_false, vocabulary, max_expansion_nodes=max_expansion_nodes, _stack=_stack),
        )
    elif isinstance(expr, TemplateParam):
        raise ValueError('unbound template parameter')
    else:
        expanded = expr
    if _node_count(expanded) > int(max_expansion_nodes):
        raise ValueError('expansion node budget exceeded')
    return expanded


def evaluate_with_vocabulary(expr: Expr, context: Mapping[str, object], vocabulary: CognitiveVocabulary) -> object:
    return evaluate_expr(expand_expr(expr, vocabulary), context)


__all__ = [
    'TemplateParam', 'AbstractionCall', 'LearnedAbstraction', 'CognitiveVocabulary',
    'make_abstraction', 'expand_expr', 'evaluate_with_vocabulary',
]
