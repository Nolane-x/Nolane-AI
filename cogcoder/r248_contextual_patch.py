from __future__ import annotations

import ast
import hashlib
import itertools
from dataclasses import dataclass
from typing import Sequence

from .r247_executable_patch_cegis import (
    PatchCandidate,
    PatchMacro,
    _BINOPS,
    _CMPOPS,
    _digest,
    _operator_name,
    _parse_function,
    _wrap,
    infer_patch_macro,
)


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _guarded_return_names(fn: ast.FunctionDef) -> frozenset[str]:
    """Names whose defining assignment feeds an If test and that If returns that value.

    This is identifier-invariant: concrete names only join def-use edges inside the
    heldout function; learned macros store the abstract role, never a training name.
    """
    assigned: set[str] = set()
    for stmt in fn.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            assigned.add(stmt.targets[0].id)
    guarded: set[str] = set()
    for stmt in fn.body:
        if not isinstance(stmt, ast.If) or not isinstance(stmt.test, ast.Compare):
            continue
        test = stmt.test
        if not isinstance(test.left, ast.Name) or test.left.id not in assigned:
            continue
        name = test.left.id
        if any(isinstance(n, ast.Return) and name in _names_in(n) for n in ast.walk(ast.Module(body=stmt.body, type_ignores=[]))):
            guarded.add(name)
    return frozenset(guarded)


def _changed_sites(before: ast.FunctionDef, after: ast.FunctionDef, slot: str) -> tuple[ast.AST, ...]:
    typ = {'binop': ast.BinOp, 'operand_wrapper': ast.BinOp, 'compare': ast.Compare}[slot]
    a = [n for n in ast.walk(before) if isinstance(n, typ)]
    b = [n for n in ast.walk(after) if isinstance(n, typ)]
    if len(a) != len(b):
        return ()
    return tuple(x for x, y in zip(a, b) if ast.dump(x, include_attributes=False) != ast.dump(y, include_attributes=False))


@dataclass(frozen=True, order=True)
class ContextualPatchMacro:
    macro_id: str
    base: PatchMacro
    context_role: str
    support: int = 1

    def __post_init__(self):
        if self.context_role != 'guarded_return_value':
            raise ValueError('unsupported context role')
        if int(self.support) <= 0:
            raise ValueError('support must be positive')
        object.__setattr__(self, 'support', int(self.support))

    @property
    def slot(self) -> str:
        return self.base.slot

    @property
    def signature(self):
        return (*self.base.signature, self.context_role)


def infer_contextual_patch_macro(before_source: str, after_source: str) -> ContextualPatchMacro:
    base = infer_patch_macro(before_source, after_source)
    if base.slot not in {'binop', 'operand_wrapper', 'compare'}:
        raise ValueError('R2.48 supports contextual binop/operand/compare macros')
    before = _parse_function(before_source)
    guarded = _guarded_return_names(before)
    changed = _changed_sites(before, _parse_function(after_source), base.slot)
    if not changed:
        raise ValueError('no changed contextual site')
    valid = False
    if base.slot in {'binop', 'operand_wrapper'}:
        for stmt in before.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                if stmt.targets[0].id in guarded and any(stmt.value is node for node in changed):
                    valid = True
                    break
    else:
        for stmt in before.body:
            if isinstance(stmt, ast.If) and stmt.test in changed and isinstance(stmt.test, ast.Compare):
                if isinstance(stmt.test.left, ast.Name) and stmt.test.left.id in guarded:
                    valid = True
                    break
    if not valid:
        raise ValueError('changed site does not satisfy guarded-return context')
    sig = (*base.signature, 'guarded_return_value')
    mid = 'cpm:' + hashlib.sha256('|'.join('' if v is None else str(v) for v in sig).encode()).hexdigest()[:20]
    return ContextualPatchMacro(mid, base, 'guarded_return_value', 1)


