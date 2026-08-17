from __future__ import annotations
import hashlib
import itertools
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping
from cogcoder.r219_representation_types import VerifierObservation
from cogcoder.r220_operator_discovery import initial_proposal_supports, update_proposal_supports
from cogcoder.r239_predicate_macros import ProbeMacro, induce_probe_macros
from cogcoder.r239_recursive_discovery import discover_with_recursive_typed_probes
from cogcoder.r239_recursive_probe_synthesis import synthesize_recursive_typed_probe
from cogcoder.r239_typed_probe_dsl import TypedProbe, const3, eq_probe, evaluate_typed_probe, trit_atom, typed_prediction_row
from cogcoder.r241_competitive_discovery import discover_with_competing_macros
FAMILY = 'z3_dual_semantic'
MACRO_TRAIN_SEEDS = (811, 821, 823, 827, 829, 839)
DEV_SEEDS = (853, 857, 859)
DEV_REGIMES = ('multi_clean', 'semantic_shift')
HELDOUT_SEEDS = (881, 883, 887)
HELDOUT_REGIMES = ('held_clean', 'held_semantic_shift')
MODES = ('competitive_calibrated', 'single_best_macro', 'unconditional_multi_macro', 'no_macro', 'r238_binary')
HYPOTHESIS_COUNT = 16
INITIAL_PROBE_COUNT = 1
QUERY_BUDGET = 7
PROBE_COST_BUDGET = 15.0
ACCEPT_PROBABILITY = 0.94
ACCEPT_MARGIN = 0.7
ATOM_SHORTLIST_SIZE = 8
MAX_RAW_CANDIDATES = 480
MAX_MACRO_CANDIDATES = 160
COMPETITION_THRESHOLD = 0.55
MACRO_MARGIN_OVER_RAW = 0.06

@dataclass(frozen=True)
class DualSemanticHypothesis:
    operator_id: str
    mdl_cost: int = 1

def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def _states():
    return tuple(itertools.product((0, 1, 2), repeat=2))

def _atom_id(state, coord: int) -> str:
    return f'r241:z3:{state[0]}{state[1]}:y{int(coord)}'

def _transition(params, state):
    a, b, c, d, e, f, g, h = params
    x0, x1 = state
    cross = x0 * x1 % 3
    cross_sum = (x0 + x1) % 3
    return ((a * x0 + b * x1 + c + g * cross) % 3, (d * x0 + e * x1 + f + h * cross_sum) % 3)

@lru_cache(maxsize=1)
def _prepared():
    rows = []
    seen = set()
    states = _states()
    for params in itertools.product((0, 1, 2), repeat=8):
        a, b, _, d, e, _, g, h = params
        if (a, b) == (0, 0) or (d, e) == (0, 0) or (g, h) == (0, 0):
            continue
        signature = tuple((v for state in states for v in _transition(params, state)))
        if signature in seen:
            continue
        seen.add(signature)
        rows.append((_digest(f'r241-family:{params}'), tuple(params), signature))
    rows.sort(key=lambda row: (row[0], row[1]))
    params_rows = tuple((params for _, params, _ in rows[:HYPOTHESIS_COUNT]))
    atom_ids = tuple((_atom_id(state, coord) for state in states for coord in range(2)))
    hypotheses = []
    values = {}
    for params in params_rows:
        hid = 'r241h:' + _digest(f'{FAMILY}:{params}')[:20]
        hypotheses.append(DualSemanticHypothesis(hid))
        row = {}
        for state in states:
            after = _transition(params, state)
            row[_atom_id(state, 0)] = after[0]
            row[_atom_id(state, 1)] = after[1]
        values[hid] = row
    return (tuple(hypotheses), atom_ids, values)

def _target(episode_key: int):
    hypotheses, _, values = _prepared()
    idx = int(_digest(f'r241-target:{int(episode_key)}')[:16], 16) % len(hypotheses)
    target = hypotheses[idx]
    signature = tuple((values[target.operator_id][key] for key in sorted(values[target.operator_id])))
    equivalent = frozenset((h.operator_id for h in hypotheses if tuple((values[h.operator_id][key] for key in sorted(values[h.operator_id]))) == signature))
    return (target.operator_id, equivalent)

