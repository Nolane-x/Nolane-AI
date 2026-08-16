from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache

from cogcoder.r219_representation_types import VerifierObservation
from cogcoder.r220_operator_discovery import choose_operator_query, initial_proposal_supports, update_proposal_supports
from cogcoder.r220_language_synthesis import synthesize_operator_proposals
from cogcoder.r221_adaptive_evidence import discover_operator_adaptive
from . import r220_language_synthesis as r220

BASE_BUDGET = 12
MAX_BUDGET = 24
CONTINUATION_MIN_DISAGREEMENT = 0.01
RECOVERABILITY_FLOOR = 0.01

@lru_cache(maxsize=1)
def _proposal_library():
    return r220.synthesize_operator_proposals(r220.WIDTH, max_nodes=r220.MAX_NODES, primitive_budget=r220.PRIMITIVE_BUDGET)

@lru_cache(maxsize=64)
def _frozen_r220(seed: int, heldout: bool):
    return r220.run_r220(int(seed), heldout=bool(heldout))

def _adaptive_discovery(seed: int, *, noisy: bool):
    target = r220._target(seed); proposals = _proposal_library(); rows = r220._raw_rows(target, r220._latent_step_a)
    predictions = r220._predictions(proposals, rows, r220._latent_step_a); byrow = {row[0]: row for row in rows}
    equiv = set(r220._target_equiv(proposals, target, rows, r220._latent_step_a))
    def verifier(q: str) -> VerifierObservation:
        return r220._noise_observation(seed, byrow[q]) if noisy else r220._clean_observation(byrow[q])
    decision = discover_operator_adaptive(proposals, tuple(row[0] for row in rows), predictions, verifier=verifier,
        counterexample_check=lambda proposal: proposal.operator_id in equiv, base_budget=BASE_BUDGET, max_budget=MAX_BUDGET,
        accept_probability=r220.ACCEPT_PROBABILITY, accept_margin=r220.ACCEPT_MARGIN, max_mdl_cost=r220.MAX_MDL_COST,
        complexity_weight=r220.COMPLEXITY_WEIGHT, continuation_min_disagreement=CONTINUATION_MIN_DISAGREEMENT,
        recoverability_floor=RECOVERABILITY_FLOOR)
    correct = decision.status == 'accept' and decision.operator_id in equiv
    return decision, correct, proposals, rows, target, equiv, predictions

def _always_max(seed: int) -> dict:
    target = r220._target(seed); proposals = tuple(p for p in _proposal_library() if p.mdl_cost <= r220.MAX_MDL_COST)
    rows = r220._raw_rows(target, r220._latent_step_a); predictions = r220._predictions(proposals, rows, r220._latent_step_a)
    byrow = {row[0]: row for row in rows}; equiv = set(r220._target_equiv(proposals, target, rows, r220._latent_step_a))
    supports = initial_proposal_supports(proposals, complexity_weight=r220.COMPLEXITY_WEIGHT); remaining = [row[0] for row in rows]; queried=[]
    for _ in range(min(MAX_BUDGET, len(remaining))):
        q=choose_operator_query(proposals,supports,remaining,predictions)
        supports=update_proposal_supports(proposals,supports,r220._noise_observation(seed,byrow[q]),predictions[q]); queried.append(q); remaining.remove(q)
    ranked=sorted(supports,key=lambda row:(-row.posterior,row.operator_id)); top=ranked[0]; second=ranked[1].posterior if len(ranked)>1 else 0.0
    margin=top.posterior-second; correct=top.operator_id in equiv and top.posterior>=r220.ACCEPT_PROBABILITY and margin>=r220.ACCEPT_MARGIN
    return {'correct':correct,'query_cost':len(queried),'posterior':top.posterior,'margin':margin}

