from __future__ import annotations

import hashlib
from functools import lru_cache

from cogcoder.r219_representation_types import VerifierObservation
from cogcoder.r239_recursive_discovery import discover_with_recursive_typed_probes
from cogcoder.r239_typed_probe_dsl import evaluate_typed_probe
from cogcoder.r240_calibrated_discovery import discover_with_calibrated_macro_applicability
from benchmarks.kfigg import r239_recursive_typed_probe_dsl as parent

DEV_SEEDS=(701,709,719,727,733,739)
DEV_REGIMES=('cal_clean','cal_shift')
MODES=('calibrated','unconditional_macro','no_macro','r238_binary')
FAMILY='z3_bilinear_asym'
APPLICABILITY_THRESHOLD=.60


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _observation(seed: int, regime: str, program, truth: bool) -> VerifierObservation:
    if regime not in DEV_REGIMES:
        raise ValueError('unknown R2.40 development regime')
    if regime=='cal_clean':
        return VerifierObservation(program.probe_id,bool(truth),.99)
    draw=int(_digest(f'r240-dev:{int(seed)}:{program.probe_id}')[:8],16)
    if draw%17==0:
        return VerifierObservation(program.probe_id,not bool(truth),.58)
    return VerifierObservation(program.probe_id,bool(truth),.97)


def _public_decision(mode, decision, equivalent):
    correct=decision.status=='accept' and decision.operator_id in equivalent
    false_accept=decision.status=='accept' and decision.operator_id not in equivalent
    row={
        'mode':mode,'status':decision.status,'correct':bool(correct),'false_accept':bool(false_accept),
        'queries_used':len(decision.queries),'total_probe_cost':decision.total_probe_cost,
        'macro_probe_count':len(decision.macro_probe_ids),
        'raw_candidates_evaluated':decision.raw_candidates_evaluated,
        'macro_candidates_evaluated':decision.macro_candidates_evaluated,
    }
    if mode=='calibrated':
        row['applicability_routes']=list(decision.applicability_routes)
        row['applicability_lcbs']=list(decision.applicability_lcbs)
        row['observed_reliabilities']=list(decision.observed_reliabilities)
    return row


def run_episode(seed: int, regime: str, mode: str):
    seed=int(seed)
    if regime not in DEV_REGIMES:
        raise ValueError('unknown R2.40 development regime')
    if mode not in MODES:
        raise ValueError('unknown R2.40 mode')
    hypotheses,atoms,values=parent._prepared(FAMILY)
    target,equivalent=parent._target(FAMILY,seed)
    target_values=values[target]
    macros=parent.learn_macro_library()
    def verifier(program):
        truth=evaluate_typed_probe(program,target_values)
        return _observation(seed,regime,program,bool(truth))
    common=dict(
        verifier=verifier,counterexample_check=lambda h:h.operator_id in equivalent,
        query_budget=parent.QUERY_BUDGET,probe_cost_budget=parent.PROBE_COST_BUDGET,
        accept_probability=parent.ACCEPT_PROBABILITY,accept_margin=parent.ACCEPT_MARGIN,
        atom_shortlist_size=parent.ATOM_SHORTLIST_SIZE,max_raw_candidates=parent.MAX_RAW_CANDIDATES,
        max_macro_candidates=parent.MAX_MACRO_CANDIDATES,
    )
    initial=parent._initial_probes(FAMILY,seed,'clean')
    if mode=='calibrated':
        decision=discover_with_calibrated_macro_applicability(
            hypotheses,atoms,values,initial,macros,
            applicability_threshold=APPLICABILITY_THRESHOLD,**common,
        )
    else:
        p_mode={'unconditional_macro':'recursive_macro','no_macro':'recursive_no_macro','r238_binary':'r238_binary'}[mode]
        decision=discover_with_recursive_typed_probes(
            hypotheses,atoms,values,initial,macros if p_mode=='recursive_macro' else (),
            mode=p_mode,complexity_weight=0.0,**common,
        )
    row={'schema_version':1,'milestone':'R2.40 Uncertainty-Aware Macro Applicability Calibration','family':FAMILY,'episode_key':seed,'regime':regime}
    row.update(_public_decision(mode,decision,equivalent))
    return row


