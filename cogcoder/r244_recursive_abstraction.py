from __future__ import annotations

import hashlib
import itertools
import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r239_predicate_macros import ProbeMacro, abstract_macro_template, instantiate_macro
from .r239_typed_probe_dsl import (
    ProbeType,
    TypedProbe,
    and_probe,
    bool_atom,
    equiv_probe,
    or_probe,
    trit_atom,
    typed_prediction_row,
    xor_probe,
)
from .r243_macro_composition import CompositionDiscoveryDecision

_CONNECTIVES = {
    'and': and_probe,
    'or': or_probe,
    'xor': xor_probe,
    'equiv': equiv_probe,
}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:24]


def _binary_entropy(p: float) -> float:
    p = max(0.0, min(1.0, float(p)))
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))


def _normalize_posterior(
    posterior: Mapping[str, float], hypothesis_ids: Sequence[str]
) -> dict[str, float]:
    ids = tuple(map(str, hypothesis_ids))
    raw = {str(k): float(v) for k, v in posterior.items()}
    if set(raw) != set(ids):
        raise ValueError('posterior/hypothesis coverage mismatch')
    if any((not math.isfinite(v)) or v < 0.0 for v in raw.values()):
        raise ValueError('posterior must contain finite non-negative masses')
    total = sum(raw.values())
    if total <= 0.0:
        raise ValueError('posterior mass must be positive')
    return {hid: raw[hid] / total for hid in ids}


def _row_information(row: Mapping[str, bool], posterior: Mapping[str, float]) -> float:
    p = sum(float(posterior[h]) for h, label in row.items() if bool(label))
    return _binary_entropy(p)


def _conditional_entropy(
    child: Mapping[str, bool],
    parent: Mapping[str, bool],
    posterior: Mapping[str, float],
) -> float:
    """H(child | parent) in bits under the current posterior.

    A copied/degenerate child has zero novelty with respect to its source parent,
    while a genuine two-parent composition stays positive even when marginal
    entropy is already near the one-bit ceiling. This avoids R2.43's depth
    saturation where every layer was required to increase marginal entropy.
    """
    out = 0.0
    for parent_label in (False, True):
        mass = sum(
            float(posterior[h])
            for h in posterior
            if bool(parent[h]) is parent_label
        )
        if mass <= 0.0:
            continue
        child_true = sum(
            float(posterior[h])
            for h in posterior
            if bool(parent[h]) is parent_label and bool(child[h])
        )
        out += mass * _binary_entropy(child_true / mass)
    return max(0.0, min(1.0, out))


def conditional_composition_novelty(
    child: Mapping[str, bool],
    left: Mapping[str, bool],
    right: Mapping[str, bool],
    posterior: Mapping[str, float],
) -> float:
    """Novelty that requires *both* parents: min(H(C|L), H(C|R))."""
    if set(child) != set(left) or set(child) != set(right) or set(child) != set(posterior):
        raise ValueError('semantic row/posterior coverage mismatch')
    return min(
        _conditional_entropy(child, left, posterior),
        _conditional_entropy(child, right, posterior),
    )


def _program_atom_ids(program: TypedProbe) -> frozenset[tuple[ProbeType, str]]:
    out: set[tuple[ProbeType, str]] = set()
    stack = [program]
    while stack:
        node = stack.pop()
        if node.op == 'atom':
            out.add((node.output_type, str(node.atom_id)))
        else:
            stack.extend(node.children)
    return frozenset(out)


def _decision_novelty(decision: object) -> float:
    if hasattr(decision, 'conditional_novelty'):
        return float(getattr(decision, 'conditional_novelty'))
    return max(0.0, float(getattr(decision, 'synergy', 0.0)))