def _adaptive_ambiguous_abstains() -> bool:
    proposals=synthesize_operator_proposals(2,max_nodes=1,primitive_budget=4)[:2]; a,b=proposals
    predictions={f'amb{i}':{a.operator_id:bool(i%2),b.operator_id:bool(i%2)} for i in range(6)}
    decision=discover_operator_adaptive((a,b),tuple(predictions),predictions,
        verifier=lambda q: VerifierObservation(q,predictions[q][a.operator_id],.99), counterexample_check=lambda proposal: True,
        base_budget=2,max_budget=6,accept_probability=.9,accept_margin=.5,max_mdl_cost=3,complexity_weight=0.0,
        continuation_min_disagreement=CONTINUATION_MIN_DISAGREEMENT,recoverability_floor=RECOVERABILITY_FLOOR)
    return decision.status=='abstain'

def run_r221(seed: int, *, heldout: bool=False) -> dict:
    seed=int(seed); frozen=_frozen_r220(seed,heldout); diagnostic=_frozen_r220(73459,True)
    clean_decision,clean_correct,*_=_adaptive_discovery(seed,noisy=False); noisy_decision,noisy_correct,*_=_adaptive_discovery(seed,noisy=True)
    always_max=_always_max(seed); ambiguous=_adaptive_ambiguous_abstains(); diagnostic_decision,diagnostic_correct,*_=_adaptive_discovery(73459,noisy=True)
    diagnostic_preserved=diagnostic['all_gates_pass'] is False and diagnostic['gates']['partial_noisy_verifier_calibrated'] is False and diagnostic_correct and len(diagnostic_decision.queries)>r220.QUERY_BUDGET
    gates={'diagnostic_fixed15_failure_preserved':diagnostic_preserved,'adaptive_noisy_verifier_calibrated':noisy_correct,
        'adaptive_clean_discovery_correct':clean_correct,'adaptive_cost_below_always_max':len(noisy_decision.queries)<always_max['query_cost'],
        'always_max_correctness_not_better':(not always_max['correct']) or noisy_correct,'nonidentifiable_case_abstains':ambiguous,
        'r220_target_outside_fixed_grammar':frozen['gates']['target_outside_r219_fixed_grammar'],'r220_operator_generated':frozen['gates']['synthesized_target_operator_generated'],
        'r220_main_discovery_intact':frozen['gates']['autonomous_operator_discovery'],'r220_prospective_reuse_intact':frozen['gates']['promoted_operator_reuses_on_second_unseen_task']}
    return {'schema_version':1,'milestone':'R2.21 Confidence-Adaptive Evidence Acquisition','seed':seed,'heldout':bool(heldout),
        'thresholds':{'base_budget':BASE_BUDGET,'max_budget':MAX_BUDGET,'continuation_min_disagreement':CONTINUATION_MIN_DISAGREEMENT,'recoverability_floor':RECOVERABILITY_FLOOR,
        'accept_probability':r220.ACCEPT_PROBABILITY,'accept_margin':r220.ACCEPT_MARGIN,'complexity_weight':r220.COMPLEXITY_WEIGHT},
        'adaptive_clean_decision':{**asdict(clean_decision),'queries_used':len(clean_decision.queries),'correct':clean_correct},
        'adaptive_noisy_decision':{**asdict(noisy_decision),'queries_used':len(noisy_decision.queries),'correct':noisy_correct},
        'diagnostic_73459':{'frozen_r220_failed_noise_gate':diagnostic['gates']['partial_noisy_verifier_calibrated'] is False,'adaptive_correct':diagnostic_correct,'adaptive_queries':len(diagnostic_decision.queries)},
        'ablations':{'fixed_15':{'diagnostic_correct':diagnostic['gates']['partial_noisy_verifier_calibrated'],'query_budget':r220.QUERY_BUDGET},'always_max':always_max},
        'gates':gates,'all_gates_pass':all(gates.values()),'status':'accepted' if all(gates.values()) else 'rejected',
        'claims':{'agi_claim':False,'broad_generalization_claim':False,'boundary':'Adaptive evidence acquisition over the bounded R2.20 finite-state operator language; not unrestricted representation invention or AGI.'}}