def _summary(rows):
    out={'episodes_per_mode':len(DEV_SEEDS)*len(DEV_REGIMES)}
    for mode in MODES:
        subset=[r for r in rows if r['mode']==mode]
        out[f'{mode}_correct']=sum(r['correct'] for r in subset)
        out[f'{mode}_mean_probe_cost']=sum(r['total_probe_cost'] for r in subset)/len(subset)
    out['false_accepts']=sum(r['false_accept'] for r in rows)
    calibrated=[r for r in rows if r['mode']=='calibrated']
    routes=[x for r in calibrated for x in r['applicability_routes']]
    out['macro_route_count']=sum(x=='macro' for x in routes)
    out['defer_route_count']=sum(x=='defer_raw' for x in routes)
    out['fully_deferred_episodes']=sum(bool(r['applicability_routes']) and all(x=='defer_raw' for x in r['applicability_routes']) for r in calibrated)
    return out


@lru_cache(maxsize=1)
def run_dev_matrix():
    rows=[]
    for regime in DEV_REGIMES:
        for seed in DEV_SEEDS:
            for mode in MODES:
                rows.append(run_episode(seed,regime,mode))
    summary=_summary(rows)
    gates={
        'calibrated_all_correct':summary['calibrated_correct']==summary['episodes_per_mode'],
        'zero_false_accepts':summary['false_accepts']==0,
        'strict_gain_over_unconditional_macro':summary['calibrated_correct']>summary['unconditional_macro_correct'] or (summary['calibrated_correct']==summary['unconditional_macro_correct'] and summary['calibrated_mean_probe_cost']<summary['unconditional_macro_mean_probe_cost']),
        'not_worse_than_no_macro':summary['calibrated_correct']>=summary['no_macro_correct'],
        'macro_exercised':summary['macro_route_count']>0,
        'deferral_exercised':summary['defer_route_count']>0 and summary['fully_deferred_episodes']>0,
        'same_budgets':all(r['queries_used']<=parent.QUERY_BUDGET and r['total_probe_cost']<=parent.PROBE_COST_BUDGET+1e-12 for r in rows),
    }
    return {'schema_version':1,'milestone':'R2.40 Uncertainty-Aware Macro Applicability Calibration','family':FAMILY,'seeds':list(DEV_SEEDS),'regimes':list(DEV_REGIMES),'rows':rows,'summary':summary,'gates':gates,'all_gates_pass':all(gates.values())}

HELDOUT_REGIMES=('app_clean','app_shift')

def _held_observation(seed: int, regime: str, program, truth: bool) -> VerifierObservation:
    if regime not in HELDOUT_REGIMES:
        raise ValueError('unknown R2.40 heldout regime')
    if regime=='app_clean':
        return VerifierObservation(program.probe_id,bool(truth),.991)
    draw=int(_digest(f'r240-held:{int(seed)}:{program.probe_id}')[:8],16)
    if draw%17==0:
        return VerifierObservation(program.probe_id,not bool(truth),.56)
    return VerifierObservation(program.probe_id,bool(truth),.969)


def run_heldout_episode(seed: int, regime: str, mode: str):
    seed=int(seed)
    if regime not in HELDOUT_REGIMES:
        raise ValueError('unknown R2.40 heldout regime')
    if mode not in MODES:
        raise ValueError('unknown R2.40 mode')
    hypotheses,atoms,values=parent._prepared(FAMILY)
    target,equivalent=parent._target(FAMILY,seed)
    target_values=values[target]
    macros=parent.learn_macro_library()
    def verifier(program):
        truth=evaluate_typed_probe(program,target_values)
        return _held_observation(seed,regime,program,bool(truth))
    common=dict(
        verifier=verifier,counterexample_check=lambda h:h.operator_id in equivalent,
        query_budget=parent.QUERY_BUDGET,probe_cost_budget=parent.PROBE_COST_BUDGET,
        accept_probability=parent.ACCEPT_PROBABILITY,accept_margin=parent.ACCEPT_MARGIN,
        atom_shortlist_size=parent.ATOM_SHORTLIST_SIZE,max_raw_candidates=parent.MAX_RAW_CANDIDATES,
        max_macro_candidates=parent.MAX_MACRO_CANDIDATES,
    )
    initial=parent._initial_probes(FAMILY,seed,'clean')
    if mode=='calibrated':
        decision=discover_with_calibrated_macro_applicability(hypotheses,atoms,values,initial,macros,applicability_threshold=APPLICABILITY_THRESHOLD,**common)
    else:
        p_mode={'unconditional_macro':'recursive_macro','no_macro':'recursive_no_macro','r238_binary':'r238_binary'}[mode]
        decision=discover_with_recursive_typed_probes(hypotheses,atoms,values,initial,macros if p_mode=='recursive_macro' else (),mode=p_mode,complexity_weight=0.0,**common)
    row={'schema_version':1,'milestone':'R2.40 Uncertainty-Aware Macro Applicability Calibration','family':FAMILY,'episode_key':seed,'regime':regime}
    row.update(_public_decision(mode,decision,equivalent))
    return row
