from __future__ import annotations

import ast
import copy
import hashlib
import itertools
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:20]


def _parse_function(source: str) -> ast.FunctionDef:
    module = ast.parse(str(source))
    funcs = [n for n in module.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(funcs) != 1 or not isinstance(funcs[0], ast.FunctionDef):
        raise ValueError('source must contain exactly one synchronous function')
    return funcs[0]


def _dump(node: ast.AST) -> str:
    return ast.dump(node, include_attributes=False)


def _node_pairs(before: ast.AST, after: ast.AST, typ: type[ast.AST]):
    a = [n for n in ast.walk(before) if isinstance(n, typ)]
    b = [n for n in ast.walk(after) if isinstance(n, typ)]
    if len(a) != len(b):
        return ()
    return tuple(zip(a, b))


@dataclass(frozen=True, order=True)
class PatchMacro:
    macro_id: str
    slot: str
    kind: str
    src: str | None
    dst: str | None
    support: int = 1

    def __post_init__(self) -> None:
        slot = str(self.slot).strip().lower()
        kind = str(self.kind).strip().lower()
        if slot not in {'binop', 'operand_wrapper', 'compare', 'return_wrapper'}:
            raise ValueError('unsupported patch slot')
        if not kind:
            raise ValueError('kind must be non-empty')
        if int(self.support) <= 0:
            raise ValueError('support must be positive')
        object.__setattr__(self, 'slot', slot)
        object.__setattr__(self, 'kind', kind)
        object.__setattr__(self, 'support', int(self.support))

    @property
    def signature(self) -> tuple[str, str, str | None, str | None]:
        return self.slot, self.kind, self.src, self.dst


@dataclass(frozen=True)
class PatchCandidate:
    candidate_id: str
    macro_ids: tuple[str, ...]
    source: str
    support_score: int
    edit_count: int


@dataclass(frozen=True)
class PatchTest:
    test_id: str
    args: tuple[int, ...]
    expected: object


@dataclass(frozen=True)
class PatchRound:
    round_index: int
    observed_test_ids: tuple[str, ...]
    surviving_candidates: int
    selected_candidate_id: str | None
    counterexample_test_id: str | None


@dataclass(frozen=True)
class PatchCegisReceipt:
    status: str
    candidate: PatchCandidate | None
    exact: bool
    initial_tests: int
    counterexamples_revealed: int
    observed_test_ids: tuple[str, ...]
    feedback_fraction: float
    rounds: tuple[PatchRound, ...]
    initial_candidate_count: int
    final_survivor_count: int
    candidate_test_evaluations: int
    exhaustive_tests_verified: int
    reason: str


def _macro_id(signature: tuple[str, str, str | None, str | None]) -> str:
    return 'pm:' + _digest('|'.join('' if v is None else str(v) for v in signature))


def _operator_name(node: ast.AST) -> str:
    return type(node).__name__


def _wrapped_with(after: ast.AST, before: ast.AST) -> str | None:
    if isinstance(after, ast.Call) and isinstance(after.func, ast.Name) and len(after.args) == 1:
        if _dump(after.args[0]) == _dump(before) and after.func.id in {'abs'}:
            return after.func.id
    if isinstance(after, ast.UnaryOp) and isinstance(after.op, ast.USub) and _dump(after.operand) == _dump(before):
        return 'neg'
    if (
        isinstance(after, ast.Call)
        and isinstance(after.func, ast.Name)
        and after.func.id == 'max'
        and len(after.args) == 2
        and isinstance(after.args[0], ast.Constant)
        and after.args[0].value == 0
        and _dump(after.args[1]) == _dump(before)
    ):
        return 'max0'
    return None


def infer_patch_macro(before_source: str, after_source: str) -> PatchMacro:
    """Infer one generic AST rewrite from a single-edit demonstration."""
    before = _parse_function(before_source)
    after = _parse_function(after_source)

    changes: list[tuple[str, str, str | None, str | None]] = []

    bin_pairs = _node_pairs(before, after, ast.BinOp)
    for a, b in bin_pairs:
        assert isinstance(a, ast.BinOp) and isinstance(b, ast.BinOp)
        if _operator_name(a.op) != _operator_name(b.op) and _dump(a.left) == _dump(b.left) and _dump(a.right) == _dump(b.right):
            changes.append(('binop', 'replace', _operator_name(a.op), _operator_name(b.op)))
        elif _operator_name(a.op) == _operator_name(b.op):
            lw = _wrapped_with(b.left, a.left)
            rw = _wrapped_with(b.right, a.right)
            if lw is not None and lw == rw:
                changes.append(('operand_wrapper', 'wrap', None, lw))

    cmp_pairs = _node_pairs(before, after, ast.Compare)
    for a, b in cmp_pairs:
        assert isinstance(a, ast.Compare) and isinstance(b, ast.Compare)
        if len(a.ops) == len(b.ops) == 1 and len(a.comparators) == len(b.comparators) == 1:
            if (
                _operator_name(a.ops[0]) != _operator_name(b.ops[0])
                and _dump(a.left) == _dump(b.left)
                and _dump(a.comparators[0]) == _dump(b.comparators[0])
            ):
                changes.append(('compare', 'replace', _operator_name(a.ops[0]), _operator_name(b.ops[0])))

    ret_pairs = _node_pairs(before, after, ast.Return)
    for a, b in ret_pairs:
        assert isinstance(a, ast.Return) and isinstance(b, ast.Return)
        if a.value is not None and b.value is not None:
            wrapper = _wrapped_with(b.value, a.value)
            if wrapper is not None:
                changes.append(('return_wrapper', 'wrap', None, wrapper))

    unique = sorted(set(changes))
    if len(unique) != 1:
        raise ValueError(f'demonstration must imply exactly one patch macro, got {unique!r}')
    sig = unique[0]
    return PatchMacro(_macro_id(sig), *sig, support=1)


def learn_patch_library(demonstrations: Sequence[tuple[str, str]]) -> tuple[PatchMacro, ...]:
    counts: dict[tuple[str, str, str | None, str | None], int] = {}
    for before, after in demonstrations:
        macro = infer_patch_macro(before, after)
        counts[macro.signature] = counts.get(macro.signature, 0) + 1
    out = []
    for sig, support in sorted(counts.items()):
        out.append(PatchMacro(_macro_id(sig), *sig, support=support))
    return tuple(out)


_BINOPS: dict[str, type[ast.operator]] = {
    'Add': ast.Add, 'Sub': ast.Sub, 'Mult': ast.Mult, 'FloorDiv': ast.FloorDiv, 'Mod': ast.Mod,
}
_CMPOPS: dict[str, type[ast.cmpop]] = {
    'Lt': ast.Lt, 'LtE': ast.LtE, 'Gt': ast.Gt, 'GtE': ast.GtE, 'Eq': ast.Eq,
}


def _wrap(node: ast.expr, wrapper: str) -> ast.expr:
    if wrapper == 'abs':
        return ast.Call(func=ast.Name(id='abs', ctx=ast.Load()), args=[node], keywords=[])
    if wrapper == 'neg':
        return ast.UnaryOp(op=ast.USub(), operand=node)
    if wrapper == 'max0':
        return ast.Call(func=ast.Name(id='max', ctx=ast.Load()), args=[ast.Constant(0), node], keywords=[])
    raise ValueError('unsupported wrapper')


class _ApplyMacro(ast.NodeTransformer):
    def __init__(self, macro: PatchMacro):
        self.macro = macro

    def visit_BinOp(self, node: ast.BinOp):
        node = self.generic_visit(node)
        assert isinstance(node, ast.BinOp)
        if self.macro.slot == 'binop' and self.macro.kind == 'replace':
            if type(node.op).__name__ == self.macro.src and self.macro.dst in _BINOPS:
                node.op = _BINOPS[self.macro.dst]()
        elif self.macro.slot == 'operand_wrapper' and self.macro.kind == 'wrap':
            if isinstance(node.left, ast.Name) and isinstance(node.right, ast.Name):
                node.left = _wrap(node.left, str(self.macro.dst))
                node.right = _wrap(node.right, str(self.macro.dst))
        return node

    def visit_Compare(self, node: ast.Compare):
        node = self.generic_visit(node)
        assert isinstance(node, ast.Compare)
        if self.macro.slot == 'compare' and self.macro.kind == 'replace' and len(node.ops) == 1:
            if type(node.ops[0]).__name__ == self.macro.src and self.macro.dst in _CMPOPS:
                node.ops[0] = _CMPOPS[self.macro.dst]()
        return node

    def visit_Return(self, node: ast.Return):
        node = self.generic_visit(node)
        assert isinstance(node, ast.Return)
        if self.macro.slot == 'return_wrapper' and self.macro.kind == 'wrap' and node.value is not None:
            node.value = _wrap(node.value, str(self.macro.dst))
        return node


def apply_patch_macros(source: str, macros: Sequence[PatchMacro]) -> str:
    tree = ast.parse(source)
    ordered = sorted(macros, key=lambda m: ({'binop': 0, 'operand_wrapper': 1, 'compare': 2, 'return_wrapper': 3}[m.slot], m.macro_id))
    for macro in ordered:
        tree = _ApplyMacro(macro).visit(tree)
        ast.fix_missing_locations(tree)
    return ast.unparse(tree) + '\n'


def enumerate_patch_candidates(source: str, macros: Sequence[PatchMacro]) -> tuple[PatchCandidate, ...]:
    by_slot: dict[str, list[PatchMacro]] = {slot: [] for slot in ('binop', 'operand_wrapper', 'compare', 'return_wrapper')}
    for macro in macros:
        by_slot[macro.slot].append(macro)
    choices = []
    for slot in ('binop', 'operand_wrapper', 'compare', 'return_wrapper'):
        choices.append((None, *sorted(by_slot[slot], key=lambda m: m.macro_id)))
    out: dict[str, PatchCandidate] = {}
    for selection in itertools.product(*choices):
        selected = tuple(m for m in selection if m is not None)
        patched = apply_patch_macros(source, selected)
        macro_ids = tuple(sorted(m.macro_id for m in selected))
        cid = 'pc:' + _digest('|'.join(macro_ids) + '|' + patched)
        candidate = PatchCandidate(
            cid, macro_ids, patched,
            sum(m.support for m in selected), len(selected),
        )
        prior = out.get(patched)
        if prior is None or (
            candidate.edit_count, -candidate.support_score, candidate.macro_ids
        ) < (
            prior.edit_count, -prior.support_score, prior.macro_ids
        ):
            out[patched] = candidate
    return tuple(sorted(out.values(), key=lambda c: (c.edit_count, -c.support_score, c.macro_ids, c.candidate_id)))


def compile_candidate(candidate: PatchCandidate) -> tuple[str, Callable[..., object]]:
    fn = _parse_function(candidate.source)
    namespace = {'__builtins__': {'abs': abs, 'max': max}}
    code = compile(candidate.source, f'<{candidate.candidate_id}>', 'exec')
    exec(code, namespace, namespace)
    func = namespace[fn.name]
    return fn.name, func


def _passes(candidate: PatchCandidate, tests: Sequence[PatchTest]) -> tuple[bool, int]:
    try:
        _name, fn = compile_candidate(candidate)
    except Exception:
        return False, 0
    evaluations = 0
    for test in tests:
        evaluations += 1
        try:
            value = fn(*test.args)
        except Exception:
            return False, evaluations
        if value != test.expected:
            return False, evaluations
    return True, evaluations


def solve_patch_with_sparse_tests(
    candidates: Sequence[PatchCandidate],
    tests: Sequence[PatchTest],
    *,
    initial_test_ids: Sequence[str],
    hidden_order: Sequence[str],
    max_counterexamples: int = 32,
) -> PatchCegisReceipt:
    by_id = {t.test_id: t for t in tests}
    if len(by_id) != len(tuple(tests)):
        raise ValueError('duplicate test ids')
    initial = tuple(map(str, initial_test_ids))
    order = tuple(map(str, hidden_order))
    if not initial or len(set(initial)) != len(initial) or any(t not in by_id for t in initial):
        raise ValueError('invalid initial tests')
    if set(order) != set(by_id) or len(order) != len(by_id):
        raise ValueError('hidden_order must be a permutation of all tests')
    if int(max_counterexamples) < 0:
        raise ValueError('max_counterexamples must be non-negative')

    observed = list(initial)
    observed_set = set(initial)
    survivors = list(candidates)
    rounds: list[PatchRound] = []
    total_evals = 0
    counterexamples = 0

    for round_index in range(int(max_counterexamples) + 1):
        visible_tests = [by_id[tid] for tid in observed]
        next_survivors = []
        for candidate in survivors:
            ok, evals = _passes(candidate, visible_tests)
            total_evals += evals
            if ok:
                next_survivors.append(candidate)
        survivors = sorted(next_survivors, key=lambda c: (c.edit_count, -c.support_score, c.macro_ids, c.candidate_id))
        if not survivors:
            rounds.append(PatchRound(round_index, tuple(observed), 0, None, None))
            return PatchCegisReceipt(
                'abstain', None, False, len(initial), counterexamples, tuple(observed),
                len(observed) / len(tests), tuple(rounds), len(candidates), 0, total_evals, 0,
                'version_space_empty',
            )
        selected = survivors[0]
        hidden_failure = None
        _name, fn = compile_candidate(selected)
        for tid in order:
            if tid in observed_set:
                continue
            test = by_id[tid]
            total_evals += 1
            try:
                value = fn(*test.args)
            except Exception:
                hidden_failure = tid
                break
            if value != test.expected:
                hidden_failure = tid
                break
        rounds.append(PatchRound(
            round_index, tuple(observed), len(survivors), selected.candidate_id, hidden_failure
        ))
        if hidden_failure is None:
            exact_count = 0
            for test in tests:
                total_evals += 1
                try:
                    if fn(*test.args) == test.expected:
                        exact_count += 1
                except Exception:
                    pass
            exact = exact_count == len(tests)
            return PatchCegisReceipt(
                'accept' if exact else 'abstain', selected, exact, len(initial), counterexamples,
                tuple(observed), len(observed) / len(tests), tuple(rounds), len(candidates),
                len(survivors), total_evals, exact_count,
                'sparse_executable_patch_converged' if exact else 'final_executable_verification_failed',
            )
        if counterexamples >= int(max_counterexamples):
            break
        observed.append(hidden_failure)
        observed_set.add(hidden_failure)
        counterexamples += 1

    return PatchCegisReceipt(
        'abstain', survivors[0] if survivors else None, False, len(initial), counterexamples,
        tuple(observed), len(observed) / len(tests), tuple(rounds), len(candidates),
        len(survivors), total_evals, 0, 'counterexample_budget_exhausted',
    )
