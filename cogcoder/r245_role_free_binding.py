from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r239_predicate_macros import ProbeMacro, instantiate_macro
from .r239_typed_probe_dsl import ProbeType, TypedProbe, typed_prediction_row
from .r244_recursive_abstraction import (
    RecursiveAbstractionRecord,
    _CONNECTIVES,
    _base_argument_candidates,
    _program_atom_ids,
    propagate_quarantine,
)


def _normalize_distribution(values: Mapping[str, float], expected_ids: Sequence[str]) -> dict[str, float]:
    ids = tuple(map(str, expected_ids))
    raw = {str(k): float(v) for k, v in values.items()}
    if set(raw) != set(ids):
        raise ValueError('posterior/hypothesis coverage mismatch')
    if any((not math.isfinite(v)) or v < 0.0 for v in raw.values()):
        raise ValueError('posterior must contain finite non-negative masses')
    total = sum(raw.values())
    if total <= 0.0:
        raise ValueError('posterior mass must be positive')
    return {hid: raw[hid] / total for hid in ids}


def binary_mutual_information(
    row: Mapping[str, bool],
    target: Mapping[str, bool],
    posterior: Mapping[str, float],
) -> float:
    """I(row; target), measured under the current hypothesis posterior.

    In R2.45 target is the observable test/counterexample outcome, not hidden
    structural metadata. This makes role inference goal-directed while removing
    the privileged per-macro argument scopes used by the R2.44 benchmark.
    """
    if set(row) != set(target) or set(row) != set(posterior):
        raise ValueError('row/target/posterior coverage mismatch')
    joint = {(a, b): 0.0 for a in (False, True) for b in (False, True)}
    pa = {False: 0.0, True: 0.0}
    pb = {False: 0.0, True: 0.0}
    for hid, mass in posterior.items():
        m = float(mass)
        a, b = bool(row[hid]), bool(target[hid])
        joint[(a, b)] += m
        pa[a] += m
        pb[b] += m
    out = 0.0
    for (a, b), mass in joint.items():
        denom = pa[a] * pb[b]
        if mass > 0.0 and denom > 0.0:
            out += mass * math.log2(mass / denom)
    if abs(out) < 1e-15:
        return 0.0
    if abs(out - 1.0) < 1e-15:
        return 1.0
    return max(0.0, out)


@dataclass(frozen=True)
class RoleFreeApplication:
    macro_id: str
    program: TypedProbe
    semantic_key: tuple[bool, ...]
    target_information: float
    generation: int


@dataclass(frozen=True)
class RoleFreeBindingReceipt:
    status: str
    target_macro_id: str
    program: TypedProbe | None
    exact: bool
    candidates_evaluated: int
    base_bindings_evaluated: int
    recursive_pairs_evaluated: int
    shared_atom_count: int
    base_macro_count: int
    privileged_role_scopes_used: bool
    beam_width: int
    blocked_closure: tuple[str, ...]
    max_generation: int
    frontier_sizes: tuple[tuple[str, int], ...]
    reason: str


