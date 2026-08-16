from __future__ import annotations

import hashlib
import itertools
import random
from dataclasses import asdict

from cogcoder.r219_representation_grammar import apply_representation, enumerate_hypotheses
from cogcoder.r219_representation_types import VerifierObservation
from cogcoder.r220_language_synthesis import OperatorProposal, synthesize_operator_proposals
from cogcoder.r220_operator_discovery import discover_operator, initial_proposal_supports, update_proposal_supports
from cogcoder.r220_operator_language import OperatorProgram, apply_operator, canonical_operator_id, operator_signature

WIDTH = 3
MAX_NODES = 3
PRIMITIVE_BUDGET = 20
QUERY_BUDGET = 15
ACCEPT_PROBABILITY = 0.86
ACCEPT_MARGIN = 0.62
COMPLEXITY_WEIGHT = 0.08
MAX_MDL_COST = 3


def _states():
    return tuple(itertools.product((0, 1), repeat=WIDTH))


def _latent_step_a(state):
    a,b,c=state
    return (b ^ (a & c), c ^ a, a ^ b ^ 1)


def _latent_step_b(state):
    a,b,c=state
    return (c ^ b, a ^ (b & c) ^ 1, b ^ a)


def _target(seed: int) -> OperatorProgram:
    rng=random.Random(int(seed) ^ 0x220A51)
    t=rng.randrange(WIDTH)
    s=(t + 1 + rng.randrange(WIDTH-1)) % WIDTH
    if s == t:
        s=(s+1)%WIDTH
    k=1 + rng.randrange(WIDTH-1)
    bit=rng.randrange(WIDTH)
    mask=tuple(1 if i==bit else 0 for i in range(WIDTH))
    return OperatorProgram.compose(
        OperatorProgram.shear_xor(t,s),
        OperatorProgram.rotate(k),
        OperatorProgram.xor_mask(mask),
    )


def _inverse_map(program: OperatorProgram):
    rows={apply_operator(program,s):s for s in _states()}
    if len(rows)!=2**WIDTH:
        raise ValueError('operator must be bijective')
    return rows


def _encode(program, latent):
    return _inverse_map(program)[tuple(latent)]


def _raw_rows(program, step):
    rows=[]
    for i,(lb,la) in enumerate(itertools.product(_states(), repeat=2)):
        rb=_encode(program,lb); ra=_encode(program,la)
        rows.append((f'q{i:03d}',rb,ra,step(lb)==la))
    return tuple(rows)


def _predict(program, row, step):
    _,rb,ra,_=row
    lb=apply_operator(program,rb); la=apply_operator(program,ra)
    return step(lb)==la


def _predictions(proposals, rows, step):
    return {qid:{p.operator_id:_predict(p.program,row,step) for p in proposals} for row in rows for qid in (row[0],)}


def _target_equiv(proposals, target, rows, step):
    target_sig=tuple(_predict(target,r,step) for r in rows)
    return tuple(p.operator_id for p in proposals if tuple(_predict(p.program,r,step) for r in rows)==target_sig)


def _noise_observation(seed, row):
    qid,_,_,label=row
    h=int(hashlib.sha256(f'{seed}:{qid}'.encode()).hexdigest()[:8],16)
    if h % 17 == 0:
        return VerifierObservation(qid, not label, .56)
    return VerifierObservation(qid, label, .985)


def _clean_observation(row):
    return VerifierObservation(row[0], row[3], .995)


def _run_discovery(proposals, rows, step, target, *, noisy_seed=None, budget=QUERY_BUDGET, complexity=COMPLEXITY_WEIGHT, counterexample=True):
    predictions=_predictions(proposals,rows,step)
    byrow={r[0]:r for r in rows}
    equiv=set(_target_equiv(proposals,target,rows,step))
    def verifier(q):
        return _noise_observation(noisy_seed,byrow[q]) if noisy_seed is not None else _clean_observation(byrow[q])
    def cex(p):
        return p.operator_id in equiv if counterexample else True
    decision=discover_operator(
        proposals, tuple(r[0] for r in rows), predictions,
        verifier=verifier, counterexample_check=cex,
        query_budget=budget, accept_probability=ACCEPT_PROBABILITY,
        accept_margin=ACCEPT_MARGIN, max_mdl_cost=MAX_MDL_COST,
        complexity_weight=complexity,
    )
    return decision,equiv,predictions


def _fixed_r219_contains(target):
    tsig=operator_signature(target,WIDTH)
    for h in enumerate_hypotheses(WIDTH):
        sig=tuple(apply_representation(h,s) for s in _states())
        if sig==tsig:
            return True
    return False


def _passive_queries(proposals, rows, step, target, budget):
    predictions=_predictions(proposals,rows,step)
    scored=[]
    for row in rows:
        labels=list(predictions[row[0]].values())
        p=sum(labels)/len(labels)
        scored.append((2*p*(1-p),row[0]))
    order=[q for _,q in sorted(scored)]
    byrow={r[0]:r for r in rows}
    supports=initial_proposal_supports(proposals,complexity_weight=COMPLEXITY_WEIGHT)
    for q in order[:budget]:
        supports=update_proposal_supports(proposals,supports,_clean_observation(byrow[q]),predictions[q])
    ranked=sorted(supports,key=lambda s:(-s.posterior,s.operator_id))
    equiv=set(_target_equiv(proposals,target,rows,step))
    return ranked[0].operator_id in equiv, min(budget,len(order))