def _initial_probes(episode_key: int, regime: str):
    _, atom_ids, _ = _prepared()
    probes = [eq_probe(trit_atom(qid), const3(value)) for qid in atom_ids for value in (0, 1, 2)]
    ranked = sorted(probes, key=lambda p: (_digest(f'r241-pool:{int(episode_key)}:{regime}:{p.probe_id}'), p.probe_id))
    return tuple(ranked[:INITIAL_PROBE_COUNT])

def _shift_sensitive(program: TypedProbe) -> bool:
    if program.depth < 3 or program.op != 'eq':
        return False
    children = tuple((c for c in (program.left, program.right) if c is not None))
    if len(children) != 2:
        return False
    add_children = [child for child in children if child.op == 'add3']
    peer_children = [child for child in children if child.op != 'add3']
    return len(add_children) == 1 and len(peer_children) == 1 and (peer_children[0].op == 'const3') and (int(peer_children[0].const_value) == 1)

def _heldout_shift_sensitive(program: TypedProbe) -> bool:
    if program.depth < 3 or program.op != 'neq':
        return False
    children = tuple((c for c in (program.left, program.right) if c is not None))
    if len(children) != 2:
        return False
    add_children = [child for child in children if child.op == 'add3']
    peer_children = [child for child in children if child.op != 'add3']
    return len(add_children) == 1 and len(peer_children) == 1 and (peer_children[0].op == 'const3') and (int(peer_children[0].const_value) == 2)

def _observation(episode_key: int, regime: str, program: TypedProbe, truth: bool):
    if regime == 'multi_clean':
        return (VerifierObservation(program.probe_id, bool(truth), 0.995), False)
    if regime == 'semantic_shift':
        flip = _shift_sensitive(program)
        return (VerifierObservation(program.probe_id, not bool(truth) if flip else bool(truth), 0.97), bool(flip))
    if regime == 'held_clean':
        return (VerifierObservation(program.probe_id, bool(truth), 0.992), False)
    if regime == 'held_semantic_shift':
        flip = _heldout_shift_sensitive(program)
        return (VerifierObservation(program.probe_id, not bool(truth) if flip else bool(truth), 0.965), bool(flip))
    raise ValueError('unknown R2.41 verifier regime')

def _macro_training_programs(seed: int):
    hypotheses, atom_ids, values = _prepared()
    target, _ = _target(seed)
    supports = initial_proposal_supports(hypotheses, complexity_weight=0.0)
    observed: set[str] = set()
    programs = []
    for initial_probe in _initial_probes(seed, 'multi_clean'):
        mining_blocked = set(observed)
        for _ in range(10):
            receipt = synthesize_recursive_typed_probe(atom_ids, supports, values, mining_blocked, atom_shortlist_size=ATOM_SHORTLIST_SIZE, max_raw_candidates=MAX_RAW_CANDIDATES)
            program = receipt.best_recursive_program
            programs.append(program)
            mining_blocked.add(program.probe_id)
        truth = bool(evaluate_typed_probe(initial_probe, values[target]))
        obs, _ = _observation(seed, 'multi_clean', initial_probe, truth)
        supports = update_proposal_supports(hypotheses, supports, obs, typed_prediction_row(initial_probe, values))
        observed.add(initial_probe.probe_id)
    return tuple(programs)

@lru_cache(maxsize=1)
def learn_r241_macro_library() -> tuple[ProbeMacro, ...]:
    episode_programs = {f'r241-train-{seed}': _macro_training_programs(seed) for seed in MACRO_TRAIN_SEEDS}
    return induce_probe_macros(episode_programs, min_support=2, max_macros=6)

def _public_competitive(mode: str, decision, equivalent, reliabilities, flips):
    correct = decision.status == 'accept' and decision.operator_id in equivalent
    false_accept = decision.status == 'accept' and decision.operator_id not in equivalent
    return {'mode': mode, 'status': decision.status, 'correct': bool(correct), 'false_accept': bool(false_accept), 'queries_used': len(decision.queries), 'total_probe_cost': decision.total_probe_cost, 'selected_macro_ids': list(decision.selected_macro_ids), 'route_history': list(decision.route_history), 'quarantined_macro_ids': list(decision.quarantined_macro_ids), 'raw_route_count': sum((route == 'raw' for route in decision.route_history)), 'raw_candidates_evaluated': decision.raw_candidates_evaluated, 'macro_candidates_evaluated': decision.macro_candidates_evaluated, 'reported_reliabilities': list(reliabilities), 'semantic_shift_flip_count': int(sum(flips))}