@dataclass(frozen=True, order=True)
class RecursiveAbstractionRecord:
    macro: ProbeMacro
    generation: int
    connective: str
    parent_macro_ids: tuple[str, ...]
    ancestor_macro_ids: tuple[str, ...]
    support_episode_ids: tuple[str, ...]
    source_composition_ids: tuple[str, ...]
    mean_novelty: float

    def __post_init__(self) -> None:
        if int(self.generation) <= 0:
            raise ValueError('generation must be positive')
        connective = str(self.connective).strip().lower()
        if connective not in _CONNECTIVES:
            raise ValueError('unsupported recursive connective')
        if len(self.parent_macro_ids) != 2:
            raise ValueError('recursive abstraction requires exactly two parents')
        if not self.support_episode_ids:
            raise ValueError('support episodes must be non-empty')
        if not 0.0 <= float(self.mean_novelty) <= 1.0:
            raise ValueError('mean_novelty must be in [0,1]')
        object.__setattr__(self, 'connective', connective)
        object.__setattr__(self, 'mean_novelty', float(self.mean_novelty))

    @property
    def mean_synergy(self) -> float:
        """Compatibility alias for early R2.44 callers/evidence."""
        return self.mean_novelty


@dataclass(frozen=True)
class RecursiveMacroApplication:
    macro_id: str
    program: TypedProbe
    semantic_key: tuple[bool, ...]
    information_gain: float
    generation: int
    leaf_macro_ids: tuple[str, ...]


@dataclass(frozen=True)
class RecursiveFrontierReceipt:
    macro_id: str
    applications: tuple[RecursiveMacroApplication, ...]
    candidates_evaluated: int
    base_bindings_evaluated: int
    recursive_pairs_evaluated: int
    max_generation: int
    reason: str


@dataclass(frozen=True)
class RecursiveCompositionDecision:
    status: str
    composition_id: str | None
    selected_macro_ids: tuple[str, ...]
    connective: str | None
    program: TypedProbe | None
    information_gain: float
    best_parent_information_gain: float
    conditional_novelty: float
    candidates_evaluated: int
    counterexamples_checked: int
    rejected_composition_ids: tuple[str, ...]
    reason: str


def promote_composition_batch(
    decisions: Mapping[str, CompositionDiscoveryDecision | RecursiveCompositionDecision],
    *,
    base_macros: Sequence[ProbeMacro] = (),
    prior_records: Sequence[RecursiveAbstractionRecord] = (),
    min_support: int = 3,
    call_mdl_cost: int = 2,
) -> tuple[RecursiveAbstractionRecord, ...]:
    """Promote repeated counterexample-surviving compositions into reusable macros.

    Promotion is cross-episode, concrete atom identities are abstracted away, and
    complete parent/ancestor lineage is retained for transitive falsification.
    """
    min_support = int(min_support)
    if min_support < 2:
        raise ValueError('min_support must be at least 2')
    call_mdl_cost = int(call_mdl_cost)
    if call_mdl_cost <= 0:
        raise ValueError('call_mdl_cost must be positive')

    known: dict[str, tuple[int, frozenset[str]]] = {}
    for macro in base_macros:
        mid = str(macro.macro_id)
        if mid in known:
            raise ValueError('duplicate macro id')
        known[mid] = (0, frozenset())
    for rec in prior_records:
        mid = str(rec.macro.macro_id)
        if mid in known:
            raise ValueError('duplicate macro id')
        known[mid] = (
            int(rec.generation),
            frozenset(rec.ancestor_macro_ids) | frozenset(rec.parent_macro_ids),
        )

    grouped: dict[tuple[str, tuple, tuple[str, ...], str], list[tuple[str, object, TypedProbe, tuple]]] = {}
    for episode_id in sorted(map(str, decisions)):
        decision = decisions[episode_id]
        if getattr(decision, 'status', None) != 'accept' or getattr(decision, 'program', None) is None or getattr(decision, 'composition_id', None) is None:
            continue
        parents = tuple(sorted(map(str, getattr(decision, 'selected_macro_ids', ()))))
        connective = str(getattr(decision, 'connective', '')).strip().lower()
        if len(parents) != 2 or any(mid not in known for mid in parents) or connective not in _CONNECTIVES:
            continue
        template, parameter_types = abstract_macro_template(getattr(decision, 'program'))
        key = (template.probe_id, parameter_types, parents, connective)
        grouped.setdefault(key, []).append((episode_id, decision, template, parameter_types))

    promoted: list[RecursiveAbstractionRecord] = []
    for (template_id, parameter_types, parents, connective), rows in sorted(grouped.items(), key=lambda item: item[0][0]):
        episode_ids = tuple(sorted({row[0] for row in rows}))
        if len(episode_ids) < min_support:
            continue
        representative = min(rows, key=lambda row: (row[0], str(getattr(row[1], 'composition_id', ''))))
        template = representative[2]
        generation = 1 + max(known[mid][0] for mid in parents)
        ancestors: set[str] = set(parents)
        for mid in parents:
            ancestors.update(known[mid][1])
        raw = int(template.mdl_cost)
        definition_cost = raw
        compression_gain = float(len(episode_ids) * max(0, raw - call_mdl_cost) - definition_cost)
        if compression_gain <= 0.0:
            continue
        payload = '|'.join((
            f'g={generation}', template_id, f'c={connective}',
            'parents=' + ','.join(parents),
            'types=' + ','.join(t.value for t in parameter_types),
        ))
        macro = ProbeMacro(
            macro_id='ram:' + _digest(payload),
            template=template,
            parameter_types=tuple(parameter_types),
            support=len(episode_ids),
            compression_gain=compression_gain,
            raw_mdl_cost=raw,
            call_mdl_cost=call_mdl_cost,
        )
        source_ids = tuple(sorted({str(getattr(row[1], 'composition_id')) for row in rows}))
        novelties = [_decision_novelty(row[1]) for row in rows]
        promoted.append(RecursiveAbstractionRecord(
            macro=macro,
            generation=generation,
            connective=connective,
            parent_macro_ids=parents,
            ancestor_macro_ids=tuple(sorted(ancestors)),
            support_episode_ids=episode_ids,
            source_composition_ids=source_ids,
            mean_novelty=sum(novelties) / len(novelties),
        ))
    return tuple(sorted(promoted, key=lambda rec: (rec.generation, rec.macro.macro_id)))


