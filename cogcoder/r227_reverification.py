from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Sequence

from .r220_language_synthesis import OperatorProposal
from .r220_operator_discovery import ProposalSupport
from .r222_voi_types import VerifierRegime
from .r227_evidence_ledger import EvidenceLedger, LedgerObservation


@dataclass(frozen=True)
class CorrectionCandidate:
    observation_index: int
    query_id: str
    score: float
    influence: float
    ambiguity: float
    disagreement: float
    reliability_gap: float
    strong_cost: float


def _ranked(supports: Sequence[ProposalSupport]) -> tuple[ProposalSupport, ...]:
    return tuple(sorted(supports, key=lambda row: (-row.posterior, row.operator_id)))


def _likelihood(predicted: bool, row: LedgerObservation) -> float:
    return row.reliability if bool(predicted) == row.observed_label else 1.0 - row.reliability


def correction_value(
    proposals: Sequence[OperatorProposal],
    ledger: EvidenceLedger,
    supports: Sequence[ProposalSupport],
    observation: LedgerObservation,
    *,
    regime: VerifierRegime,
    complexity_weight: float,
) -> float:
    del ledger, complexity_weight  # interface reserves provenance/prior context without hidden target inputs
    proposals = tuple(proposals)
    supports = tuple(supports)
    if observation.superseded_by is not None or observation.channel != regime.cheap.name:
        return 0.0
    if set(observation.prediction_map) != {p.operator_id for p in proposals}:
        raise ValueError('prediction coverage mismatch')
    ranked = _ranked(supports)
    top = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    second_p = second.posterior if second is not None else 0.0
    margin = max(0.0, min(1.0, top.posterior - second_p))
    ambiguity = max(0.0, 1.0 - margin)

    posterior = {row.operator_id: row.posterior for row in supports}
    labels = observation.prediction_map
    p_true = sum(posterior[oid] for oid, label in labels.items() if bool(label))
    disagreement = max(0.0, 2.0 * p_true * (1.0 - p_true))

    influence = 0.0
    if second is not None:
        like_top = _likelihood(labels[top.operator_id], observation)
        like_second = _likelihood(labels[second.operator_id], observation)
        influence = abs(math.log(max(like_top, 1e-15)) - math.log(max(like_second, 1e-15)))

    reliability_gap = max(0.0, float(regime.strong.reliability) - float(observation.reliability))
    strong_cost = float(regime.strong.cost)
    return float(influence * ambiguity * disagreement * reliability_gap / strong_cost)


def rank_reverification_candidates(
    proposals: Sequence[OperatorProposal],
    ledger: EvidenceLedger,
    supports: Sequence[ProposalSupport],
    *,
    regime: VerifierRegime,
    complexity_weight: float,
) -> tuple[CorrectionCandidate, ...]:
    proposals = tuple(proposals)
    supports = tuple(supports)
    ranked_supports = _ranked(supports)
    top = ranked_supports[0]
    second = ranked_supports[1] if len(ranked_supports) > 1 else None
    margin = top.posterior - (second.posterior if second else 0.0)
    ambiguity = max(0.0, 1.0 - margin)
    posterior = {row.operator_id: row.posterior for row in supports}
    rows: list[CorrectionCandidate] = []
    for observation in ledger.entries:
        if observation.superseded_by is not None or observation.channel != regime.cheap.name:
            continue
        labels = observation.prediction_map
        if set(labels) != {p.operator_id for p in proposals}:
            raise ValueError('prediction coverage mismatch')
        p_true = sum(posterior[oid] for oid, label in labels.items() if bool(label))
        disagreement = max(0.0, 2.0 * p_true * (1.0 - p_true))
        influence = 0.0
        if second is not None:
            like_top = _likelihood(labels[top.operator_id], observation)
            like_second = _likelihood(labels[second.operator_id], observation)
            influence = abs(math.log(max(like_top, 1e-15)) - math.log(max(like_second, 1e-15)))
        gap = max(0.0, regime.strong.reliability - observation.reliability)
        score = correction_value(
            proposals, ledger, supports, observation,
            regime=regime, complexity_weight=complexity_weight,
        )
        rows.append(CorrectionCandidate(
            observation.observation_index,
            observation.query_id,
            score,
            influence,
            ambiguity,
            disagreement,
            gap,
            regime.strong.cost,
        ))
    return tuple(sorted(rows, key=lambda row: (-row.score, row.observation_index, row.query_id)))
