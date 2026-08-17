from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r219_representation_types import VerifierObservation
from .r220_operator_discovery import initial_proposal_supports, update_proposal_supports
from .r239_predicate_macros import ProbeMacro, instantiate_macro
from .r239_recursive_probe_synthesis import (
    _bool_disagreement,
    _posterior,
    _r238_binary_candidates,
    _simple_predicates,
    synthesize_recursive_typed_probe,
)
from .r239_typed_probe_dsl import ProbeType, TypedProbe, typed_prediction_row


@dataclass(frozen=True)
class RecursiveDiscoveryDecision:
    status: str
    operator_id: str | None
    posterior: float
    margin: float
    queries: tuple[str, ...]
    macro_probe_ids: tuple[str, ...]
    recursive_probe_ids: tuple[str, ...]
    probe_programs: tuple[TypedProbe, ...]
    total_probe_cost: float
    raw_candidates_evaluated: int
    macro_candidates_evaluated: int
    reason: str


def _rank(supports):
    ranked = sorted(supports, key=lambda s: (-s.posterior, s.operator_id))
    top = ranked[0]
    second = ranked[1].posterior if len(ranked) > 1 else 0.0
    return top, top.posterior - second


def _probe_utility(program: TypedProbe, posterior, values, *, effective_mdl: int | None = None) -> tuple[float, float]:
    row = typed_prediction_row(program, values)
    disagreement = _bool_disagreement(row, posterior)
    mdl = program.mdl_cost if effective_mdl is None else int(effective_mdl)
    utility = disagreement - 0.02 * (program.execution_cost - 1.0) - 0.005 * mdl
    return utility, disagreement


def _atom_shortlist(atom_ids: Sequence[str], posterior, values, size: int) -> tuple[str, ...]:
    scores = []
    for qid in sorted({str(v).strip().lower() for v in atom_ids if str(v).strip()}):
        masses = {0: 0.0, 1: 0.0, 2: 0.0}
        for hid, p in posterior.items():
            value = int(values[hid][qid])
            if value not in masses:
                raise ValueError('trit atom value must be 0, 1 or 2')
            masses[value] += p
        gini = 1.0 - sum(v * v for v in masses.values())
        scores.append((-gini, qid))
    return tuple(q for _, q in sorted(scores)[: min(int(size), len(scores))])


def _select_simple_or_binary(mode: str, atom_ids, supports, values, observed, atom_shortlist_size):
    posterior = _posterior(supports)
    shortlist = _atom_shortlist(atom_ids, posterior, values, atom_shortlist_size)
    simple = _simple_predicates(shortlist)
    candidates = simple if mode == 'atomic_only' else _r238_binary_candidates(simple, posterior, values)
    legal = [p for p in candidates if p.probe_id not in observed]
    if not legal:
        return None, 0
    scored = []
    for p in legal:
        utility, disagreement = _probe_utility(p, posterior, values)
        scored.append((-utility, -disagreement, p.mdl_cost, p.probe_id, p))
    return min(scored)[-1], len(legal)


def _select_macro(macros, shortlist, supports, values, observed, max_macro_candidates):
    posterior = _posterior(supports)
    evaluated = 0
    seen_rows: dict[tuple[bool, ...], tuple] = {}
    for macro in sorted(macros, key=lambda m: (-m.compression_gain, m.macro_id)):
        if any(t is not ProbeType.TRIT for t in macro.parameter_types):
            continue
        if macro.arity > len(shortlist):
            continue
        for atom_tuple in itertools.permutations(shortlist, macro.arity):
            if evaluated >= int(max_macro_candidates):
                break
            from .r239_typed_probe_dsl import trit_atom
            program = instantiate_macro(macro, tuple(trit_atom(q) for q in atom_tuple))
            if program.probe_id in observed:
                continue
            row = typed_prediction_row(program, values)
            evaluated += 1
            key = tuple(bool(row[hid]) for hid in posterior)
            utility, disagreement = _probe_utility(program, posterior, values, effective_mdl=macro.call_mdl_cost)
            candidate = (-utility, -disagreement, macro.call_mdl_cost, macro.macro_id, program.probe_id, macro, program)
            current = seen_rows.get(key)
            if current is None or candidate < current:
                seen_rows[key] = candidate
        if evaluated >= int(max_macro_candidates):
            break
    if not seen_rows:
        return None, None, evaluated
    best = min(seen_rows.values())
    return best[-2], best[-1], evaluated