def propagate_quarantine(
    records: Sequence[RecursiveAbstractionRecord],
    initial_blocked_ids: Sequence[str] | set[str] | frozenset[str],
) -> frozenset[str]:
    """Return the transitive quarantine closure over abstraction lineage."""
    blocked = {str(mid) for mid in initial_blocked_ids}
    changed = True
    ordered = tuple(sorted(records, key=lambda r: (r.generation, r.macro.macro_id)))
    while changed:
        changed = False
        for rec in ordered:
            mid = str(rec.macro.macro_id)
            if mid in blocked:
                continue
            dependencies = set(rec.parent_macro_ids) | set(rec.ancestor_macro_ids)
            if dependencies & blocked:
                blocked.add(mid)
                changed = True
    return frozenset(blocked)


def _base_argument_candidates(
    macro: ProbeMacro,
    pools: Mapping[ProbeType, Sequence[str]],
) -> tuple[tuple[TypedProbe, ...], ...]:
    choices: list[tuple[TypedProbe, ...]] = []
    for expected in macro.parameter_types:
        ids = tuple(sorted({str(v).strip().lower() for v in pools.get(expected, ()) if str(v).strip()}))
        if not ids:
            return ()
        ctor = trit_atom if expected is ProbeType.TRIT else bool_atom
        choices.append(tuple(ctor(atom_id) for atom_id in ids))
    out = []
    for args in itertools.product(*choices):
        typed = tuple((arg.output_type, str(arg.atom_id)) for arg in args)
        if len(set(typed)) != len(typed):
            continue
        out.append(tuple(args))
    return tuple(out)


