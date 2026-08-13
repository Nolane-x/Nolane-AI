from __future__ import annotations

import hashlib
from dataclasses import dataclass

import torch
from torch import Tensor


@dataclass(frozen=True)
class CertificateCalibrationRow:
    family: str
    score: float
    prediction_mse: float


@dataclass(frozen=True)
class CertificateCalibrationResult:
    threshold: float
    precision: float
    coverage: float
    selected: int
    total: int
    family_precision: dict[str, float]


def certificate_scores_from_tensors(predicted_effects:Tensor,evidence_effects:Tensor,evidence_meta:Tensor,*,agreement_scale:float=32.0)->Tensor:
    if predicted_effects.shape!=evidence_effects.shape or predicted_effects.ndim!=3: raise ValueError('predicted/evidence effects must share [batch,actions,effect_dim]')
    if evidence_meta.shape!=predicted_effects.shape[:2]+(3,): raise ValueError('evidence_meta must have shape [batch,actions,3]')
    mse=(predicted_effects-evidence_effects).pow(2).mean(dim=-1); seen=evidence_meta[...,0].gt(0).to(predicted_effects.dtype); consistency=evidence_meta[...,1].clamp(0.0,1.0); context_similarity=evidence_meta[...,2].clamp(0.0,1.0); agreement=torch.exp(-float(agreement_scale)*mse)
    return seen*consistency*context_similarity*agreement


def _stable_action_tiebreak(description:str)->int: return int.from_bytes(hashlib.sha256(description.encode('utf-8')).digest()[:8],'big')

def select_experiment(action_descriptions,reliability_scores:Tensor,evidence_counts:Tensor)->int:
    descriptions=tuple(str(item) for item in action_descriptions)
    if reliability_scores.ndim!=1 or evidence_counts.ndim!=1: raise ValueError('scores/counts must be one-dimensional')
    if len(descriptions)!=reliability_scores.numel() or len(descriptions)!=evidence_counts.numel(): raise ValueError('action metadata length mismatch')
    candidates=[i for i,d in enumerate(descriptions) if 'submit' not in d.lower()]
    if not candidates: raise ValueError('no non-submit experiment action available')
    return min(candidates,key=lambda i:(int(evidence_counts[i].item()),float(reliability_scores[i].item()),_stable_action_tiebreak(descriptions[i])))


def calibrate_reliability_threshold(rows,*,thresholds=(0.5,0.6,0.7,0.8,0.9),acceptable_mse:float=0.005,required_precision:float=0.95)->CertificateCalibrationResult:
    rows=tuple(rows)
    if not rows: raise ValueError('calibration rows must not be empty')
    families=sorted({row.family for row in rows}); best=None
    for threshold in sorted({float(v) for v in thresholds}):
        selected=[row for row in rows if float(row.score)>=threshold]
        if not selected: continue
        precision=sum(float(row.prediction_mse)<=acceptable_mse for row in selected)/len(selected); family_precision={}; valid=precision>=required_precision
        for family in families:
            family_rows=[row for row in selected if row.family==family]
            if not family_rows: valid=False; family_precision[family]=0.0; continue
            value=sum(float(row.prediction_mse)<=acceptable_mse for row in family_rows)/len(family_rows); family_precision[family]=value; valid=valid and value>=required_precision
        if not valid: continue
        result=CertificateCalibrationResult(threshold,precision,len(selected)/len(rows),len(selected),len(rows),family_precision)
        if best is None or (result.coverage,result.threshold)>(best.coverage,best.threshold): best=result
    if best is None: raise RuntimeError('no reliability threshold satisfies the calibration constraints')
    return best
