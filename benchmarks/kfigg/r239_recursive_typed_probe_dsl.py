from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass
from functools import lru_cache

from cogcoder.r219_representation_types import VerifierObservation
from cogcoder.r239_predicate_macros import ProbeMacro, induce_probe_macros
from cogcoder.r239_recursive_probe_synthesis import synthesize_recursive_typed_probe
from cogcoder.r220_operator_discovery import initial_proposal_supports, update_proposal_supports
from cogcoder.r239_typed_probe_dsl import typed_prediction_row
from cogcoder.r239_recursive_discovery import discover_with_recursive_typed_probes
from cogcoder.r239_typed_probe_dsl import const3, eq_probe, evaluate_typed_probe, trit_atom

MACRO_TRAIN_SEEDS = (301, 307, 311, 313, 317, 331)
DEV_EVAL_SEEDS = (347, 349, 353)
TRANSFER_DRY_RUN_SEEDS = (401, 409)
DEV_REGIMES = ('clean', 'noisy')
MODES = ('recursive_macro', 'recursive_no_macro', 'r238_binary', 'atomic_only')

HYPOTHESIS_COUNT = 16
INITIAL_PROBE_COUNT = 1
QUERY_BUDGET = 5
PROBE_COST_BUDGET = 12.0
ACCEPT_PROBABILITY = .94
ACCEPT_MARGIN = .70
ATOM_SHORTLIST_SIZE = 8
MAX_RAW_CANDIDATES = 480
MAX_MACRO_CANDIDATES = 160


@dataclass(frozen=True)
class TernaryHypothesis:
    operator_id: str
    mdl_cost: int = 1


def ternary_states():
    return tuple(itertools.product((0, 1, 2), repeat=2))


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _atom_id(state, coord: int) -> str:
    return f'z3:{state[0]}{state[1]}:y{int(coord)}'


def _affine(params, state):
    a,b,c,d,e,f = params; x0,x1 = state
    return ((a*x0+b*x1+c)%3, (d*x0+e*x1+f)%3)


def _bilinear(params, state):
    a,b,c,d,e,f,g,h = params; x0,x1 = state; cross=(x0*x1)%3
    return ((a*x0+b*x1+c+g*cross)%3, (d*x0+e*x1+f+h*cross)%3)


def _candidate_params(family: str):
    if family == 'z3_affine_sparse':
        source = itertools.product((0,1,2), repeat=6); transition = _affine
        def valid(p):
            a,b,_,d,e,_=p; return (a,b)!=(0,0) and (d,e)!=(0,0)
    elif family == 'z3_bilinear_asym':
        source = itertools.product((0,1,2), repeat=8); transition = _bilinear
        def valid(p):
            a,b,_,d,e,_,g,h=p; return (a,b)!=(0,0) and (d,e)!=(0,0) and (g,h)!=(0,0) and g != h
    else:
        raise ValueError('unknown ternary family')
    states=ternary_states(); rows=[]; seen=set()
    for params in source:
        if not valid(params): continue
        signature=tuple(v for s in states for v in transition(params,s))
        if signature in seen: continue
        seen.add(signature); rows.append((_digest(f'r239:{family}:{params}'), tuple(params), signature))
    rows.sort(key=lambda r:(r[0],r[1]))
    return transition, tuple(p for _,p,_ in rows[:HYPOTHESIS_COUNT])


@lru_cache(maxsize=4)
def _prepared(family: str):
    transition, params_rows = _candidate_params(family); states=ternary_states()
    atom_ids=tuple(_atom_id(s,c) for s in states for c in range(2)); hypotheses=[]; values={}
    for params in params_rows:
        hid='th:'+_digest(f'{family}:{params}')[:20]; hypotheses.append(TernaryHypothesis(hid)); row={}
        for state in states:
            after=transition(params,state); row[_atom_id(state,0)]=after[0]; row[_atom_id(state,1)]=after[1]
        values[hid]=row
    return tuple(hypotheses), atom_ids, values


def _target(family: str, episode_key: int):
    hypotheses, _, values=_prepared(family)
    idx=int(_digest(f'r239-target:{family}:{int(episode_key)}')[:16],16)%len(hypotheses)
    target=hypotheses[idx]; signature=tuple(values[target.operator_id][k] for k in sorted(values[target.operator_id]))
    equivalent=frozenset(h.operator_id for h in hypotheses if tuple(values[h.operator_id][k] for k in sorted(values[h.operator_id])) == signature)
    return target.operator_id,equivalent