def solve_role_free_recursive_macro(
    macro_id: str,
    *,
    base_macros: Sequence[ProbeMacro],
    records: Sequence[RecursiveAbstractionRecord],
    atom_ids: Sequence[str],
    posterior: Mapping[str, float],
    atom_values_by_hypothesis: Mapping[str, Mapping[str, int | bool]],
    target_labels: Mapping[str, bool],
    blocked_macro_ids: Sequence[str] = (),
    beam_width: int = 8,
) -> RoleFreeBindingReceipt:
    """Bind a recursive abstraction without per-macro argument scopes.

    Every Boolean base macro receives the same full atom set. Base bindings are
    enumerated exactly once. At each learned recursive node, only structurally
    legal disjoint parent applications are combined, semantic duplicates are
    collapsed, and a small beam is retained by mutual information with the
    observable target/test labels. No concrete role assignment is supplied.
    """
    beam_width = int(beam_width)
    if beam_width <= 0:
        raise ValueError('beam_width must be positive')
    atoms = tuple(sorted({str(a).strip().lower() for a in atom_ids if str(a).strip()}))
    if not atoms:
        raise ValueError('atom_ids must be non-empty')
    base_by_id = {str(m.macro_id): m for m in base_macros}
    rec_by_id = {str(r.macro.macro_id): r for r in records}
    if len(base_by_id) != len(tuple(base_macros)) or len(rec_by_id) != len(tuple(records)):
        raise ValueError('duplicate macro ids')
    if set(base_by_id) & set(rec_by_id):
        raise ValueError('base/recursive macro id collision')
    all_ids = set(base_by_id) | set(rec_by_id)
    target_id = str(macro_id)
    if target_id not in all_ids:
        raise KeyError(target_id)

    for macro in base_macros:
        if any(t is not ProbeType.BOOL for t in macro.parameter_types):
            raise TypeError('R2.45 role-free solver currently requires Boolean base parameters')
    for rec in records:
        if any(parent not in all_ids for parent in rec.parent_macro_ids):
            raise ValueError('recursive parent missing from registry')
        if any(
            rec_by_id[parent].generation >= rec.generation
            for parent in rec.parent_macro_ids
            if parent in rec_by_id
        ):
            raise ValueError('recursive lineage must be acyclic by generation')

    blocked = propagate_quarantine(records, blocked_macro_ids)
    if target_id in blocked:
        return RoleFreeBindingReceipt(
            'blocked', target_id, None, False, 0, 0, 0, len(atoms), len(base_by_id),
            False, beam_width, tuple(sorted(blocked)), 0, (), 'target_or_ancestor_quarantined',
        )

    hypothesis_ids = tuple(sorted(map(str, atom_values_by_hypothesis)))
    if not hypothesis_ids:
        raise ValueError('hypotheses must be non-empty')
    post = _normalize_distribution(posterior, hypothesis_ids)
    target = {str(h): bool(v) for h, v in target_labels.items()}
    if set(target) != set(hypothesis_ids):
        raise ValueError('target label coverage mismatch')
    for hid in hypothesis_ids:
        missing = set(atoms) - set(map(str, atom_values_by_hypothesis[hid]))
        if missing:
            raise ValueError(f'hypothesis {hid} missing atoms')

    memo: dict[str, tuple[RoleFreeApplication, ...]] = {}
    base_evals = 0
    pair_evals = 0
    max_generation = 0

    def rank_and_dedupe(mid: str, generation: int, programs: Sequence[TypedProbe], *, prune: bool) -> tuple[RoleFreeApplication, ...]:
        by_semantics: dict[tuple[bool, ...], RoleFreeApplication] = {}
        for program in programs:
            row = typed_prediction_row(program, atom_values_by_hypothesis)
            key = tuple(bool(row[h]) for h in hypothesis_ids)
            info = binary_mutual_information(row, target, post)
            app = RoleFreeApplication(mid, program, key, info, generation)
            prior = by_semantics.get(key)
            if prior is None or (
                -app.target_information, app.program.execution_cost, app.program.probe_id
            ) < (
                -prior.target_information, prior.program.execution_cost, prior.program.probe_id
            ):
                by_semantics[key] = app
        ranked = sorted(
            by_semantics.values(),
            key=lambda app: (-app.target_information, app.program.execution_cost, app.program.probe_id),
        )
        return tuple(ranked[:beam_width] if prune else ranked)

    def build(mid: str) -> tuple[RoleFreeApplication, ...]:
        nonlocal base_evals, pair_evals, max_generation
        if mid in memo:
            return memo[mid]
        if mid in blocked:
            memo[mid] = ()
            return ()
        if mid in base_by_id:
            macro = base_by_id[mid]
            args = _base_argument_candidates(macro, {ProbeType.BOOL: atoms})
            base_evals += len(args)
            programs = tuple(instantiate_macro(macro, args_row) for args_row in args)
            memo[mid] = rank_and_dedupe(mid, 0, programs, prune=False)
            return memo[mid]

        rec = rec_by_id[mid]
        max_generation = max(max_generation, int(rec.generation))
        left_id, right_id = rec.parent_macro_ids
        left_apps = build(left_id)
        right_apps = build(right_id)
        if not left_apps or not right_apps:
            memo[mid] = ()
            return ()
        ctor = _CONNECTIVES[rec.connective]
        programs: list[TypedProbe] = []
        for left in left_apps:
            for right in right_apps:
                if _program_atom_ids(left.program) & _program_atom_ids(right.program):
                    continue
                pair_evals += 1
                programs.append(ctor(left.program, right.program))
        memo[mid] = rank_and_dedupe(mid, int(rec.generation), programs, prune=True)
        return memo[mid]

    final_apps = build(target_id)
    exact_apps = [app for app in final_apps if app.semantic_key == tuple(target[h] for h in hypothesis_ids)]
    chosen = min(
        exact_apps,
        key=lambda app: (app.program.execution_cost, app.program.probe_id),
        default=(final_apps[0] if final_apps else None),
    )
    exact = bool(exact_apps)
    status = 'accept' if exact else ('abstain' if chosen is None else 'candidate')
    return RoleFreeBindingReceipt(
        status=status,
        target_macro_id=target_id,
        program=None if chosen is None else chosen.program,
        exact=exact,
        candidates_evaluated=base_evals + pair_evals,
        base_bindings_evaluated=base_evals,
        recursive_pairs_evaluated=pair_evals,
        shared_atom_count=len(atoms),
        base_macro_count=len(base_by_id),
        privileged_role_scopes_used=False,
        beam_width=beam_width,
        blocked_closure=tuple(sorted(blocked)),
        max_generation=max_generation,
        frontier_sizes=tuple(sorted((mid, len(apps)) for mid, apps in memo.items())),
        reason='exact_role_free_recursive_binding' if exact else 'role_free_binding_not_exact',
    )
