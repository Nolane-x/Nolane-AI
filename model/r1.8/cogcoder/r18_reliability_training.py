from __future__ import annotations
from dataclasses import dataclass
import torch
from torch import Tensor

@dataclass(frozen=True)
class ReliabilityTrainingRow:
    family:str; score:float; prediction_mse:float
@dataclass(frozen=True)
class LearnedCertificateResult:
    threshold:float; precision:float; coverage:float; selected:int; total:int; family_precision:dict[str,float]; family_coverage:dict[str,float]

def reliability_trainable_parameter_names(model)->list[str]:
    allowed={'conditional_law_confidence_head.weight','conditional_law_confidence_head.bias'}; names=[n for n,_ in model.named_parameters() if n in allowed]
    if set(names)!=allowed: raise ValueError('model does not expose the expected conditional-law confidence head')
    return names

def learned_certificate_scores(confidence:Tensor,evidence_meta:Tensor)->Tensor:
    if confidence.ndim!=2: raise ValueError('confidence must have shape [batch,actions]')
    if evidence_meta.shape!=confidence.shape+(3,): raise ValueError('evidence_meta must have shape [batch,actions,3]')
    seen=evidence_meta[...,0].gt(0).to(confidence.dtype); consistency=evidence_meta[...,1].clamp(0.,1.); context_similarity=evidence_meta[...,2].clamp(0.,1.)
    return seen*consistency*context_similarity*confidence.clamp(0.,1.)

def calibrate_learned_certificate(rows,*,thresholds,acceptable_mse:float,required_precision:float,min_coverage:float,min_family_coverage:float)->LearnedCertificateResult:
    rows=tuple(rows)
    if not rows: raise ValueError('rows must not be empty')
    families=sorted({r.family for r in rows}); totals={f:sum(r.family==f for r in rows) for f in families}; best=None
    for threshold in sorted({float(v) for v in thresholds}):
        chosen=[r for r in rows if float(r.score)>=threshold]
        if not chosen: continue
        precision=sum(float(r.prediction_mse)<=acceptable_mse for r in chosen)/len(chosen); coverage=len(chosen)/len(rows); fp={}; fc={}; valid=precision>=required_precision and coverage>=min_coverage
        for family in families:
            rows_f=[r for r in chosen if r.family==family]; fc[family]=len(rows_f)/max(1,totals[family])
            if not rows_f: fp[family]=0.; valid=False; continue
            fp[family]=sum(float(r.prediction_mse)<=acceptable_mse for r in rows_f)/len(rows_f); valid=valid and fp[family]>=required_precision and fc[family]>=min_family_coverage
        if not valid: continue
        result=LearnedCertificateResult(threshold,precision,coverage,len(chosen),len(rows),fp,fc)
        if best is None or (result.coverage,result.threshold)>(best.coverage,best.threshold): best=result
    if best is None: raise RuntimeError('no learned reliability threshold satisfies precision/coverage constraints')
    return best
