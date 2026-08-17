from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r239_typed_probe_dsl import (
    TypedProbe,
    add3,
    and_probe,
    const3,
    eq_probe,
    equiv_probe,
    neq_probe,
    or_probe,
    sub3,
    trit_atom,
    typed_prediction_row,
    xor_probe,
)


@dataclass(frozen=True)
class RecursiveSynthesisReceipt:
    program: TypedProbe
    shortlisted_atoms: tuple[str, ...]
    raw_candidates_evaluated: int
    semantic_candidates: int
    best_disagreement: float
    best_utility: float
    best_r238_binary_disagreement: float
    best_r238_binary_utility: float
    best_recursive_program: TypedProbe
    best_recursive_disagreement: float
    best_recursive_utility: float


def _stable_sum(values):
    total = 0.0
    for value in values:
        total += float(value)
    return total


def _posterior(supports) -> dict[str, float]:
    rows = {str(s.operator_id): float(s.posterior) for s in supports}
    total = _stable_sum(rows.values())
    if not rows or total <= 0:
        raise ValueError('supports must contain positive posterior mass')
    return {k: rows[k] / total for k in sorted(rows)}


def _categorical_disagreement(atom_id: str, posterior: Mapping[str, float], values) -> float:
    bins = {0: 0.0, 1: 0.0, 2: 0.0}
    for hid, p in posterior.items():
        value = int(values[hid][atom_id])
        if value not in bins:
            raise ValueError('trit atom values must be 0, 1 or 2')
        bins[value] += p
    return 1.0 - sum(v * v for v in bins.values())


def _bool_disagreement(row: Mapping[str, bool], posterior: Mapping[str, float]) -> float:
    if set(row) != set(posterior):
        raise ValueError('prediction coverage mismatch')
    p_true = _stable_sum(posterior[hid] for hid, label in row.items() if bool(label))
    return 2.0 * p_true * (1.0 - p_true)


def _utility(program: TypedProbe, disagreement: float, *, execution_cost_weight: float, mdl_weight: float) -> float:
    return (
        float(disagreement)
        - float(execution_cost_weight) * (program.execution_cost - 1.0)
        - float(mdl_weight) * program.mdl_cost
    )


def _simple_predicates(shortlist: Sequence[str]) -> tuple[TypedProbe, ...]:
    atoms = {qid: trit_atom(qid) for qid in shortlist}
    rows: list[TypedProbe] = []
    for qid in shortlist:
        for value in (0, 1, 2):
            rows.append(eq_probe(atoms[qid], const3(value)))
            rows.append(neq_probe(atoms[qid], const3(value)))
    for a, b in itertools.combinations(shortlist, 2):
        rows.append(eq_probe(atoms[a], atoms[b]))
        rows.append(neq_probe(atoms[a], atoms[b]))
    return tuple(sorted(set(rows), key=lambda p: p.probe_id))


def _r238_binary_candidates(simple: Sequence[TypedProbe], posterior, values) -> tuple[TypedProbe, ...]:
    ranked = sorted(
        simple,
        key=lambda p: (-_bool_disagreement(typed_prediction_row(p, values), posterior), p.probe_id),
    )[:12]
    rows: list[TypedProbe] = list(simple)
    for a, b in itertools.combinations(ranked, 2):
        rows.extend((and_probe(a, b), or_probe(a, b), xor_probe(a, b), equiv_probe(a, b)))
    return tuple(rows)


def _recursive_candidates(shortlist: Sequence[str], simple: Sequence[TypedProbe]) -> tuple[TypedProbe, ...]:
    atoms = {qid: trit_atom(qid) for qid in shortlist}
    rows: list[TypedProbe] = []
    for a, b in itertools.combinations(shortlist, 2):
        add = add3(atoms[a], atoms[b])
        for c in shortlist:
            if c in (a, b):
                continue
            rows.extend((eq_probe(add, atoms[c]), neq_probe(add, atoms[c])))
        for value in (0, 1, 2):
            rows.extend((eq_probe(add, const3(value)), neq_probe(add, const3(value))))
    for a, b in itertools.permutations(shortlist, 2):
        diff = sub3(atoms[a], atoms[b])
        for c in shortlist:
            if c in (a, b):
                continue
            rows.extend((eq_probe(diff, atoms[c]), neq_probe(diff, atoms[c])))
        for value in (0, 1, 2):
            rows.extend((eq_probe(diff, const3(value)), neq_probe(diff, const3(value))))
    compact = tuple(sorted(simple, key=lambda p: (p.mdl_cost, p.probe_id))[:6])
    for a, b, c in itertools.combinations(compact, 3):
        for first in (and_probe, or_probe, xor_probe, equiv_probe):
            left = first(a, b)
            for second in (and_probe, or_probe, xor_probe, equiv_probe):
                rows.append(second(left, c))
    return tuple(rows)


