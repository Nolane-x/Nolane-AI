from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Sequence

from .r255_lifecycle import ProcedureLifecycleLedger
from .r256_operator_dsl import Binary, Const, Expr, Field, IfElse, Unary, expr_digest
from .r257_vocabulary import CognitiveVocabulary, LearnedAbstraction, TemplateParam, make_abstraction


@dataclass(frozen=True, slots=True)
class VerifiedExpression:
    task_id: str
    expression: Expr

    def __post_init__(self) -> None:
        task = str(self.task_id).strip()
        if not task:
            raise ValueError('task_id must be non-empty')
        if not isinstance(self.expression, Expr):
            raise TypeError('expression must be Expr')
        object.__setattr__(self, 'task_id', task)


@dataclass(frozen=True, slots=True)
class AbstractionCandidate:
    abstraction: LearnedAbstraction
    support_task_ids: tuple[str, ...]
    compression_gain: int


@dataclass(frozen=True, slots=True)
class AbstractionLearningReceipt:
    candidates: tuple[AbstractionCandidate, ...]
    groups_considered: int


def _children(expr: Expr) -> tuple[Expr, ...]:
    if isinstance(expr, Unary):
        return (expr.arg,)
    if isinstance(expr, Binary):
        return (expr.left, expr.right)
    if isinstance(expr, IfElse):
        return (expr.condition, expr.when_true, expr.when_false)
    return ()


def _subexpressions(expr: Expr) -> tuple[Expr, ...]:
    out = [expr]
    for child in _children(expr):
        out.extend(_subexpressions(child))
    return tuple(out)


def _leaf_key(expr: Expr) -> str:
    return json.dumps(expr.to_data(), sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _template_and_args(expr: Expr) -> tuple[Expr, tuple[Expr, ...]]:
    slots: dict[str, int] = {}
    args: list[Expr] = []

    def walk(node: Expr) -> Expr:
        if isinstance(node, (Field, Const)):
            key = _leaf_key(node)
            if key not in slots:
                slots[key] = len(args)
                args.append(node)
            return TemplateParam(slots[key])
        if isinstance(node, Unary):
            return Unary(node.op, walk(node.arg))
        if isinstance(node, Binary):
            return Binary(node.op, walk(node.left), walk(node.right))
        if isinstance(node, IfElse):
            return IfElse(walk(node.condition), walk(node.when_true), walk(node.when_false))
        raise TypeError(f'unsupported corpus node: {type(node).__name__}')

    return walk(expr), tuple(args)


def _signature(template: Expr) -> str:
    return json.dumps(template.to_data(), sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def learn_abstractions(
    corpus: Iterable[VerifiedExpression],
    *,
    min_support_tasks: int = 3,
    min_subexpr_cost: int = 3,
) -> AbstractionLearningReceipt:
    if int(min_support_tasks) < 2:
        raise ValueError('min_support_tasks must be at least 2')
    if int(min_subexpr_cost) < 2:
        raise ValueError('min_subexpr_cost must be at least 2')
    groups: dict[str, list[tuple[str, Expr, Expr, tuple[Expr, ...]]]] = defaultdict(list)
    for row in corpus:
        if not isinstance(row, VerifiedExpression):
            raise TypeError('corpus rows must be VerifiedExpression')
        for subexpr in _subexpressions(row.expression):
            if subexpr.cost < int(min_subexpr_cost):
                continue
            template, args = _template_and_args(subexpr)
            groups[_signature(template)].append((row.task_id, subexpr, template, args))

    candidates: list[AbstractionCandidate] = []
    for rows in groups.values():
        by_task: dict[str, tuple[str, Expr, Expr, tuple[Expr, ...]]] = {}
        for row in sorted(rows, key=lambda item: (item[0], expr_digest(item[1]))):
            by_task.setdefault(row[0], row)
        if len(by_task) < int(min_support_tasks):
            continue
        selected = tuple(by_task[key] for key in sorted(by_task))
        template = selected[0][2]
        parameter_count = len(selected[0][3])
        if any(len(item[3]) != parameter_count for item in selected):
            continue
        raw_cost = sum(item[1].cost for item in selected)
        definition_cost = template.cost
        call_cost = sum(1 + sum(arg.cost for arg in item[3]) for item in selected)
        rewritten_cost = definition_cost + call_cost
        if rewritten_cost >= raw_cost:
            continue
        tasks = tuple(sorted(by_task))
        abstraction = make_abstraction(
            template,
            parameter_count=parameter_count,
            support_task_ids=tasks,
            raw_occurrence_cost=raw_cost,
            rewritten_cost=rewritten_cost,
        )
        candidates.append(AbstractionCandidate(abstraction, tasks, abstraction.compression_gain))

    candidates.sort(key=lambda c: (
        -c.compression_gain,
        -len(c.support_task_ids),
        c.abstraction.template.cost,
        c.abstraction.abstraction_id,
    ))
    return AbstractionLearningReceipt(tuple(candidates), len(groups))


def match_abstraction(abstraction: LearnedAbstraction, expression: Expr) -> tuple[Expr, ...] | None:
    bindings: dict[int, Expr] = {}

    def match(template: Expr, actual: Expr) -> bool:
        if isinstance(template, TemplateParam):
            existing = bindings.get(template.index)
            if existing is None:
                bindings[template.index] = actual
                return True
            return existing.to_data() == actual.to_data()
        if type(template) is not type(actual):
            return False
        if isinstance(template, Field):
            return template.name == actual.name
        if isinstance(template, Const):
            return template.value == actual.value
        if isinstance(template, Unary):
            return template.op == actual.op and match(template.arg, actual.arg)
        if isinstance(template, Binary):
            return template.op == actual.op and match(template.left, actual.left) and match(template.right, actual.right)
        if isinstance(template, IfElse):
            return match(template.condition, actual.condition) and match(template.when_true, actual.when_true) and match(template.when_false, actual.when_false)
        return False

    if not match(abstraction.template, expression):
        return None
    if set(bindings) != set(range(abstraction.parameter_count)):
        return None
    return tuple(bindings[i] for i in range(abstraction.parameter_count))


def promote_abstraction(
    candidate: AbstractionCandidate,
    challenges: Sequence[VerifiedExpression],
    *,
    vocabulary: CognitiveVocabulary,
    lifecycle: ProcedureLifecycleLedger,
) -> bool:
    aid = candidate.abstraction.abstraction_id
    if lifecycle.state(aid) == 'unseen':
        lifecycle.transition(aid, 'candidate', reason='positive_multi_task_compression')
    if lifecycle.state(aid) != 'candidate':
        return False
    lifecycle.transition(aid, 'probation', reason='heldout_structural_challenge_required')
    for challenge in challenges:
        if match_abstraction(candidate.abstraction, challenge.expression) is None:
            lifecycle.transition(aid, 'quarantined', reason=f'challenge_failed:{challenge.task_id}')
            return False
    try:
        vocabulary.register(candidate.abstraction)
    except (TypeError, ValueError):
        lifecycle.transition(aid, 'quarantined', reason='vocabulary_registration_failed')
        return False
    lifecycle.transition(aid, 'promoted', reason='heldout_challenges_passed')
    return True


__all__ = [
    'VerifiedExpression', 'AbstractionCandidate', 'AbstractionLearningReceipt',
    'learn_abstractions', 'match_abstraction', 'promote_abstraction',
]