def discover_with_recursive_typed_probes(
    hypotheses,
    trit_atom_ids: Sequence[str],
    atom_values_by_hypothesis: Mapping[str, Mapping[str, int]],
    initial_probes: Sequence[TypedProbe],
    macros: Sequence[ProbeMacro],
    *,
    verifier: Callable[[TypedProbe], VerifierObservation],
    counterexample_check: Callable[[object], bool],
    query_budget: int,
    probe_cost_budget: float,
    accept_probability: float,
    accept_margin: float,
    mode: str,
    atom_shortlist_size: int = 8,
    max_raw_candidates: int = 480,
    max_macro_candidates: int = 160,
    complexity_weight: float = 0.0,
    macro_reuse_bonus_weight: float = 0.005,
) -> RecursiveDiscoveryDecision:
    if mode not in {'recursive_macro', 'recursive_no_macro', 'r238_binary', 'atomic_only'}:
        raise ValueError('unknown recursive discovery mode')
    hypotheses = tuple(hypotheses)
    if not hypotheses:
        raise ValueError('hypotheses must be non-empty')
    ids = {str(h.operator_id) for h in hypotheses}
    if set(atom_values_by_hypothesis) != ids:
        raise ValueError('hypothesis atom-value coverage mismatch')
    if int(query_budget) < 0 or float(probe_cost_budget) < 0:
        raise ValueError('budgets must be non-negative')

    by_hypothesis = {str(h.operator_id): h for h in hypotheses}
    supports = initial_proposal_supports(hypotheses, complexity_weight=float(complexity_weight))
    remaining_initial = list(initial_probes)
    observed: set[str] = set()
    queries: list[str] = []
    macro_ids: list[str] = []
    recursive_ids: list[str] = []
    probe_programs: list[TypedProbe] = []
    total_cost = 0.0
    raw_evals = 0
    macro_evals = 0

    for _ in range(int(query_budget)):
        posterior = _posterior(supports)
        chosen: TypedProbe | None = None
        chosen_macro: ProbeMacro | None = None

        if remaining_initial:
            candidates = [p for p in remaining_initial if p.probe_id not in observed]
            if not candidates:
                remaining_initial = []
                continue
            scored = []
            for p in candidates:
                utility, disagreement = _probe_utility(p, posterior, atom_values_by_hypothesis)
                scored.append((-utility, -disagreement, p.mdl_cost, p.probe_id, p))
            chosen = min(scored)[-1]
            remaining_initial.remove(chosen)
        elif mode in {'atomic_only', 'r238_binary'}:
            chosen, count = _select_simple_or_binary(
                mode, trit_atom_ids, supports, atom_values_by_hypothesis, observed, atom_shortlist_size,
            )
            raw_evals += count
        else:
            raw_budget = int(max_raw_candidates)
            if mode == 'recursive_macro' and macros:
                raw_budget = min(raw_budget, 96)
            raw = synthesize_recursive_typed_probe(
                trit_atom_ids,
                supports,
                atom_values_by_hypothesis,
                observed,
                atom_shortlist_size=atom_shortlist_size,
                max_raw_candidates=raw_budget,
            )
            raw_evals += raw.raw_candidates_evaluated
            chosen = raw.program
            raw_utility, raw_disagreement = _probe_utility(chosen, posterior, atom_values_by_hypothesis)
            if mode == 'recursive_macro' and macros:
                macro, macro_program, evaluated = _select_macro(
                    macros,
                    raw.shortlisted_atoms,
                    supports,
                    atom_values_by_hypothesis,
                    observed,
                    max_macro_candidates,
                )
                macro_evals += evaluated
                if macro is not None and macro_program is not None:
                    macro_utility, macro_disagreement = _probe_utility(
                        macro_program,
                        posterior,
                        atom_values_by_hypothesis,
                        effective_mdl=macro.call_mdl_cost,
                    )
                    macro_utility += float(macro_reuse_bonus_weight) * max(0.0, macro.compression_gain)
                    macro_key = (-macro_utility, -macro_disagreement, macro.call_mdl_cost, macro.macro_id, macro_program.probe_id)
                    raw_key = (-raw_utility, -raw_disagreement, chosen.mdl_cost, '~raw', chosen.probe_id)
                    if macro_key <= raw_key:
                        chosen = macro_program
                        chosen_macro = macro

        if chosen is None:
            break
        if chosen.output_type is not ProbeType.BOOL:
            raise TypeError('verifier probe root must be bool')
        if total_cost + chosen.execution_cost > float(probe_cost_budget) + 1e-12:
            break

        observation = verifier(chosen)
        if observation.query_id != chosen.probe_id:
            raise ValueError('verifier returned wrong probe id')
        row = typed_prediction_row(chosen, atom_values_by_hypothesis)
        supports = update_proposal_supports(hypotheses, supports, observation, row)
        observed.add(chosen.probe_id)
        queries.append(chosen.probe_id)
        probe_programs.append(chosen)
        total_cost += chosen.execution_cost
        if chosen_macro is not None:
            macro_ids.append(chosen.probe_id)
        if chosen.depth >= 3:
            recursive_ids.append(chosen.probe_id)

        top, margin = _rank(supports)
        if top.posterior >= float(accept_probability) and margin >= float(accept_margin):
            hypothesis = by_hypothesis[top.operator_id]
            if counterexample_check(hypothesis):
                return RecursiveDiscoveryDecision(
                    'accept', hypothesis.operator_id, top.posterior, margin, tuple(queries),
                    tuple(macro_ids), tuple(recursive_ids), tuple(probe_programs), total_cost, raw_evals, macro_evals,
                    'supported_hypothesis_survived_counterexample',
                )
            return RecursiveDiscoveryDecision(
                'abstain', None, top.posterior, margin, tuple(queries), tuple(macro_ids), tuple(recursive_ids), tuple(probe_programs),
                total_cost, raw_evals, macro_evals, 'counterexample_rejected_top_hypothesis',
            )

    top, margin = _rank(supports)
    return RecursiveDiscoveryDecision(
        'abstain', None, top.posterior, margin, tuple(queries), tuple(macro_ids), tuple(recursive_ids), tuple(probe_programs),
        total_cost, raw_evals, macro_evals, 'insufficient_identifiability_or_budget',
    )
