from __future__ import annotations

import math
from dataclasses import dataclass, replace


def _unit(value: float, *, field: str) -> float:
    out = float(value)
    tolerance = 16.0 * math.ulp(1.0)
    if out < -tolerance or out > 1.0 + tolerance:
        raise ValueError(f"{field} must be in [0,1]")
    return min(1.0, max(0.0, out))


@dataclass(frozen=True)
class MacroCompetitionEvidence:
    reported_reliability: float
    semantic_alignment: float
    prediction_stability: float
    posterior_entropy: float
    posterior_margin: float
    information_gain: float
    relative_cost: float
    counterexample_survival: bool | None = None

    def __post_init__(self) -> None:
        reliability = float(self.reported_reliability)
        if not 0.5 < reliability <= 1.0:
            raise ValueError("reported_reliability must be in (0.5,1]")
        object.__setattr__(self, "reported_reliability", reliability)
        for name in (
            "semantic_alignment",
            "prediction_stability",
            "posterior_entropy",
            "posterior_margin",
            "information_gain",
            "relative_cost",
        ):
            object.__setattr__(self, name, _unit(getattr(self, name), field=name))
        if self.counterexample_survival not in (None, True, False):
            raise TypeError("counterexample_survival must be bool or None")


@dataclass(frozen=True)
class MacroCompetitionState:
    macro_id: str
    alpha: float = 2.0
    beta: float = 2.0
    semantic_alignment: float = 0.5
    semantic_conflicts: int = 0
    information_gain_history: tuple[float, ...] = ()
    cost_history: tuple[float, ...] = ()
    shock_count: int = 0
    quarantined: bool = False

    def __post_init__(self) -> None:
        if not str(self.macro_id):
            raise ValueError("macro_id must be non-empty")
        if float(self.alpha) <= 0 or float(self.beta) <= 0:
            raise ValueError("alpha and beta must be positive")
        object.__setattr__(self, "alpha", float(self.alpha))
        object.__setattr__(self, "beta", float(self.beta))
        object.__setattr__(self, "semantic_alignment", _unit(self.semantic_alignment, field="semantic_alignment"))
        if int(self.semantic_conflicts) < 0 or int(self.shock_count) < 0:
            raise ValueError("conflict and shock counts must be non-negative")
        object.__setattr__(self, "semantic_conflicts", int(self.semantic_conflicts))
        object.__setattr__(self, "shock_count", int(self.shock_count))
        object.__setattr__(self, "information_gain_history", tuple(float(x) for x in self.information_gain_history))
        object.__setattr__(self, "cost_history", tuple(float(x) for x in self.cost_history))


@dataclass(frozen=True)
class MacroCompetitionAssessment:
    route: str
    posterior_mean: float
    lower_confidence_bound: float
    evidence_quality: float
    score: float
    reason: str


def _evidence_quality(evidence: MacroCompetitionEvidence) -> float:
    quality = (
        0.20 * evidence.reported_reliability
        + 0.28 * evidence.semantic_alignment
        + 0.14 * evidence.prediction_stability
        + 0.10 * (1.0 - evidence.posterior_entropy)
        + 0.08 * evidence.posterior_margin
        + 0.14 * evidence.information_gain
        + 0.06 * (1.0 - evidence.relative_cost)
    )
    if evidence.counterexample_survival is True:
        quality += 0.04
    elif evidence.counterexample_survival is False:
        quality -= 0.20
    return min(1.0, max(0.0, quality))


def _beta_lcb(alpha: float, beta: float) -> tuple[float, float]:
    total = alpha + beta
    mean = alpha / total
    variance = (alpha * beta) / ((total * total) * (total + 1.0))
    return mean, max(0.0, mean - 1.28 * math.sqrt(variance))


def assess_competing_macro(
    state: MacroCompetitionState,
    evidence: MacroCompetitionEvidence,
    *,
    threshold: float = 0.60,
) -> MacroCompetitionAssessment:
    threshold = _unit(threshold, field="threshold")
    quality = _evidence_quality(evidence)
    alpha = state.alpha + 2.0 * quality
    beta = state.beta + 2.0 * (1.0 - quality)
    mean, lcb = _beta_lcb(alpha, beta)
    score = lcb + 0.08 * evidence.information_gain - 0.04 * evidence.relative_cost
    if state.quarantined:
        return MacroCompetitionAssessment("quarantined", mean, lcb, quality, score, "macro_quarantined")
    route = "macro" if lcb >= threshold else "defer_raw"
    reason = "macro_competition_supported" if route == "macro" else "macro_competition_uncertain"
    return MacroCompetitionAssessment(route, mean, lcb, quality, score, reason)


def update_macro_competition_state(
    state: MacroCompetitionState,
    evidence: MacroCompetitionEvidence,
) -> MacroCompetitionState:
    quality = _evidence_quality(evidence)
    semantic_conflict = evidence.reported_reliability >= 0.90 and evidence.semantic_alignment <= 0.20
    conflicts = state.semantic_conflicts + int(semantic_conflict)
    low_reliability_shock = evidence.reported_reliability <= 0.60
    counterexample_shock = evidence.counterexample_survival is False
    immediate_shock = low_reliability_shock or counterexample_shock
    quarantine = state.quarantined or immediate_shock or conflicts >= 2
    shocks = state.shock_count + int(immediate_shock or (semantic_conflict and conflicts >= 2))
    semantic_alignment = 0.7 * state.semantic_alignment + 0.3 * evidence.semantic_alignment
    return replace(
        state,
        alpha=state.alpha + quality,
        beta=state.beta + (1.0 - quality),
        semantic_alignment=semantic_alignment,
        semantic_conflicts=conflicts,
        information_gain_history=state.information_gain_history + (evidence.information_gain,),
        cost_history=state.cost_history + (evidence.relative_cost,),
        shock_count=shocks,
        quarantined=quarantine,
    )