def _initial_probes(family: str, episode_key: int, regime: str):
    _,atom_ids,_=_prepared(family)
    probes=[eq_probe(trit_atom(q),const3(v)) for q in atom_ids for v in (0,1,2)]
    ranked=sorted(probes,key=lambda p:(_digest(f'r239-pool:{family}:{int(episode_key)}:{regime}:{p.probe_id}'),p.probe_id))
    return tuple(ranked[:INITIAL_PROBE_COUNT])


def _noise_observation(family: str, episode_key: int, regime: str, program, label: bool):
    if regime == 'clean': return VerifierObservation(program.probe_id,bool(label),.997)
    if regime == 'held_clean': return VerifierObservation(program.probe_id,bool(label),.992)
    draw=int(_digest(f'r239-noise:{family}:{int(episode_key)}:{program.probe_id}')[:8],16)
    if regime == 'noisy':
        if draw % 31 == 0: return VerifierObservation(program.probe_id,not bool(label),.64)
        return VerifierObservation(program.probe_id,bool(label),.985)
    if regime == 'held_noisy':
        if draw % 23 == 0: return VerifierObservation(program.probe_id,not bool(label),.60)
        return VerifierObservation(program.probe_id,bool(label),.975)
    raise ValueError('unknown verifier regime')


def _program_signature(program):
    return {'probe_id':program.probe_id,'op':program.op,'depth':program.depth,'mdl_cost':program.mdl_cost,'leaf_count':program.leaf_count,'execution_cost':program.execution_cost}


def _run_episode(family: str, episode_key: int, regime: str, mode: str, macros=()):
    hypotheses,atom_ids,values=_prepared(family); target,equivalent=_target(family,episode_key); target_values=values[target]
    def verifier(program):
        label=evaluate_typed_probe(program,target_values)
        return _noise_observation(family,episode_key,regime,program,bool(label))
    decision=discover_with_recursive_typed_probes(
        hypotheses,atom_ids,values,_initial_probes(family,episode_key,regime),tuple(macros),
        verifier=verifier,counterexample_check=lambda h:h.operator_id in equivalent,
        query_budget=QUERY_BUDGET,probe_cost_budget=PROBE_COST_BUDGET,accept_probability=ACCEPT_PROBABILITY,accept_margin=ACCEPT_MARGIN,
        mode=mode,atom_shortlist_size=ATOM_SHORTLIST_SIZE,max_raw_candidates=MAX_RAW_CANDIDATES,max_macro_candidates=MAX_MACRO_CANDIDATES,complexity_weight=0.0,
    )
    correct=decision.status=='accept' and decision.operator_id in equivalent; false_accept=decision.status=='accept' and decision.operator_id not in equivalent
    return {'schema_version':1,'milestone':'R2.39 Recursive Typed Probe DSL + Learned Intermediate Predicates','family':family,'episode_key':int(episode_key),'regime':regime,'mode':mode,'hypothesis_count':len(hypotheses),'atom_count':len(atom_ids),'query_budget':QUERY_BUDGET,'probe_cost_budget':PROBE_COST_BUDGET,'status':decision.status,'correct':bool(correct),'false_accept':bool(false_accept),'queries_used':len(decision.queries),'total_probe_cost':decision.total_probe_cost,'macro_probe_count':len(decision.macro_probe_ids),'recursive_probe_count':len(decision.recursive_probe_ids),'raw_candidates_evaluated':decision.raw_candidates_evaluated,'macro_candidates_evaluated':decision.macro_candidates_evaluated,'programs':[_program_signature(p) for p in decision.probe_programs],'_program_objects':decision.probe_programs}


def _macro_training_programs(seed: int):
    hypotheses, atom_ids, values = _prepared('z3_affine_sparse'); target, _ = _target('z3_affine_sparse', seed)
    supports = initial_proposal_supports(hypotheses, complexity_weight=0.0); observed = set(); programs = []
    initial = _initial_probes('z3_affine_sparse', seed, 'clean')
    for probe in initial[:3]:
        receipt = synthesize_recursive_typed_probe(atom_ids, supports, values, observed, atom_shortlist_size=ATOM_SHORTLIST_SIZE, max_raw_candidates=MAX_RAW_CANDIDATES)
        programs.append(receipt.best_recursive_program)
        label = evaluate_typed_probe(probe, values[target]); obs = _noise_observation('z3_affine_sparse', seed, 'clean', probe, bool(label))
        supports = update_proposal_supports(hypotheses, supports, obs, typed_prediction_row(probe, values)); observed.add(probe.probe_id)
    return tuple(programs)