def learn_contextual_patch_library(demos: Sequence[tuple[str, str]]) -> tuple[ContextualPatchMacro, ...]:
    by_sig: dict[tuple, tuple[ContextualPatchMacro, int]] = {}
    for before, after in demos:
        m = infer_contextual_patch_macro(before, after)
        prior = by_sig.get(m.signature)
        by_sig[m.signature] = (m, 1 if prior is None else prior[1] + 1)
    return tuple(
        ContextualPatchMacro(m.macro_id, m.base, m.context_role, support)
        for _sig, (m, support) in sorted(by_sig.items())
    )


class _ContextApply(ast.NodeTransformer):
    def __init__(self, macro: ContextualPatchMacro, guarded: frozenset[str]):
        self.macro = macro
        self.guarded = guarded
        self._assign_target: str | None = None
        self._if_test = False

    def visit_Assign(self, node: ast.Assign):
        target = node.targets[0].id if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) else None
        old = self._assign_target
        self._assign_target = target
        node.value = self.visit(node.value)
        self._assign_target = old
        return node

    def visit_If(self, node: ast.If):
        old = self._if_test
        self._if_test = True
        node.test = self.visit(node.test)
        self._if_test = old
        node.body = [self.visit(s) for s in node.body]
        node.orelse = [self.visit(s) for s in node.orelse]
        return node

    def visit_BinOp(self, node: ast.BinOp):
        node = self.generic_visit(node)
        base = self.macro.base
        if self._assign_target not in self.guarded:
            return node
        if base.slot == 'binop' and base.kind == 'replace':
            if type(node.op).__name__ == base.src and base.dst in _BINOPS:
                node.op = _BINOPS[base.dst]()
        elif base.slot == 'operand_wrapper' and base.kind == 'wrap':
            if isinstance(node.left, ast.Name) and isinstance(node.right, ast.Name):
                node.left = _wrap(node.left, str(base.dst))
                node.right = _wrap(node.right, str(base.dst))
        return node

    def visit_Compare(self, node: ast.Compare):
        node = self.generic_visit(node)
        base = self.macro.base
        if not self._if_test or not isinstance(node.left, ast.Name) or node.left.id not in self.guarded:
            return node
        if base.slot == 'compare' and base.kind == 'replace' and len(node.ops) == 1:
            if type(node.ops[0]).__name__ == base.src and base.dst in _CMPOPS:
                node.ops[0] = _CMPOPS[base.dst]()
        return node


def apply_contextual_patch_macros(source: str, macros: Sequence[ContextualPatchMacro]) -> str:
    tree = ast.parse(source)
    fn = _parse_function(source)
    guarded = _guarded_return_names(fn)
    ordered = sorted(macros, key=lambda m: ({'binop': 0, 'operand_wrapper': 1, 'compare': 2}[m.slot], m.macro_id))
    for macro in ordered:
        tree = _ContextApply(macro, guarded).visit(tree)
        ast.fix_missing_locations(tree)
    return ast.unparse(tree) + '\n'


def enumerate_contextual_candidates(source: str, macros: Sequence[ContextualPatchMacro]) -> tuple[PatchCandidate, ...]:
    by_slot: dict[str, list[ContextualPatchMacro]] = {s: [] for s in ('binop', 'operand_wrapper', 'compare')}
    for m in macros:
        by_slot[m.slot].append(m)
    out: dict[str, PatchCandidate] = {}
    choices = [(None, *sorted(by_slot[s], key=lambda m: m.macro_id)) for s in ('binop', 'operand_wrapper', 'compare')]
    for selection in itertools.product(*choices):
        selected = tuple(m for m in selection if m is not None)
        patched = apply_contextual_patch_macros(source, selected)
        ids = tuple(sorted(m.macro_id for m in selected))
        cid = 'cpc:' + _digest('|'.join(ids) + '|' + patched)
        c = PatchCandidate(cid, ids, patched, sum(m.support for m in selected), len(selected))
        prior = out.get(patched)
        if prior is None or (c.edit_count, -c.support_score, c.macro_ids) < (prior.edit_count, -prior.support_score, prior.macro_ids):
            out[patched] = c
    return tuple(sorted(out.values(), key=lambda c: (c.edit_count, -c.support_score, c.macro_ids, c.candidate_id)))
