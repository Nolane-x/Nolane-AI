from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Sequence

from .r220_language_synthesis import OperatorProposal
from .r222_voi_types import VerifierRegime
from .r227_evidence_ledger import EvidenceLedger, LedgerObservation, replay_supports, supersede_observation
from .r228_trust_model import ReliabilityPosterior


@dataclass(frozen=True)
class BayesianProbeCandidate:
    observation_index: int
    query_id: str
    score: float
    expected_information_gain: float
    p_strong_agrees: float
    current_entropy: float
    expected_entropy_after: float
    strong_cost: float


def _posterior_entropy(supports) -> float:
    return -sum(float(row.posterior) * math.log(max(float(row.posterior), 1e-300)) for row in supports)


def _strong_agreement_probability(trust_posterior: ReliabilityPosterior, strong_reliability: float) -> float:
    s = float(strong_reliability)
    return sum(
        float(weight) * (float(q) * s + (1.0 - float(q)) * (1.0 - s))
        for q, weight in zip(trust_posterior.grid, trust_posterior.weights)
    )


def _counterfactual_entropy(
    proposals: Sequence[OperatorProposal],
    ledger: EvidenceLedger,
    observation: LedgerObservation,
    *,
    strong_observed_label: bool,
    regime: VerifierRegime,
    complexity_weight: float,
) -> float:
    replaced = supersede_observation(
        ledger,
        observation_index=observation.observation_index,
        observed_label=bool(strong_observed_label),
        reliability=regime.strong.reliability,
        channel=regime.strong.name,
        cost=regime.strong.cost,
    )
    return _posterior_entropy(
        replay_supports(proposals, replaced, complexity_weight=float(complexity_weight))
    )


def _candidate_value(
    proposals: Sequence[OperatorProposal],
    ledger: EvidenceLedger,
    observation: LedgerObservation,
    trust_posterior: ReliabilityPosterior,
    *,
    regime: VerifierRegime,
    complexity_weight: float,
    current_entropy: float,
) -> BayesianProbeCandidate:
    p_agree = _strong_agreement_probability(trust_posterior, regime.strong.reliability)
    h_agree = _counterfactual_entropy(
        proposals,
        ledger,
        observation,
        strong_observed_label=observation.observed_label,
        regime=regime,
        complexity_weight=complexity_weight,
    )
    h_disagree = _counterfactual_entropy(
        proposals,
        ledger,
        observation,
        strong_observed_label=not observation.observed_label,
        regime=regime,
        complexity_weight=complexity_weight,
    )
    expected_entropy = p_agree * h_agree + (1.0 - p_agree) * h_disagree
    information_gain = float(current_entropy - expected_entropy)
    cost = float(regime.strong.cost)
    return BayesianProbeCandidate(
        observation_index=observation.observation_index,
        query_id=observation.query_id,
        score=information_gain / cost,
        expected_information_gain=information_gain,
        p_strong_agrees=float(p_agree),
        current_entropy=float(current_entropy),
        expected_entropy_after=float(expected_entropy),
        strong_cost=cost,
    )


def rank_bayesian_probe_candidates(
    proposals: Sequence[OperatorProposal],
    ledger: EvidenceLedger,
    trust_posterior: ReliabilityPosterior,
    *,
    regime: VerifierRegime,
    complexity_weight: float,
) -> tuple[BayesianProbeCandidate, ...]:
    """Rank active cheap evidence by Bayesian strong-probe information value.

    This function is deliberately inference-only: its inputs contain the current
    proposal hypotheses, evidence ledger, verifier-trust posterior, and verifier
    economics. It does not receive task truth, target identity, seed, domain, or
    an evaluator's actual cheap reliability.
    """
    proposals = tuple(proposals)
    current_supports = replay_supports(
        proposals,
        ledger,
        complexity_weight=float(complexity_weight),
    )
    current_entropy = _posterior_entropy(current_supports)
    rows = []
    for observation in ledger.entries:
        if not observation.active or observation.channel != regime.cheap.name:
            continue
        rows.append(
            _candidate_value(
                proposals,
                ledger,
                observation,
                trust_posterior,
                regime=regime,
                complexity_weight=float(complexity_weight),
                current_entropy=current_entropy,
            )
        )
    return tuple(
        sorted(
            rows,
            key=lambda row: (-row.score, row.observation_index, row.query_id),
        )
    )
