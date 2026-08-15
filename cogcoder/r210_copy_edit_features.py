from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

import torch
from torch import Tensor

from .r29_patch_model import PatchCandidate, TextEdit

CANONICAL_OPERATORS: dict[str, str] = {
    '+': 'ADD', '-': 'SUB', '*': 'MUL', '/': 'DIV',
    '<': 'LT', '<=': 'LE', '>': 'GT', '>=': 'GE',
    '==': 'EQ', '===': 'EQ', '!=': 'NE', '!==': 'NE',
    'and': 'AND', '&&': 'AND', 'or': 'OR', '||': 'OR',
}

OPERATOR_FAMILIES: dict[str, tuple[str, ...]] = {
    'python:arith': ('+', '-', '*', '/'),
    'javascript:arith': ('+', '-', '*', '/'),
    'python:compare': ('<', '<=', '>', '>='),
    'javascript:compare': ('<', '<=', '>', '>='),
    'python:equality': ('==', '!=', '<', '>'),
    'javascript:equality': ('===', '!==', '<', '>'),
    'python:logic': ('and', 'or', '==', '!='),
    'javascript:logic': ('&&', '||', '===', '!=='),
}

_TOKEN_RE = re.compile(
    r"===|!==|<=|>=|==|!=|&&|\|\||[+\-*/<>]|[A-Za-z_$][A-Za-z0-9_$]*|-?\d+(?:\.\d+)?|[(),{}:;]"
)


@dataclass(frozen=True, slots=True)
class FailureProbe:
    inputs: tuple[float, ...]
    observed: float
    expected: float
    is_boolean: bool = False


def _signature(source: str, language: str) -> tuple[str | None, tuple[str, ...]]:
    if language == 'python':
        match = re.search(r"\bdef\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", source)
    elif language == 'javascript':
        match = re.search(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)", source)
    else:
        raise ValueError(f'unsupported language: {language}')
    if not match:
        raise ValueError('unable to locate function signature')
    params = tuple(part.strip() for part in match.group(2).split(',') if part.strip())
    return match.group(1), params


def _canonical_token(token: str, *, function_name: str | None, params: tuple[str, ...]) -> str | None:
    if token in {'def', 'function'}:
        return None
    if token == function_name:
        return 'FUNC'
    if token == 'return':
        return 'RETURN'
    if token in CANONICAL_OPERATORS:
        return CANONICAL_OPERATORS[token]
    if token in {'true', 'True'}:
        return 'TRUE'
    if token in {'false', 'False'}:
        return 'FALSE'
    if token in {'(', ')', ',', '{', '}', ':', ';'}:
        return None
    for index, param in enumerate(params):
        if token == param:
            return f'ARG{index}'
    if re.fullmatch(r'-?\d+(?:\.\d+)?', token):
        value = float(token)
        if value == 0:
            return 'NUM_ZERO'
        if value == 1:
            return 'NUM_ONE'
        if value == -1:
            return 'NUM_NEG_ONE'
        return 'NUM'
    if re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]*', token):
        return 'IDENT'
    return None


def canonicalize_source(source: str, *, language: str) -> tuple[str, ...]:
    function_name, params = _signature(source, language)
    tokens: list[str] = ['FUNC']
    tokens.extend(f'ARG{i}' for i in range(len(params)))
    # Only semantic body tokens are retained; surface braces/indentation disappear.
    body_start = source.find('\n')
    body = source[body_start + 1 :] if body_start >= 0 else source
    for token in _TOKEN_RE.findall(body):
        canonical = _canonical_token(token, function_name=function_name, params=params)
        if canonical is not None:
            tokens.append(canonical)
    return tuple(tokens)


def canonicalize_fragment(fragment: str, *, params: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for token in _TOKEN_RE.findall(fragment):
        canonical = _canonical_token(token, function_name=None, params=params)
        if canonical is not None:
            result.append(canonical)
    return tuple(result)


def _scaled(value: float) -> float:
    if not math.isfinite(float(value)):
        return 0.0
    return math.tanh(float(value) / 8.0)


def encode_evidence(probes: Iterable[FailureProbe], *, max_probes: int = 2) -> Tensor:
    rows: list[float] = []
    for probe in list(probes)[:max_probes]:
        inputs = tuple(probe.inputs[:2]) + (0.0, 0.0)
        a, b = inputs[:2]
        observed = float(probe.observed)
        expected = float(probe.expected)
        delta = expected - observed
        rows.extend(
            [
                _scaled(a),
                _scaled(b),
                _scaled(observed),
                _scaled(expected),
                _scaled(delta),
                float(expected > observed) - float(expected < observed),
                float(expected == observed),
                float(probe.is_boolean),
            ]
        )
    target = max_probes * 8
    rows.extend([0.0] * (target - len(rows)))
    return torch.tensor(rows[:target], dtype=torch.float32)


def _return_line(source: str) -> tuple[int, str]:
    lines = source.splitlines(keepends=True)
    for index, line in enumerate(lines, start=1):
        if re.search(r'\breturn\b', line):
            return index, line
    raise ValueError('unable to locate return line')


def _operator_family(operator: str, language: str) -> tuple[str, ...]:
    canonical = CANONICAL_OPERATORS.get(operator)
    if canonical in {'ADD', 'SUB', 'MUL', 'DIV'}:
        family = 'arith'
    elif canonical in {'LT', 'LE', 'GT', 'GE'}:
        family = 'compare'
    elif canonical in {'EQ', 'NE'}:
        family = 'equality'
    elif canonical in {'AND', 'OR'}:
        family = 'logic'
    else:
        raise ValueError(f'unsupported operator: {operator}')
    return OPERATOR_FAMILIES[f'{language}:{family}']


def enumerate_copy_edit_candidates(
    source: str,
    *,
    language: str,
    target_path: str,
    candidate_prefix: str = '',
) -> tuple[PatchCandidate, ...]:
    line_no, line = _return_line(source)
    # Longest operators first so <= is not mistaken for <.
    surface_ops = sorted(CANONICAL_OPERATORS, key=len, reverse=True)
    found: str | None = None
    match_span: tuple[int, int] | None = None
    for operator in surface_ops:
        pattern = rf'(?<![\w$]){re.escape(operator)}(?![\w$])' if operator.isalpha() else re.escape(operator)
        match = re.search(pattern, line)
        if match:
            found = operator
            match_span = match.span()
            break
    if found is None or match_span is None:
        raise ValueError('no supported operator found in return line')

    candidates: list[PatchCandidate] = []
    for index, replacement_op in enumerate(_operator_family(found, language)):
        replacement_line = line[: match_span[0]] + replacement_op + line[match_span[1] :]
        candidates.append(
            PatchCandidate(
                candidate_id=f'{candidate_prefix}op-{index}',
                edits=(TextEdit(target_path, line_no, line_no + 1, replacement_line),),
                provenance='r210-copy-edit-operator',
                targeted_nodes=frozenset({'target'}),
            )
        )
    return tuple(candidates)
