from __future__ import annotations

import math
from dataclasses import dataclass, replace


def _unit(value: float, *, field: str) -> float:
    out=float(value)
    if not 0.0 <= out <= 1.0:
        raise ValueError(f'{field} must be in [0,1]')
    return out


@dataclass(frozen=True)
class MacroCompetitionEvidence:
    reported_reliability: float
    posterior_entropy_before: float
    posterior_entropy_after: float
    posterior_margin_before: float
    posterior_margin_after: float
    macro_raw_agreement: float
    prediction_stability: float
    relative_search_efficiency: float
    counterexample_survival: bool | None
    cross_check_conflict: float = 0.0
    executed_by_macro: bool = True

    def __post_init__(self) -> None:
        reliability=float(self.reported_reliability)
        if not 0.5 <= reliability <= 1.0:
            raise ValueError('reported_reliability must be in [0.5,1]')
        object.__setattr__(self,'reported_reliability',reliability)
        for field in (
            'posterior_entropy_before','posterior_entropy_after',
            'posterior_margin_before','posterior_margin_after',
            'macro_raw_agreement','prediction_stability','relative_search_efficiency','cross_check_conflict',
        ):
            object.__setattr__(self,field,_unit(getattr(self,field),field=field))
        if self.counterexample_survival not in (None,True,False):
            raise TypeError('counterexample_survival must be bool or None')
        if not isinstance(self.executed_by_macro,bool):
            raise TypeError('executed_by_macro must be bool')


@dataclass(frozen=True)
class MacroCompetitionState:
    macro_id: str
    alpha: float = 2.0
    beta: float = 2.0
    evidence_count: int = 0
    semantic_alignment: float = 0.5
    information_gain_sum: float = 0.0
    execution_efficiency_sum: float = 0.0
    semantic_shocks: int = 0
    quarantined: bool = False
    quarantine_reason: str | None = None

    def __post_init__(self) -> None:
        if not str(self.macro_id).strip():
            raise ValueError('macro_id must be non-empty')
        if float(self.alpha) <= 0 or float(self.beta) <= 0:
            raise ValueError('alpha and beta must be positive')
        if int(self.evidence_count) < 0 or int(self.semantic_shocks) < 0:
            raise ValueError('counts must be non-negative')
        object.__setattr__(self,'macro_id',str(self.macro_id))
        object.__setattr__(self,'alpha',float(self.alpha))
        object.__setattr__(self,'beta',float(self.beta))
        object.__setattr__(self,'evidence_count',int(self.evidence_count))
        object.__setattr__(self,'semantic_alignment',_unit(self.semantic_alignment,field='semantic_alignment'))
        object.__setattr__(self,'information_gain_sum',max(0.0,float(self.information_gain_sum)))
        object.__setattr__(self,'execution_efficiency_sum',max(0.0,float(self.execution_efficiency_sum)))
        object.__setattr__(self,'semantic_shocks',int(self.semantic_shocks))
        if self.quarantined and not self.quarantine_reason:
            raise ValueError('quarantined state requires a reason')


@dataclass(frozen=True)
class MacroCompetitionAssessment:
    macro_id: str
    posterior_mean: float
    lower_confidence_bound: float
    eligible: bool
    evidence_count: int
    semantic_alignment: float
    reason: str


def assess_competing_macro(
    state: MacroCompetitionState,
    *,
    support_floor: float=.58,
) -> MacroCompetitionAssessment:
    support_floor=_unit(support_floor,field='support_floor')
    total=state.alpha+state.beta
    mean=state.alpha/total
    variance=(state.alpha*state.beta)/((total*total)*(total+1.0))
    lcb=max(0.0,mean-1.28*math.sqrt(variance))
    eligible=(not state.quarantined) and state.evidence_count>0 and lcb>=support_floor
    if state.quarantined:
        reason='macro_quarantined'
    elif state.evidence_count==0:
        reason='insufficient_macro_evidence'
    elif lcb<support_floor:
        reason='applicability_lcb_below_floor'
    else:
        reason='macro_supported'
    return MacroCompetitionAssessment(
        state.macro_id,mean,lcb,eligible,state.evidence_count,state.semantic_alignment,reason,
    )


def update_macro_competition_state(
    state: MacroCompetitionState,
    evidence: MacroCompetitionEvidence,
) -> MacroCompetitionState:
    if state.quarantined:
        return state

    entropy_gain=max(0.0,evidence.posterior_entropy_before-evidence.posterior_entropy_after)
    margin_gain=max(0.0,evidence.posterior_margin_after-evidence.posterior_margin_before)
    credit=1.0 if evidence.executed_by_macro else 0.0
    normalized_information=min(1.0,3.0*entropy_gain)*credit
    normalized_margin=min(1.0,3.0*margin_gain)*credit
    quality=(
        .20*evidence.reported_reliability +
        .25*evidence.macro_raw_agreement +
        .15*evidence.prediction_stability +
        .15*normalized_information +
        .15*normalized_margin +
        .10*evidence.relative_search_efficiency
    )
    if evidence.counterexample_survival is True:
        quality += .04
    elif evidence.counterexample_survival is False:
        quality -= .18
    quality=max(0.0,min(1.0,quality))

    alpha=state.alpha+4.0*quality
    beta=state.beta+4.0*(1.0-quality)
    shocks=state.semantic_shocks
    quarantine_reason=None

    cross_check_reversal=evidence.reported_reliability >= .95 and evidence.cross_check_conflict >= .70
    semantic_mismatch=(
        evidence.reported_reliability >= .95 and
        evidence.macro_raw_agreement <= .30 and
        normalized_information <= .10 and
        normalized_margin <= .10
    )
    low_reliability=evidence.reported_reliability < .65
    if cross_check_reversal:
        shocks += 1
        beta += 3.5
        quarantine_reason='cross_check_reversal'
    elif semantic_mismatch:
        shocks += 1
        beta += 3.0
        quarantine_reason='semantic_mismatch'
    elif low_reliability:
        shocks += 1
        beta += 2.0
        quarantine_reason='verifier_trust_shock'

    n=state.evidence_count
    alignment=(state.semantic_alignment*n+evidence.macro_raw_agreement)/(n+1)
    decisive_cross_check=bool(cross_check_reversal and evidence.cross_check_conflict >= .95)
    quarantined=bool(shocks>=2 or decisive_cross_check)
    if not quarantined:
        quarantine_reason=None

    return replace(
        state,
        alpha=alpha,
        beta=beta,
        evidence_count=n+1,
        semantic_alignment=alignment,
        information_gain_sum=state.information_gain_sum+entropy_gain+margin_gain,
        execution_efficiency_sum=state.execution_efficiency_sum+evidence.relative_search_efficiency,
        semantic_shocks=shocks,
        quarantined=quarantined,
        quarantine_reason=quarantine_reason,
    )