@lru_cache(maxsize=1)
def learn_macro_library() -> tuple[ProbeMacro,...]:
    episode_programs={f'train-{seed}':_macro_training_programs(seed) for seed in MACRO_TRAIN_SEEDS}
    return induce_probe_macros(episode_programs,min_support=2,max_macros=8)


def _public(row): return {k:v for k,v in row.items() if k != '_program_objects'}


def _aggregate(rows):
    episodes_per_mode=len([r for r in rows if r['mode']=='recursive_macro']); out={'episodes_per_mode':episodes_per_mode}
    for mode in MODES:
        subset=[r for r in rows if r['mode']==mode]
        out[f'{mode}_correct']=sum(r['correct'] for r in subset)
        out[f'{mode}_mean_probe_cost']=sum(r['total_probe_cost'] for r in subset)/len(subset)
        out[f'{mode}_mean_candidate_evals']=sum(r['raw_candidates_evaluated']+r['macro_candidates_evaluated'] for r in subset)/len(subset)
    out['macro_probe_count']=sum(r['macro_probe_count'] for r in rows if r['mode']=='recursive_macro'); out['false_accepts']=sum(r['false_accept'] for r in rows)
    return out


def _matrix(family,seeds):
    macros=learn_macro_library(); rows=[]
    for regime in DEV_REGIMES:
        for seed in seeds:
            for mode in MODES: rows.append(_run_episode(family,seed,regime,mode,macros if mode=='recursive_macro' else ()))
    summary=_aggregate(rows)
    gates={'recursive_macro_all_correct':summary['recursive_macro_correct']==summary['episodes_per_mode'],'zero_false_accepts':summary['false_accepts']==0,'strict_gain_over_r238_binary':(summary['recursive_macro_correct']>summary['r238_binary_correct'] or (summary['recursive_macro_correct']==summary['r238_binary_correct'] and summary['recursive_macro_mean_probe_cost']<summary['r238_binary_mean_probe_cost'])),'macro_not_worse_than_recursive_no_macro':summary['recursive_macro_correct']>=summary['recursive_no_macro_correct'],'macro_search_or_probe_efficiency':(summary['recursive_macro_mean_candidate_evals']<=summary['recursive_no_macro_mean_candidate_evals'] or summary['recursive_macro_mean_probe_cost']<summary['recursive_no_macro_mean_probe_cost']),'macro_exercised':summary['macro_probe_count']>0,'same_query_and_cost_ceiling':all(r['query_budget']==QUERY_BUDGET and r['probe_cost_budget']==PROBE_COST_BUDGET for r in rows)}
    return {'schema_version':1,'family':family,'rows':[_public(r) for r in rows],'summary':summary,'gates':gates,'all_gates_pass':all(gates.values())}


def run_dev_matrix(): return _matrix('z3_affine_sparse',DEV_EVAL_SEEDS)

def run_transfer_dry_run():
    result=_matrix('z3_bilinear_asym',TRANSFER_DRY_RUN_SEEDS); result['gates'].pop('strict_gain_over_r238_binary', None); result['gates']['non_bit_transfer_family']='bilinear' in result['family']; result['all_gates_pass']=all(result['gates'].values()); return result


def run_episode(family: str, episode_key: int, regime: str, mode: str) -> dict:
    macros = learn_macro_library() if mode == 'recursive_macro' else ()
    return _public(_run_episode(family, int(episode_key), str(regime), str(mode), macros))

def macro_library_payload():
    return {'schema_version':1,'milestone':'R2.39 Recursive Typed Probe DSL + Learned Intermediate Predicates','train_family':'z3_affine_sparse','train_seeds':list(MACRO_TRAIN_SEEDS),'macros':[{'macro_id':m.macro_id,'support':m.support,'compression_gain':m.compression_gain,'arity':m.arity,'raw_mdl_cost':m.raw_mdl_cost,'call_mdl_cost':m.call_mdl_cost,'template_probe_id':m.template.probe_id,'parameter_types':[t.value for t in m.parameter_types]} for m in learn_macro_library()]}


if __name__=='__main__':
    print(json.dumps({'macro_library':macro_library_payload(),'dev':run_dev_matrix(),'transfer':run_transfer_dry_run()},indent=2,sort_keys=True))
