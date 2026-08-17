from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


def _unit(value: float, *, field: str) -> float:
    out=float(value)
    if not 0.0 <= out <= 1.0:
        raise ValueError(f'{field} must be in [0,1]')
    return out


@dataclass(frozen=True)
class MacroApplicabilityEvidence:
    observed_reliabilities: tuple[float, ...]
    posterior_entropy: float
    posterior_margin: float
    macro_raw_agreement: float
    prediction_stability: float
    search_cost_ratio: float
    counterexample_survival: bool | None

    def __post_init__(self) -> None:
        rels=tuple(float(v) for v in self.observed_reliabilities)
        if any(not 0.5 < v <= 1.0 for v in rels):
            raise ValueError('observed_reliabilities must be in (0.5,1]')
        object.__setattr__(self,'observed_reliabilities',rels)
        for field in ('posterior_entropy','posterior_margin','macro_raw_agreement','prediction_stability','search_cost_ratio'):
            object.__setattr__(self,field,_unit(getattr(self,field),field=field))
        if self.counterexample_survival not in (None,True,False):
            raise TypeError('counterexample_survival must be bool or None')


@dataclass(frozen=True)
class MacroApplicabilityAssessment:
    route: str
    posterior_mean: float
    lower_confidence_bound: float
    evidence_quality: float
    effective_evidence: int
    reason: str


def assess_macro_applicability(
    evidence: MacroApplicabilityEvidence,
    *,
    threshold: float=.66,
) -> MacroApplicabilityAssessment:
    threshold=_unit(threshold,field='threshold')
    rels=evidence.observed_reliabilities or (0.75,)
    mean_rel=sum(rels)/len(rels)
    min_rel=min(rels)
    quality=(
        .30*mean_rel +
        .30*min_rel +
        .10*evidence.macro_raw_agreement +
        .10*evidence.prediction_stability +
        .05*(1.0-evidence.posterior_entropy) +
        .05*evidence.posterior_margin +
        .10*evidence.search_cost_ratio
    )
    if evidence.counterexample_survival is True:
        quality += .03
    elif evidence.counterexample_survival is False:
        quality -= .15
    quality=min(1.0,max(0.0,quality))

    # Fixed-strength Beta approximation. The cross-episode macro library is a
    # prior, while trajectory diagnostics decide whether reuse is currently safe.
    strength=10.0
    alpha=1.0+strength*quality
    beta=1.0+strength*(1.0-quality)
    mean=alpha/(alpha+beta)
    variance=(alpha*beta)/(((alpha+beta)**2)*(alpha+beta+1.0))
    lcb=max(0.0,mean-1.28*math.sqrt(variance))
    route='macro' if lcb >= threshold else 'defer_raw'
    reason='applicability_lcb_supported' if route=='macro' else 'applicability_uncertain_defer_raw'
    return MacroApplicabilityAssessment(route,mean,lcb,quality,len(evidence.observed_reliabilities),reason)
