from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from .r219_representation_types import VerifierObservation
from .r220_language_synthesis import OperatorProposal

_EPS = 1e-15


@dataclass(frozen=True)
class ProposalSupport:
    operator_id: str
    log_likelihood: float
    posterior: float


@dataclass(frozen=True)
class OperatorDiscoveryDecision:
    status: str
    operator_id: str | None
    posterior: float
    margin: float
    mdl_cost: int | None
    queries: tuple[str, ...]
    reason: str


def _normalize(log_rows):
    m = max(log_rows.values())
    weights = {k: math.exp(v-m) for k,v in log_rows.items()}
    total = sum(weights.values())
    return {k:v/total for k,v in weights.items()}


def initial_proposal_supports(proposals: Sequence[OperatorProposal], *, complexity_weight: float) -> tuple[ProposalSupport, ...]:
    proposals = tuple(proposals)
    if not proposals:
        raise ValueError('proposals must be non-empty')
    if len({p.operator_id for p in proposals}) != len(proposals):
        raise ValueError('proposals must be semantically unique')
    logs = {p.operator_id: -float(complexity_weight) * p.mdl_cost for p in proposals}
    post = _normalize(logs)
    return tuple(ProposalSupport(p.operator_id, logs[p.operator_id], post[p.operator_id]) for p in proposals)


def update_proposal_supports(proposals, supports, observation: VerifierObservation, predicted_labels: Mapping[str,bool]):
    proposals=tuple(proposals)
    by={s.operator_id:s for s in supports}
    ids={p.operator_id for p in proposals}
    if set(by)!=ids or set(predicted_labels)!=ids:
        raise ValueError('support/prediction coverage mismatch')
    logs={}
    r=observation.reliability
    for p in proposals:
        prior=by[p.operator_id].log_likelihood
        like=r if bool(predicted_labels[p.operator_id]) == observation.observed_label else 1-r
        logs[p.operator_id]=prior+math.log(max(_EPS,like))
    post=_normalize(logs)
    return tuple(ProposalSupport(p.operator_id,logs[p.operator_id],post[p.operator_id]) for p in proposals)


def choose_operator_query(proposals, supports, candidates, predictions):
    proposals=tuple(proposals)
    by={s.operator_id:s.posterior for s in supports}
    scored=[]
    for q in candidates:
        row=predictions[q]
        p_true=sum(by[oid] for oid,label in row.items() if bool(label))
        disagreement=2*p_true*(1-p_true)
        scored.append((-disagreement,str(q)))
    if not scored:
        raise ValueError('candidates must be non-empty')
    return min(scored)[1]


def discover_operator(
    proposals: Sequence[OperatorProposal], query_ids, predictions,
    *, verifier: Callable[[str], VerifierObservation],
    counterexample_check: Callable[[OperatorProposal], bool],
    query_budget: int, accept_probability: float, accept_margin: float,
    max_mdl_cost: int, complexity_weight: float,
):
    proposals=tuple(p for p in proposals if p.mdl_cost <= int(max_mdl_cost))
    if not proposals:
        return OperatorDiscoveryDecision('abstain',None,0.0,0.0,None,(), 'no_proposals_within_complexity_budget')
    byp={p.operator_id:p for p in proposals}
    supports=initial_proposal_supports(proposals, complexity_weight=complexity_weight)
    remaining=list(dict.fromkeys(map(str,query_ids)))
    queried=[]
    budget=min(int(query_budget),len(remaining))
    for _ in range(budget):
        q=choose_operator_query(proposals,supports,remaining,predictions)
        obs=verifier(q)
        if obs.query_id != q:
            raise ValueError('verifier returned wrong query')
        supports=update_proposal_supports(proposals,supports,obs,predictions[q])
        queried.append(q); remaining.remove(q)
        ranked=sorted(supports,key=lambda s:(-s.posterior,s.operator_id))
        top=ranked[0]; second=ranked[1] if len(ranked)>1 else None
        margin=top.posterior-(second.posterior if second else 0.0)
        if top.posterior >= accept_probability and margin >= accept_margin:
            p=byp[top.operator_id]
            if counterexample_check(p):
                return OperatorDiscoveryDecision('accept',p.operator_id,top.posterior,margin,p.mdl_cost,tuple(queried),'supported_compact_operator_survived_counterexample')
            return OperatorDiscoveryDecision('abstain',None,top.posterior,margin,p.mdl_cost,tuple(queried),'counterexample_rejected_top_operator')
    ranked=sorted(supports,key=lambda s:(-s.posterior,s.operator_id))
    top=ranked[0]; second=ranked[1] if len(ranked)>1 else None
    margin=top.posterior-(second.posterior if second else 0.0)
    return OperatorDiscoveryDecision('abstain',None,top.posterior,margin,top and byp[top.operator_id].mdl_cost,tuple(queried),'insufficient_identifiability_or_budget')
