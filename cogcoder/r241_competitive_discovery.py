from __future__ import annotations
import itertools
import math
from dataclasses import dataclass, replace
from typing import Callable, Mapping, Sequence
from .r219_representation_types import VerifierObservation
from .r220_operator_discovery import initial_proposal_supports, update_proposal_supports
from .r239_predicate_macros import ProbeMacro, instantiate_macro
from .r239_recursive_discovery import _atom_shortlist, _probe_utility, _rank
from .r239_recursive_probe_synthesis import _posterior, synthesize_recursive_typed_probe
from .r239_typed_probe_dsl import ProbeType, TypedProbe, trit_atom, typed_prediction_row
from .r241_macro_competition import MacroCompetitionEvidence, MacroCompetitionState, assess_competing_macro, update_macro_competition_state

@dataclass(frozen=True)
class CompetitiveRecursiveDecision:
    status: str
    operator_id: str | None
    posterior: float
    margin: float
    queries: tuple[str, ...]
    selected_macro_ids: tuple[str, ...]
    selected_macro_probe_ids: tuple[str, ...]
    raw_probe_ids: tuple[str, ...]
    probe_programs: tuple[TypedProbe, ...]
    total_probe_cost: float
    raw_candidates_evaluated: int
    macro_candidates_evaluated: int
    route_history: tuple[str, ...]
    quarantined_macro_ids: tuple[str, ...]
    macro_state_summaries: tuple[tuple[str, float, float, int, bool], ...]
    reason: str

@dataclass(frozen=True)
class _EvidenceLedgerEntry:
    route: str
    observation: VerifierObservation
    predicted_labels: Mapping[str, bool]

def _predictive_mass(supports, predicted_labels: Mapping[str, bool], observed_label: bool) -> float:
    posterior = _posterior(supports)
    return sum((float(posterior[operator_id]) for operator_id in posterior if bool(predicted_labels[operator_id]) == bool(observed_label)))

def _rebuild_supports(hypotheses, ledger: Sequence[_EvidenceLedgerEntry], *, excluded_macro_ids: frozenset[str]=frozenset()):
    supports = initial_proposal_supports(hypotheses, complexity_weight=0.0)
    for entry in ledger:
        if entry.route in excluded_macro_ids:
            continue
        supports = update_proposal_supports(hypotheses, supports, entry.observation, entry.predicted_labels)
    return supports

def _quarantine_macro_state(state: MacroCompetitionState) -> MacroCompetitionState:
    if state.quarantined:
        return state
    return replace(state, semantic_conflicts=state.semantic_conflicts + 1, shock_count=state.shock_count + 1, quarantined=True)

def _active_macro_ids_in_ledger(ledger: Sequence[_EvidenceLedgerEntry], states: Mapping[str, MacroCompetitionState]) -> tuple[str, ...]:
    return tuple(sorted({entry.route for entry in ledger if entry.route in states and (not states[entry.route].quarantined)}))

def _attribute_surprising_observation(hypotheses, supports, ledger: Sequence[_EvidenceLedgerEntry], states: Mapping[str, MacroCompetitionState], predicted_labels: Mapping[str, bool], observed_label: bool, *, minimum_gain: float=0.2, minimum_margin: float=0.005) -> str | None:
    baseline_mass = _predictive_mass(supports, predicted_labels, observed_label)
    scored = []
    for macro_id in _active_macro_ids_in_ledger(ledger, states):
        rebuilt = _rebuild_supports(hypotheses, ledger, excluded_macro_ids=frozenset((macro_id,)))
        recovered_mass = _predictive_mass(rebuilt, predicted_labels, observed_label)
        gain = recovered_mass - baseline_mass
        scored.append((gain, recovered_mass, macro_id))
    if not scored:
        return None
    scored.sort(key=lambda row: (-row[0], -row[1], row[2]))
    best_gain, _, best_macro = scored[0]
    second_gain = scored[1][0] if len(scored) > 1 else 0.0
    if best_gain < float(minimum_gain):
        return None
    if best_gain - second_gain < float(minimum_margin):
        return None
    return best_macro