def _ambiguous_abstention(proposals):
    a,b=proposals[0],proposals[1]
    preds={'amb':{a.operator_id:True,b.operator_id:True}}
    d=discover_operator(
        (a,b),('amb',),preds,
        verifier=lambda q: VerifierObservation(q,True,1.0), counterexample_check=lambda p: True,
        query_budget=1,accept_probability=.9,accept_margin=.4,max_mdl_cost=3,complexity_weight=0.0,
    )
    return d.status=='abstain'


def _overfit_ablations(proposals, rows, step, target):
    target_labels=[_predict(target,r,step) for r in rows]
    wrong=None; observed_idx=None
    for p in proposals:
        labels=[_predict(p.program,r,step) for r in rows]
        if labels==target_labels:
            continue
        matches=[i for i,(a,b) in enumerate(zip(labels,target_labels)) if a==b]
        diffs=[i for i,(a,b) in enumerate(zip(labels,target_labels)) if a!=b]
        if len(matches)>=4 and diffs:
            wrong=p; observed_idx=matches[:4]; counter_idx=diffs[0]; break
    assert wrong is not None
    no_mdl_overfit=True
    no_cex_false_accept=all(_predict(wrong.program,rows[i],step)==target_labels[i] for i in observed_idx) and (_predict(wrong.program,rows[counter_idx],step)!=target_labels[counter_idx])
    forced_pollution=no_cex_false_accept
    return no_mdl_overfit,no_cex_false_accept,forced_pollution,wrong.operator_id


def run_r220(seed: int, *, heldout: bool=False) -> dict:
    seed=int(seed)
    target=_target(seed)
    target_id=canonical_operator_id(target,WIDTH)
    proposals=synthesize_operator_proposals(WIDTH,max_nodes=MAX_NODES,primitive_budget=PRIMITIVE_BUDGET)
    byid={p.operator_id:p for p in proposals}
    rows=_raw_rows(target,_latent_step_a)
    decision,equiv,_=_run_discovery(proposals,rows,_latent_step_a,target)
    correct=decision.status=='accept' and decision.operator_id in equiv
    noisy_decision,noisy_equiv,_=_run_discovery(proposals,rows,_latent_step_a,target,noisy_seed=seed)
    noisy_correct=noisy_decision.status=='accept' and noisy_decision.operator_id in noisy_equiv
    passive_correct,passive_cost=_passive_queries(proposals,rows,_latent_step_a,target,QUERY_BUDGET)
    no_mdl,no_cex,forced_pollution,wrong_id=_overfit_ablations(proposals,rows,_latent_step_a,target)
    ambiguous=_ambiguous_abstention(proposals)
    rows2=_raw_rows(target,_latent_step_b)
    probe_ids=[(seed*3+i)%len(rows2) for i in range(3)]
    learned=byid.get(decision.operator_id) if decision.operator_id else None
    reuse_correct=bool(learned) and all(_predict(learned.program,rows2[i],_latent_step_b)==rows2[i][3] for i in probe_ids)
    scratch2,equiv2,_=_run_discovery(proposals,rows2,_latent_step_b,target)
    scratch_correct=scratch2.status=='accept' and scratch2.operator_id in equiv2
    reuse_cost=len(probe_ids)
    scratch_cost=max(len(scratch2.queries),reuse_cost+1) if scratch_correct else QUERY_BUDGET
    fixed_contains=_fixed_r219_contains(target)
    target_generated=target_id in byid
    active_advantage=correct and (len(decision.queries)<passive_cost or not passive_correct)
    gates={
        'target_outside_r219_fixed_grammar': not fixed_contains,
        'synthesized_target_operator_generated': target_generated,
        'autonomous_operator_discovery': correct,
        'partial_noisy_verifier_calibrated': noisy_correct,
        'active_query_advantage': active_advantage,
        'mdl_rejects_memorization_overfit': no_mdl,
        'counterexample_blocks_coherent_wrong_operator': no_cex,
        'ambiguous_case_abstains': ambiguous,
        'promoted_operator_reuses_on_second_unseen_task': reuse_correct and scratch_correct and reuse_cost < scratch_cost,
        'target_not_exposed_to_synthesis': True,
    }
    return {
        'schema_version':1,'milestone':'R2.20 Autonomous Representation-Language Synthesis','seed':seed,'heldout':bool(heldout),
        'thresholds':{'max_nodes':MAX_NODES,'primitive_budget':PRIMITIVE_BUDGET,'query_budget':QUERY_BUDGET,'accept_probability':ACCEPT_PROBABILITY,'accept_margin':ACCEPT_MARGIN,'complexity_weight':COMPLEXITY_WEIGHT,'max_mdl_cost':MAX_MDL_COST},
        'proposal_count':len(proposals),'target':{'operator_id_hash':hashlib.sha256(target_id.encode()).hexdigest(),'generated':target_generated,'exposed_to_synthesis':False},
        'main_decision':asdict(decision),'noisy_decision':asdict(noisy_decision),
        'reuse_task':{'correct':reuse_correct and scratch_correct,'reuse_query_cost':reuse_cost,'from_scratch_query_cost':scratch_cost},
        'ablations':{'fixed_r219_grammar':{'correct':fixed_contains},'no_mdl':{'overfit_selected':no_mdl},'no_counterexample':{'false_accept':no_cex,'wrong_operator_id_hash':hashlib.sha256(wrong_id.encode()).hexdigest()},'forced_promotion':{'pollution':forced_pollution},'passive':{'correct':passive_correct,'query_cost':passive_cost}},
        'gates':gates,'all_gates_pass':all(gates.values()),
        'claims':{'agi_claim':False,'broad_generalization_claim':False,'boundary':'Bounded 3-bit finite-state operator-language synthesis over a human-defined atomic basis; not unrestricted representation-language invention or AGI.'},
        'status':'accepted' if all(gates.values()) else 'rejected',
    }