def synthesize_recursive_typed_probe(
    trit_atom_ids: Sequence[str],
    supports,
    atom_values_by_hypothesis: Mapping[str, Mapping[str, int]],
    observed_probe_ids,
    *,
    atom_shortlist_size: int = 8,
    max_raw_candidates: int = 480,
    max_depth: int = 4,
    max_mdl_cost: int = 9,
    max_leaves: int = 4,
    execution_cost_weight: float = 0.02,
    mdl_weight: float = 0.005,
) -> RecursiveSynthesisReceipt:
    posterior = _posterior(supports)
    if set(atom_values_by_hypothesis) != set(posterior):
        raise ValueError('hypothesis value coverage mismatch')
    ids = tuple(sorted({str(v).strip().lower() for v in trit_atom_ids if str(v).strip()}))
    if len(ids) < 2:
        raise ValueError('at least two trit atoms are required')
    if int(atom_shortlist_size) < 2:
        raise ValueError('atom_shortlist_size must be at least 2')
    for hid in posterior:
        if any(qid not in atom_values_by_hypothesis[hid] for qid in ids):
            raise ValueError('missing trit atom value')
    shortlist = tuple(sorted(
        ids,
        key=lambda qid: (-_categorical_disagreement(qid, posterior, atom_values_by_hypothesis), qid),
    )[: min(int(atom_shortlist_size), len(ids))])

    simple = _simple_predicates(shortlist)
    baseline = _r238_binary_candidates(simple, posterior, atom_values_by_hypothesis)
    recursive = _recursive_candidates(shortlist, simple)
    observed = {str(v) for v in observed_probe_ids}

    max_raw_candidates = int(max_raw_candidates)
    if max_raw_candidates <= 0:
        raise ValueError('max_raw_candidates must be positive')
    baseline_budget = min(len(baseline), max(1, max_raw_candidates // 2))
    recursive_budget = max(0, max_raw_candidates - baseline_budget)
    candidates = tuple(baseline[:baseline_budget]) + tuple(recursive[:recursive_budget])
    semantic: dict[tuple[bool, ...], tuple[float, float, TypedProbe, float]] = {}
    raw_evaluated = 0
    baseline_disagreement = 0.0
    baseline_utility = float('-inf')
    baseline_ids = {p.probe_id for p in baseline}
    best_recursive: tuple[float, float, TypedProbe] | None = None

    for program in candidates:
        if raw_evaluated >= max_raw_candidates:
            break
        if program.probe_id in observed:
            continue
        if program.depth > int(max_depth) or program.mdl_cost > int(max_mdl_cost) or program.leaf_count > int(max_leaves):
            continue
        row = typed_prediction_row(program, atom_values_by_hypothesis)
        raw_evaluated += 1
        disagreement = _bool_disagreement(row, posterior)
        utility = _utility(program, disagreement, execution_cost_weight=float(execution_cost_weight), mdl_weight=float(mdl_weight))
        if program.probe_id in baseline_ids:
            baseline_disagreement = max(baseline_disagreement, disagreement)
            baseline_utility = max(baseline_utility, utility)
        elif program.depth >= 3:
            candidate_recursive = (utility, disagreement, program)
            if best_recursive is None or (-utility, -disagreement, program.mdl_cost, program.probe_id) < (-best_recursive[0], -best_recursive[1], best_recursive[2].mdl_cost, best_recursive[2].probe_id):
                best_recursive = candidate_recursive
        key = tuple(bool(row[hid]) for hid in posterior)
        current = semantic.get(key)
        candidate_key = (program.mdl_cost, program.execution_cost, program.probe_id)
        if current is None or candidate_key < (current[2].mdl_cost, current[2].execution_cost, current[2].probe_id):
            semantic[key] = (utility, disagreement, program, program.execution_cost)

    if not semantic:
        raise ValueError('no legal unobserved typed probe remains')
    if best_recursive is None:
        raise ValueError('no legal recursive typed probe remains')
    best = min(semantic.values(), key=lambda row: (-row[0], -row[1], row[2].mdl_cost, row[2].probe_id))
    return RecursiveSynthesisReceipt(
        program=best[2], shortlisted_atoms=shortlist, raw_candidates_evaluated=raw_evaluated,
        semantic_candidates=len(semantic), best_disagreement=best[1], best_utility=best[0],
        best_r238_binary_disagreement=baseline_disagreement, best_r238_binary_utility=baseline_utility,
        best_recursive_program=best_recursive[2], best_recursive_disagreement=best_recursive[1], best_recursive_utility=best_recursive[0],
    )
