from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .r219_representation_types import VerifierObservation
from .r220_operator_discovery import initial_proposal_supports, update_proposal_supports
from .r239_predicate_macros import ProbeMacro
from .r239_recursive_discovery import (
    _atom_shortlist,
    _probe_utility,
    _rank,
    _select_macro,
)
from .r239_recursive_probe_synthesis import _posterior, synthesize_recursive_typed_probe
from .r239_typed_probe_dsl import ProbeType, TypedProbe, typed_prediction_row
from .r240_macro_applicability import MacroApplicabilityEvidence, assess_macro_applicability


@dataclass(frozen=True)
class CalibratedRecursiveDecision:
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
    applicability_routes: tuple[str, ...]
    applicability_lcbs: tuple[float, ...]
    observed_reliabilities: tuple[float, ...]
    reason: str


def _entropy(posterior: Mapping[str,float]) -> float:
    vals=[float(p) for p in posterior.values() if p>0]
    if len(vals)<=1:
        return 0.0
    h=-sum(p*math.log(p) for p in vals)
    return max(0.0,min(1.0,h/math.log(len(vals))))


def _agreement(a: TypedProbe,b: TypedProbe,posterior,values) -> float:
    ra=typed_prediction_row(a,values); rb=typed_prediction_row(b,values)
    return sum(float(posterior[h]) for h in posterior if bool(ra[h])==bool(rb[h]))


def discover_with_calibrated_macro_applicability(
    hypotheses,
    trit_atom_ids: Sequence[str],
    atom_values_by_hypothesis: Mapping[str,Mapping[str,int]],
    initial_probes: Sequence[TypedProbe],
    macros: Sequence[ProbeMacro],
    *,
    verifier: Callable[[TypedProbe],VerifierObservation],
    counterexample_check: Callable[[object],bool],
    query_budget: int,
    probe_cost_budget: float,
    accept_probability: float,
    accept_margin: float,
    atom_shortlist_size: int=8,
    max_raw_candidates: int=480,
    max_macro_candidates: int=160,
    applicability_threshold: float=.60,
    macro_reuse_bonus_weight: float=.005,
) -> CalibratedRecursiveDecision:
    hypotheses=tuple(hypotheses); macros=tuple(macros)
    if not hypotheses:
        raise ValueError('hypotheses must be non-empty')
    by_hypothesis={str(h.operator_id):h for h in hypotheses}
    supports=initial_proposal_supports(hypotheses,complexity_weight=0.0)
    remaining_initial=list(initial_probes)
    observed=set(); queries=[]; macro_ids=[]; recursive_ids=[]; programs=[]
    reliabilities=[]; routes=[]; lcbs=[]
    total_cost=0.0; raw_evals=0; macro_evals=0
    macro_deferred=False

    for _ in range(int(query_budget)):
        posterior=_posterior(supports)
        chosen=None; chosen_macro=None
        if remaining_initial:
            legal=[p for p in remaining_initial if p.probe_id not in observed]
            if not legal:
                remaining_initial=[]; continue
            scored=[]
            for p in legal:
                utility,disagreement=_probe_utility(p,posterior,atom_values_by_hypothesis)
                scored.append((-utility,-disagreement,p.mdl_cost,p.probe_id,p))
            chosen=min(scored)[-1]; remaining_initial.remove(chosen)
        else:
            raw=synthesize_recursive_typed_probe(
                trit_atom_ids,supports,atom_values_by_hypothesis,observed,
                atom_shortlist_size=atom_shortlist_size,
                max_raw_candidates=min(int(max_raw_candidates),96) if macros else int(max_raw_candidates),
            )
            raw_evals += raw.raw_candidates_evaluated
            chosen=raw.program
            raw_u,raw_d=_probe_utility(chosen,posterior,atom_values_by_hypothesis)
            route='defer_raw'; lcb=0.0
            if macros:
                macro,macro_program,evaluated=_select_macro(
                    macros,raw.shortlisted_atoms,supports,atom_values_by_hypothesis,observed,max_macro_candidates,
                )
                macro_evals += evaluated
                if macro is not None and macro_program is not None:
                    macro_u,macro_d=_probe_utility(macro_program,posterior,atom_values_by_hypothesis,effective_mdl=macro.call_mdl_cost)
                    margin=_rank(supports)[1]
                    evidence=MacroApplicabilityEvidence(
                        tuple(reliabilities),
                        _entropy(posterior),
                        margin,
                        _agreement(macro_program,chosen,posterior,atom_values_by_hypothesis),
                        max(0.0,1.0-abs(macro_d-raw_d)),
                        min(1.0,chosen.execution_cost/max(macro_program.execution_cost,1e-12)),
                        None,
                    )
                    assessment=assess_macro_applicability(evidence,threshold=applicability_threshold)
                    route='defer_raw' if macro_deferred else assessment.route
                    lcb=assessment.lower_confidence_bound
                    if route=='defer_raw':
                        macro_deferred=True
                    if route=='macro':
                        macro_u += float(macro_reuse_bonus_weight)*max(0.0,macro.compression_gain)
                        macro_key=(-macro_u,-macro_d,macro.call_mdl_cost,macro.macro_id,macro_program.probe_id)
                        raw_key=(-raw_u,-raw_d,chosen.mdl_cost,'~raw',chosen.probe_id)
                        if macro_key <= raw_key:
                            chosen=macro_program; chosen_macro=macro
            routes.append(route); lcbs.append(lcb)

        if chosen is None:
            break
        if chosen.output_type is not ProbeType.BOOL:
            raise TypeError('verifier probe root must be bool')
        if total_cost+chosen.execution_cost > float(probe_cost_budget)+1e-12:
            break
        observation=verifier(chosen)
        if observation.query_id != chosen.probe_id:
            raise ValueError('verifier returned wrong probe id')
        row=typed_prediction_row(chosen,atom_values_by_hypothesis)
        supports=update_proposal_supports(hypotheses,supports,observation,row)
        observed.add(chosen.probe_id); queries.append(chosen.probe_id); programs.append(chosen)
        reliabilities.append(observation.reliability); total_cost += chosen.execution_cost
        if chosen_macro is not None: macro_ids.append(chosen.probe_id)
        if chosen.depth>=3: recursive_ids.append(chosen.probe_id)
        top,margin=_rank(supports)
        if top.posterior>=float(accept_probability) and margin>=float(accept_margin):
            h=by_hypothesis[top.operator_id]
            if counterexample_check(h):
                return CalibratedRecursiveDecision('accept',h.operator_id,top.posterior,margin,tuple(queries),tuple(macro_ids),tuple(recursive_ids),tuple(programs),total_cost,raw_evals,macro_evals,tuple(routes),tuple(lcbs),tuple(reliabilities),'supported_hypothesis_survived_counterexample')
            return CalibratedRecursiveDecision('abstain',None,top.posterior,margin,tuple(queries),tuple(macro_ids),tuple(recursive_ids),tuple(programs),total_cost,raw_evals,macro_evals,tuple(routes),tuple(lcbs),tuple(reliabilities),'counterexample_rejected_top_hypothesis')
    top,margin=_rank(supports)
    return CalibratedRecursiveDecision('abstain',None,top.posterior,margin,tuple(queries),tuple(macro_ids),tuple(recursive_ids),tuple(programs),total_cost,raw_evals,macro_evals,tuple(routes),tuple(lcbs),tuple(reliabilities),'insufficient_identifiability_or_budget')