def _dedupe_rank_applications(
    macro_id: str,
    generation: int,
    programs: Sequence[TypedProbe],
    posterior: Mapping[str, float],
    values_by_hypothesis: Mapping[str, Mapping[str, int | bool]],
    hypothesis_ids: Sequence[str],
    *,
    leaf_macro_ids: Sequence[str],
    max_applications: int,
) -> tuple[RecursiveMacroApplication, ...]:
    by_semantics: dict[tuple[bool, ...], RecursiveMacroApplication] = {}
    for program in programs:
        row = typed_prediction_row(program, values_by_hypothesis)
        key = tuple(bool(row[h]) for h in hypothesis_ids)
        app = RecursiveMacroApplication(
            str(macro_id), program, key, _row_information(row, posterior),
            int(generation), tuple(sorted(map(str, leaf_macro_ids))),
        )
        prior = by_semantics.get(key)
        if prior is None or (program.execution_cost, program.probe_id) < (prior.program.execution_cost, prior.program.probe_id):
            by_semantics[key] = app
    ranked = sorted(
        by_semantics.values(),
        key=lambda app: (-app.information_gain, app.program.execution_cost, app.program.probe_id),
    )
    return tuple(ranked[: max(1, int(max_applications))])


def build_recursive_application_frontier(
    macro_id: str,
    *,
    base_macros: Sequence[ProbeMacro],
    records: Sequence[RecursiveAbstractionRecord],
    atom_pools_by_macro: Mapping[str, Mapping[ProbeType, Sequence[str]]],
    posterior: Mapping[str, float],
    atom_values_by_hypothesis: Mapping[str, Mapping[str, int | bool]],
    blocked_macro_ids: Sequence[str] = (),
    max_applications_per_node: int = 12,
) -> RecursiveFrontierReceipt:
    """Instantiate a promoted abstraction through its lineage DAG, not flat arity.

    The key complexity change is hierarchical binding: a generation-N macro is
    evaluated by reusing the already-bounded frontiers of its two parents. It
    never enumerates all permutations of its full raw parameter list.
    """
    if int(max_applications_per_node) <= 0:
        raise ValueError('max_applications_per_node must be positive')
    base_by_id = {str(m.macro_id): m for m in base_macros}
    record_by_id = {str(r.macro.macro_id): r for r in records}
    if len(base_by_id) != len(tuple(base_macros)) or len(record_by_id) != len(tuple(records)):
        raise ValueError('duplicate macro ids')
    overlap = set(base_by_id) & set(record_by_id)
    if overlap:
        raise ValueError('base/recursive macro id collision')
    all_ids = set(base_by_id) | set(record_by_id)
    for rec in records:
        if any(parent not in all_ids for parent in rec.parent_macro_ids):
            raise ValueError('recursive parent is missing from registry')
        if any((record_by_id[parent].generation >= rec.generation) for parent in rec.parent_macro_ids if parent in record_by_id):
            raise ValueError('recursive generations must form an acyclic ladder')

    blocked = propagate_quarantine(records, blocked_macro_ids)
    target_id = str(macro_id)
    if target_id not in all_ids:
        raise KeyError(target_id)
    if target_id in blocked:
        return RecursiveFrontierReceipt(target_id, (), 0, 0, 0, 0, 'macro_or_ancestor_quarantined')

    hypothesis_ids = tuple(sorted(map(str, atom_values_by_hypothesis)))
    if not hypothesis_ids:
        raise ValueError('hypotheses must be non-empty')
    post = _normalize_posterior(posterior, hypothesis_ids)
    memo: dict[str, tuple[tuple[RecursiveMacroApplication, ...], int, int, int, int]] = {}

    def build(mid: str):
        if mid in memo:
            return memo[mid]
        if mid in blocked:
            memo[mid] = ((), 0, 0, 0, 0)
            return memo[mid]
        if mid in base_by_id:
            macro = base_by_id[mid]
            pools = atom_pools_by_macro.get(mid, {})
            args = _base_argument_candidates(macro, pools)
            programs = tuple(instantiate_macro(macro, row) for row in args)
            apps = _dedupe_rank_applications(
                mid, 0, programs, post, atom_values_by_hypothesis, hypothesis_ids,
                leaf_macro_ids=(mid,), max_applications=max_applications_per_node,
            )
            memo[mid] = (apps, len(args), len(args), 0, 0)
            return memo[mid]

        rec = record_by_id[mid]
        left_id, right_id = rec.parent_macro_ids
        left_apps, left_total, left_base, left_pairs, left_gen = build(left_id)
        right_apps, right_total, right_base, right_pairs, right_gen = build(right_id)
        if not left_apps or not right_apps:
            memo[mid] = ((), left_total + right_total, left_base + right_base, left_pairs + right_pairs, rec.generation)
            return memo[mid]
        ctor = _CONNECTIVES[rec.connective]
        programs = []
        pair_evals = 0
        for left in left_apps:
            for right in right_apps:
                if _program_atom_ids(left.program) & _program_atom_ids(right.program):
                    continue
                pair_evals += 1
                programs.append(ctor(left.program, right.program))
        leaves = tuple(sorted({leaf for app in left_apps + right_apps for leaf in app.leaf_macro_ids}))
        apps = _dedupe_rank_applications(
            mid, rec.generation, programs, post, atom_values_by_hypothesis, hypothesis_ids,
            leaf_macro_ids=leaves, max_applications=max_applications_per_node,
        )
        total = left_total + right_total + pair_evals
        base_count = left_base + right_base
        pair_count = left_pairs + right_pairs + pair_evals
        memo[mid] = (apps, total, base_count, pair_count, max(rec.generation, left_gen, right_gen))
        return memo[mid]

    apps, total, base_count, pair_count, max_gen = build(target_id)
    return RecursiveFrontierReceipt(
        target_id, apps, total, base_count, pair_count, max_gen,
        'recursive_frontier_ready' if apps else 'no_recursive_applications',
    )