def _public_parent(mode: str, decision, equivalent, reliabilities, flips):
    correct = decision.status == 'accept' and decision.operator_id in equivalent
    false_accept = decision.status == 'accept' and decision.operator_id not in equivalent
    return {'mode': mode, 'status': decision.status, 'correct': bool(correct), 'false_accept': bool(false_accept), 'queries_used': len(decision.queries), 'total_probe_cost': decision.total_probe_cost, 'selected_macro_ids': [], 'route_history': [], 'quarantined_macro_ids': [], 'raw_route_count': 0, 'raw_candidates_evaluated': decision.raw_candidates_evaluated, 'macro_candidates_evaluated': decision.macro_candidates_evaluated, 'reported_reliabilities': list(reliabilities), 'semantic_shift_flip_count': int(sum(flips))}

def _run_episode(seed: int, regime: str, mode: str, *, allowed_seeds, allowed_regimes):
    seed = int(seed)
    if seed not in tuple(allowed_seeds):
        raise ValueError('R2.41 episode seed is outside the requested frozen block')
    if regime not in tuple(allowed_regimes):
        raise ValueError('unknown R2.41 episode regime')
    if mode not in MODES:
        raise ValueError('unknown R2.41 mode')
    hypotheses, atoms, values = _prepared()
    target, equivalent = _target(seed)
    target_values = values[target]
    macros = learn_r241_macro_library()
    reliabilities = []
    flips = []
    def verifier(program):
        truth = bool(evaluate_typed_probe(program, target_values))
        observation, flipped = _observation(seed, regime, program, truth)
        reliabilities.append(observation.reliability)
        flips.append(bool(flipped))
        return observation
    common = dict(verifier=verifier, counterexample_check=lambda h: h.operator_id in equivalent, query_budget=QUERY_BUDGET, probe_cost_budget=PROBE_COST_BUDGET, accept_probability=ACCEPT_PROBABILITY, accept_margin=ACCEPT_MARGIN, atom_shortlist_size=ATOM_SHORTLIST_SIZE, max_raw_candidates=MAX_RAW_CANDIDATES, max_macro_candidates=MAX_MACRO_CANDIDATES)
    initial = _initial_probes(seed, regime)
    if mode == 'competitive_calibrated':
        decision = discover_with_competing_macros(hypotheses, atoms, values, initial, macros, competition_threshold=COMPETITION_THRESHOLD, macro_margin_over_raw=MACRO_MARGIN_OVER_RAW, **common)
        public = _public_competitive(mode, decision, equivalent, reliabilities, flips)
    elif mode == 'single_best_macro':
        decision = discover_with_competing_macros(hypotheses, atoms, values, initial, macros[:1], competition_threshold=COMPETITION_THRESHOLD, macro_margin_over_raw=MACRO_MARGIN_OVER_RAW, **common)
        public = _public_competitive(mode, decision, equivalent, reliabilities, flips)
    elif mode == 'unconditional_multi_macro':
        decision = discover_with_competing_macros(hypotheses, atoms, values, initial, macros, competition_threshold=0.0, macro_margin_over_raw=MACRO_MARGIN_OVER_RAW, enable_macro_calibration=False, **common)
        public = _public_competitive(mode, decision, equivalent, reliabilities, flips)
    else:
        parent_mode = {'no_macro': 'recursive_no_macro', 'r238_binary': 'r238_binary'}[mode]
        decision = discover_with_recursive_typed_probes(hypotheses, atoms, values, initial, (), mode=parent_mode, complexity_weight=0.0, **common)
        public = _public_parent(mode, decision, equivalent, reliabilities, flips)
    row = {'schema_version': 1, 'milestone': 'R2.41 Multi-Macro Competition + Semantic Shift Detection', 'family': FAMILY, 'episode_key': seed, 'regime': regime, 'query_budget': QUERY_BUDGET, 'probe_cost_budget': PROBE_COST_BUDGET}
    row.update(public)
    return row

def run_dev_episode(seed: int, regime: str, mode: str):
    return _run_episode(seed, regime, mode, allowed_seeds=DEV_SEEDS, allowed_regimes=DEV_REGIMES)

def run_heldout_episode(seed: int, regime: str, mode: str):
    return _run_episode(seed, regime, mode, allowed_seeds=HELDOUT_SEEDS, allowed_regimes=HELDOUT_REGIMES)