def _attribute_rejected_top(hypotheses, supports, ledger: Sequence[_EvidenceLedgerEntry], states: Mapping[str, MacroCompetitionState], rejected_operator_id: str, *, minimum_drop: float=0.2, minimum_margin: float=0.05) -> str | None:
    baseline = _posterior(supports).get(str(rejected_operator_id), 0.0)
    scored = []
    for macro_id in _active_macro_ids_in_ledger(ledger, states):
        rebuilt = _rebuild_supports(hypotheses, ledger, excluded_macro_ids=frozenset((macro_id,)))
        rejected_mass = _posterior(rebuilt).get(str(rejected_operator_id), 0.0)
        drop = float(baseline) - float(rejected_mass)
        scored.append((drop, rejected_mass, macro_id))
    if not scored:
        return None
    scored.sort(key=lambda row: (-row[0], row[1], row[2]))
    best_drop, _, best_macro = scored[0]
    second_drop = scored[1][0] if len(scored) > 1 else 0.0
    if best_drop < float(minimum_drop):
        return None
    if best_drop - second_drop < float(minimum_margin):
        return None
    return best_macro

def _entropy(posterior: Mapping[str, float]) -> float:
    vals = [float(p) for p in posterior.values() if p > 0.0]
    if len(vals) <= 1:
        return 0.0
    h = -sum((p * math.log(p) for p in vals))
    return max(0.0, min(1.0, h / math.log(len(vals))))

def _row_agreement(a: TypedProbe, b: TypedProbe, posterior, values) -> float:
    ra = typed_prediction_row(a, values)
    rb = typed_prediction_row(b, values)
    return sum((float(posterior[h]) for h in posterior if bool(ra[h]) == bool(rb[h])))