def discover_recursive_composed_probe(
    *,
    base_macros: Sequence[ProbeMacro],
    records: Sequence[RecursiveAbstractionRecord],
    atom_pools_by_macro: Mapping[str, Mapping[ProbeType, Sequence[str]]],
    posterior: Mapping[str, float],
    atom_values_by_hypothesis: Mapping[str, Mapping[str, int | bool]],
    blocked_macro_ids: Sequence[str] = (),
    connectives: Sequence[str] = ('and', 'or', 'xor', 'equiv'),
    max_applications_per_node: int = 8,
    max_composition_candidates: int = 256,
    min_conditional_novelty: float = 0.02,
    counterexample_check: Callable[[TypedProbe], bool] | None = None,
) -> RecursiveCompositionDecision:
    """Search over base + promoted abstractions with a depth-safe novelty gate."""
    if int(max_composition_candidates) <= 0:
        raise ValueError('max_composition_candidates must be positive')
    min_conditional_novelty = float(min_conditional_novelty)
    if not 0.0 <= min_conditional_novelty <= 1.0:
        raise ValueError('min_conditional_novelty must be in [0,1]')
    connective_names = tuple(sorted({str(c).strip().lower() for c in connectives}))
    if any(c not in _CONNECTIVES for c in connective_names):
        raise ValueError('unsupported connective')

    recursive_by_id = {str(r.macro.macro_id): r.macro for r in records}
    registry = {str(m.macro_id): m for m in base_macros}
    if set(registry) & set(recursive_by_id):
        raise ValueError('macro id collision')
    registry.update(recursive_by_id)
    blocked = propagate_quarantine(records, blocked_macro_ids)
    active_ids = tuple(sorted(mid for mid in registry if mid not in blocked))
    if len(active_ids) < 2:
        return RecursiveCompositionDecision('abstain', None, (), None, None, 0.0, 0.0, 0.0, 0, 0, (), 'need_two_trusted_macros')

    hypothesis_ids = tuple(sorted(map(str, atom_values_by_hypothesis)))
    post = _normalize_posterior(posterior, hypothesis_ids)
    frontiers: dict[str, tuple[RecursiveMacroApplication, ...]] = {}
    frontier_evaluations = 0
    for mid in active_ids:
        receipt = build_recursive_application_frontier(
            mid, base_macros=base_macros, records=records,
            atom_pools_by_macro=atom_pools_by_macro, posterior=post,
            atom_values_by_hypothesis=atom_values_by_hypothesis,
            blocked_macro_ids=blocked, max_applications_per_node=max_applications_per_node,
        )
        frontiers[mid] = receipt.applications
        frontier_evaluations += receipt.candidates_evaluated

    candidates = []
    pair_evaluated = 0
    seen_semantics: set[tuple[bool, ...]] = set()
    for li, left_id in enumerate(active_ids):
        for right_id in active_ids[li + 1:]:
            left_rec = next((r for r in records if r.macro.macro_id == left_id), None)
            right_rec = next((r for r in records if r.macro.macro_id == right_id), None)
            if left_rec is not None and right_id in set(left_rec.ancestor_macro_ids) | set(left_rec.parent_macro_ids):
                continue
            if right_rec is not None and left_id in set(right_rec.ancestor_macro_ids) | set(right_rec.parent_macro_ids):
                continue
            for left in frontiers[left_id]:
                for right in frontiers[right_id]:
                    if _program_atom_ids(left.program) & _program_atom_ids(right.program):
                        continue
                    left_row = {h: left.semantic_key[i] for i, h in enumerate(hypothesis_ids)}
                    right_row = {h: right.semantic_key[i] for i, h in enumerate(hypothesis_ids)}
                    for connective in connective_names:
                        if pair_evaluated >= int(max_composition_candidates):
                            break
                        pair_evaluated += 1
                        program = _CONNECTIVES[connective](left.program, right.program)
                        row = typed_prediction_row(program, atom_values_by_hypothesis)
                        key = tuple(bool(row[h]) for h in hypothesis_ids)
                        if key in seen_semantics:
                            continue
                        seen_semantics.add(key)
                        novelty = conditional_composition_novelty(row, left_row, right_row, post)
                        if novelty + 1e-12 < min_conditional_novelty:
                            continue
                        info = _row_information(row, post)
                        parent_info = max(left.information_gain, right.information_gain)
                        generation = 1 + max(left.generation, right.generation)
                        score = info + 0.35 * novelty + 0.03 * generation - 0.01 * program.execution_cost
                        mids = tuple(sorted((left_id, right_id)))
                        cid = 'rcm:' + _digest('|'.join((connective, *mids, program.probe_id)))
                        candidates.append((
                            -score, -novelty, program.execution_cost, cid,
                            mids, connective, program, info, parent_info, novelty,
                        ))
                    if pair_evaluated >= int(max_composition_candidates):
                        break
                if pair_evaluated >= int(max_composition_candidates):
                    break
            if pair_evaluated >= int(max_composition_candidates):
                break
        if pair_evaluated >= int(max_composition_candidates):
            break

    candidates.sort()
    if not candidates:
        return RecursiveCompositionDecision(
            'abstain', None, (), None, None, 0.0, 0.0, 0.0,
            frontier_evaluations + pair_evaluated, 0, (), 'no_conditionally_novel_composition',
        )
    check = counterexample_check or (lambda program: True)
    rejected = []
    checked = 0
    for _, _, _, cid, mids, connective, program, info, parent_info, novelty in candidates:
        checked += 1
        if not bool(check(program)):
            rejected.append(cid)
            continue
        return RecursiveCompositionDecision(
            'accept', cid, mids, connective, program, info, parent_info, novelty,
            frontier_evaluations + pair_evaluated, checked, tuple(rejected),
            'counterexample_surviving_recursive_composition',
        )
    return RecursiveCompositionDecision(
        'abstain', None, (), None, None, 0.0, 0.0, 0.0,
        frontier_evaluations + pair_evaluated, checked, tuple(rejected),
        'all_recursive_compositions_falsified',
    )


def flat_unique_binding_count(macro: ProbeMacro, atom_count_by_type: Mapping[ProbeType, int]) -> int:
    """Count type-valid unique raw bindings a flat macro enumerator must consider."""
    needed: dict[ProbeType, int] = {}
    for typ in macro.parameter_types:
        needed[typ] = needed.get(typ, 0) + 1
    total = 1
    for typ, arity in needed.items():
        n = int(atom_count_by_type.get(typ, 0))
        if n < arity:
            return 0
        total *= math.perm(n, arity)
    return int(total)