def _summary(rows):
    out = {'episodes_per_mode': len(DEV_SEEDS) * len(DEV_REGIMES)}
    for mode in MODES:
        subset = [r for r in rows if r['mode'] == mode]
        out[f'{mode}_correct'] = sum((r['correct'] for r in subset))
        out[f'{mode}_mean_probe_cost'] = sum((r['total_probe_cost'] for r in subset)) / len(subset)
    competitive = [r for r in rows if r['mode'] == 'competitive_calibrated']
    shifted = [r for r in competitive if r['regime'] == 'semantic_shift']
    out['false_accepts'] = sum((r['false_accept'] for r in rows))
    out['competitive_macro_ids'] = sorted({mid for r in competitive for mid in r['selected_macro_ids']})
    out['competitive_raw_route_count'] = sum((r['raw_route_count'] for r in competitive))
    out['selective_demotion_episodes'] = sum((len(r['quarantined_macro_ids']) == 1 for r in shifted))
    out['peer_preservation_episodes'] = sum((len(r['quarantined_macro_ids']) == 1 and bool(set(r['selected_macro_ids']) - set(r['quarantined_macro_ids'])) for r in shifted))
    out['semantic_shift_reported_reliabilities'] = [x for r in shifted for x in r['reported_reliabilities']]
    out['semantic_shift_flip_count'] = sum((r['semantic_shift_flip_count'] for r in shifted))
    return out

@lru_cache(maxsize=1)
def run_dev_matrix():
    rows = []
    for regime in DEV_REGIMES:
        for seed in DEV_SEEDS:
            for mode in MODES:
                rows.append(run_dev_episode(seed, regime, mode))
    summary = _summary(rows)
    comp_correct = summary['competitive_calibrated_correct']
    single_correct = summary['single_best_macro_correct']
    unconditional_correct = summary['unconditional_multi_macro_correct']
    comp_cost = summary['competitive_calibrated_mean_probe_cost']
    single_cost = summary['single_best_macro_mean_probe_cost']
    unconditional_cost = summary['unconditional_multi_macro_mean_probe_cost']
    strict_gain = comp_correct > min(single_correct, unconditional_correct) or (comp_correct >= max(single_correct, unconditional_correct) and comp_cost < max(single_cost, unconditional_cost) - 1e-12)
    gates = {'learned_multiple_macros': len(learn_r241_macro_library()) >= 2, 'competitive_all_correct': comp_correct == summary['episodes_per_mode'], 'zero_false_accepts': summary['false_accepts'] == 0, 'strict_gain_over_single_or_unconditional': strict_gain, 'not_worse_than_no_macro': comp_correct >= summary['no_macro_correct'], 'multiple_macros_exercised': len(summary['competitive_macro_ids']) >= 2, 'raw_fallback_exercised': summary['competitive_raw_route_count'] > 0, 'selective_semantic_demotion': summary['selective_demotion_episodes'] > 0, 'peer_preserved': summary['peer_preservation_episodes'] > 0, 'high_reliability_shift': bool(summary['semantic_shift_reported_reliabilities']) and min(summary['semantic_shift_reported_reliabilities']) >= 0.95 and (summary['semantic_shift_flip_count'] > 0), 'same_budgets': all((r['query_budget'] == QUERY_BUDGET and r['probe_cost_budget'] == PROBE_COST_BUDGET for r in rows))}
    return {'schema_version': 1, 'milestone': 'R2.41 Multi-Macro Competition + Semantic Shift Detection', 'family': FAMILY, 'train_seeds': list(MACRO_TRAIN_SEEDS), 'dev_seeds': list(DEV_SEEDS), 'regimes': list(DEV_REGIMES), 'rows': rows, 'summary': summary, 'gates': gates, 'all_gates_pass': all(gates.values())}

def macro_library_payload():
    return {'schema_version': 1, 'milestone': 'R2.41 Multi-Macro Competition + Semantic Shift Detection', 'family': FAMILY, 'train_seeds': list(MACRO_TRAIN_SEEDS), 'macros': [{'macro_id': m.macro_id, 'template_probe_id': m.template.probe_id, 'template_op': m.template.op, 'support': m.support, 'compression_gain': m.compression_gain, 'arity': m.arity, 'raw_mdl_cost': m.raw_mdl_cost, 'call_mdl_cost': m.call_mdl_cost, 'parameter_types': [t.value for t in m.parameter_types]} for m in learn_r241_macro_library()]}