def _best_candidates_by_macro(macros: Sequence[ProbeMacro], shortlist: Sequence[str], posterior: Mapping[str, float], values, observed: set[str], states: Mapping[str, MacroCompetitionState], *, budget: int, raw_program: TypedProbe, last_reliability: float, competition_threshold: float, macro_reuse_bonus_weight: float):
    rows = []
    evaluated = 0
    raw_u, raw_d = _probe_utility(raw_program, posterior, values)
    entropy = _entropy(posterior)
    active = [m for m in sorted(macros, key=lambda m: (-m.compression_gain, m.macro_id)) if not states[m.macro_id].quarantined and all((t is ProbeType.TRIT for t in m.parameter_types)) and (m.arity <= len(shortlist))]
    if not active:
        return (rows, evaluated, raw_u, raw_d)
    per_macro_quota = max(1, int(budget) // len(active))
    leftover = max(0, int(budget) - per_macro_quota * len(active))
    for index, macro in enumerate(active):
        state = states[macro.macro_id]
        best = None
        seen_semantics = set()
        macro_quota = per_macro_quota + (1 if index < leftover else 0)
        macro_evaluated = 0
        for atom_tuple in itertools.permutations(shortlist, macro.arity):
            if evaluated >= budget or macro_evaluated >= macro_quota:
                break
            program = instantiate_macro(macro, tuple((trit_atom(q) for q in atom_tuple)))
            if program.probe_id in observed:
                continue
            row = typed_prediction_row(program, values)
            semantic_key = tuple((bool(row[h]) for h in posterior))
            if semantic_key in seen_semantics:
                continue
            seen_semantics.add(semantic_key)
            evaluated += 1
            macro_evaluated += 1
            utility, disagreement = _probe_utility(program, posterior, values, effective_mdl=macro.call_mdl_cost)
            evidence = MacroCompetitionEvidence(reported_reliability=max(0.500001, min(1.0, float(last_reliability))), semantic_alignment=state.semantic_alignment, prediction_stability=_row_agreement(program, raw_program, posterior, values), posterior_entropy=entropy, posterior_margin=_rank_from_posterior(posterior)[1], information_gain=disagreement, relative_cost=min(1.0, program.execution_cost / max(program.execution_cost, raw_program.execution_cost)), counterexample_survival=None)
            assessment = assess_competing_macro(state, evidence, threshold=competition_threshold)
            if assessment.route != 'macro':
                continue
            score = utility + float(macro_reuse_bonus_weight) * max(0.0, macro.compression_gain) + 0.1 * (assessment.lower_confidence_bound - float(competition_threshold)) + 0.03 * state.semantic_alignment - 0.01 * len(state.information_gain_history)
            candidate = (-score, -disagreement, macro.call_mdl_cost, macro.macro_id, program.probe_id, macro, program, assessment)
            if best is None or candidate < best:
                best = candidate
        if best is not None:
            rows.append(best)
        if evaluated >= budget:
            break
    rows.sort()
    return (rows, evaluated, raw_u, raw_d)

def _rank_from_posterior(posterior: Mapping[str, float]):
    ranked = sorted(posterior.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    return (top, float(top[1]) - float(second))

def _summary(states: Mapping[str, MacroCompetitionState]):
    return tuple(((mid, state.alpha, state.beta, state.semantic_conflicts, state.quarantined) for mid, state in sorted(states.items())))

def discover_with_competing_macros(hypotheses, trit_atom_ids: Sequence[str], atom_values_by_hypothesis: Mapping[str, Mapping[str, int]], initial_probes: Sequence[TypedProbe], macros: Sequence[ProbeMacro], *, verifier: Callable[[TypedProbe], VerifierObservation], counterexample_check: Callable[[object], bool], query_budget: int, probe_cost_budget: float, accept_probability: float, accept_margin: float, atom_shortlist_size: int=8, max_raw_candidates: int=480, max_macro_candidates: int=160, macro_candidates_per_step: int=32, competition_threshold: float=0.55, macro_margin_over_raw: float=0.0, macro_reuse_bonus_weight: float=0.005, enable_macro_calibration: bool=True) -> CompetitiveRecursiveDecision:
    hypotheses = tuple(hypotheses)
    macros = tuple(macros)
    if not hypotheses:
        raise ValueError('hypotheses must be non-empty')
    if len({m.macro_id for m in macros}) != len(macros):
        raise ValueError('macro ids must be unique')
    by_hypothesis = {str(h.operator_id): h for h in hypotheses}
    if set(atom_values_by_hypothesis) != set(by_hypothesis):
        raise ValueError('hypothesis atom-value coverage mismatch')
    if int(query_budget) < 0 or float(probe_cost_budget) < 0:
        raise ValueError('budgets must be non-negative')
    if int(macro_candidates_per_step) <= 0:
        raise ValueError('macro_candidates_per_step must be positive')
    supports = initial_proposal_supports(hypotheses, complexity_weight=0.0)
    states = {m.macro_id: MacroCompetitionState(m.macro_id, alpha=8.0, beta=2.0, semantic_alignment=0.75) for m in macros}
    remaining_initial = list(initial_probes)
    observed: set[str] = set()
    queries: list[str] = []
    selected_macro_ids: list[str] = []
    selected_macro_probe_ids: list[str] = []
    raw_probe_ids: list[str] = []
    programs: list[TypedProbe] = []
    route_history: list[str] = []
    total_cost = 0.0
    raw_evals = 0
    macro_evals = 0
    last_reliability = 0.95
    ledger: list[_EvidenceLedgerEntry] = []
    for step_index in range(int(query_budget)):
        posterior = _posterior(supports)
        chosen = None
        chosen_macro = None
        raw_program = None
        pre_entropy = _entropy(posterior)
        if remaining_initial:
            legal = [p for p in remaining_initial if p.probe_id not in observed]
            if not legal:
                remaining_initial = []
                continue
            scored = []
            for p in legal:
                utility, disagreement = _probe_utility(p, posterior, atom_values_by_hypothesis)
                scored.append((-utility, -disagreement, p.mdl_cost, p.probe_id, p))
            chosen = min(scored)[-1]
            remaining_initial.remove(chosen)
        else:
            raw = synthesize_recursive_typed_probe(trit_atom_ids, supports, atom_values_by_hypothesis, observed, atom_shortlist_size=atom_shortlist_size, max_raw_candidates=int(max_raw_candidates))
            raw_evals += raw.raw_candidates_evaluated
            raw_program = raw.program
            chosen = raw_program
            raw_u, _ = _probe_utility(raw_program, posterior, atom_values_by_hypothesis)
            remaining_macro_budget = max(0, int(max_macro_candidates) - macro_evals)
            step_macro_budget = min(remaining_macro_budget, int(macro_candidates_per_step)) if remaining_macro_budget else 0
            candidates = []
            if step_macro_budget and macros:
                candidates, evaluated, _, _ = _best_candidates_by_macro(macros, raw.shortlisted_atoms, posterior, atom_values_by_hypothesis, observed, states, budget=step_macro_budget, raw_program=raw_program, last_reliability=last_reliability, competition_threshold=competition_threshold, macro_reuse_bonus_weight=macro_reuse_bonus_weight)
                macro_evals += evaluated
            if candidates:
                best = candidates[0]
                best_score = -best[0]
                if best_score >= raw_u + float(macro_margin_over_raw):
                    chosen_macro = best[-3]
                    chosen = best[-2]
                    route_history.append(chosen_macro.macro_id)
                else:
                    route_history.append('raw')
            else:
                route_history.append('raw')
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
        semantic_alignment = sum((float(posterior[hid]) for hid in posterior if bool(row[hid]) == bool(observation.observed_label)))
        if observation.reliability >= 0.9 and semantic_alignment <= 0.2 and ledger and enable_macro_calibration and (not any((state.quarantined for state in states.values()))):
            culprit = _attribute_surprising_observation(hypotheses, supports, ledger, states, row, observation.observed_label)
            if culprit is not None:
                states[culprit] = _quarantine_macro_state(states[culprit])
                excluded = frozenset((mid for mid, state in states.items() if state.quarantined))
                supports = _rebuild_supports(hypotheses, ledger, excluded_macro_ids=excluded)
                posterior = _posterior(supports)
                pre_entropy = _entropy(posterior)
                semantic_alignment = sum((float(posterior[hid]) for hid in posterior if bool(row[hid]) == bool(observation.observed_label)))
        supports = update_proposal_supports(hypotheses, supports, observation, row)
        post_posterior = _posterior(supports)
        info_gain = max(0.0, pre_entropy - _entropy(post_posterior))
        observed.add(chosen.probe_id)
        queries.append(chosen.probe_id)
        programs.append(chosen)
        total_cost += chosen.execution_cost
        last_reliability = observation.reliability
        if chosen_macro is not None:
            selected_macro_ids.append(chosen_macro.macro_id)
            selected_macro_probe_ids.append(chosen.probe_id)
            state = states[chosen_macro.macro_id]
            evidence = MacroCompetitionEvidence(reported_reliability=observation.reliability, semantic_alignment=semantic_alignment, prediction_stability=semantic_alignment, posterior_entropy=pre_entropy, posterior_margin=_rank_from_posterior(posterior)[1], information_gain=info_gain, relative_cost=min(1.0, chosen.execution_cost / max(float(probe_cost_budget), 1e-12)), counterexample_survival=None)
            if enable_macro_calibration:
                states[chosen_macro.macro_id] = update_macro_competition_state(state, evidence)
        elif raw_program is not None:
            raw_probe_ids.append(chosen.probe_id)
        ledger_route = chosen_macro.macro_id if chosen_macro is not None else 'raw' if raw_program is not None else 'initial'
        ledger.append(_EvidenceLedgerEntry(ledger_route, observation, row))
        top, margin = _rank(supports)
        if top.posterior >= float(accept_probability) and margin >= float(accept_margin):
            h = by_hypothesis[top.operator_id]
            if counterexample_check(h):
                return CompetitiveRecursiveDecision('accept', h.operator_id, top.posterior, margin, tuple(queries), tuple(selected_macro_ids), tuple(selected_macro_probe_ids), tuple(raw_probe_ids), tuple(programs), total_cost, raw_evals, macro_evals, tuple(route_history), tuple(sorted((mid for mid, s in states.items() if s.quarantined))), _summary(states), 'supported_hypothesis_survived_counterexample')
            culprit = None
            if enable_macro_calibration and (not any((state.quarantined for state in states.values()))):
                culprit = _attribute_rejected_top(hypotheses, supports, ledger, states, top.operator_id)
            if culprit is not None:
                states[culprit] = _quarantine_macro_state(states[culprit])
                excluded = frozenset((mid for mid, state in states.items() if state.quarantined))
                supports = _rebuild_supports(hypotheses, ledger, excluded_macro_ids=excluded)
                continue
            return CompetitiveRecursiveDecision('abstain', None, top.posterior, margin, tuple(queries), tuple(selected_macro_ids), tuple(selected_macro_probe_ids), tuple(raw_probe_ids), tuple(programs), total_cost, raw_evals, macro_evals, tuple(route_history), tuple(sorted((mid for mid, s in states.items() if s.quarantined))), _summary(states), 'counterexample_rejected_top_hypothesis')
    top, margin = _rank(supports)
    return CompetitiveRecursiveDecision('abstain', None, top.posterior, margin, tuple(queries), tuple(selected_macro_ids), tuple(selected_macro_probe_ids), tuple(raw_probe_ids), tuple(programs), total_cost, raw_evals, macro_evals, tuple(route_history), tuple(sorted((mid for mid, s in states.items() if s.quarantined))), _summary(states), 'insufficient_identifiability_or_budget')
