from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .r219_representation_types import VerifierObservation
from .r220_language_synthesis import OperatorProposal
from .r220_operator_discovery import ProposalSupport, initial_proposal_supports, update_proposal_supports
from .r222_voi_types import VerifierRegime
from .r227_evidence_ledger import EvidenceLedger, replay_supports, supersede_observation
from .r228_trust_model import ReliabilityPosterior


@dataclass(frozen=True)
class LOOCorrectionCandidate:
    observation_index: int
    query_id: str
    score: float
    loo_same_label_mass: float
    p_old_label_correct: float
    p_strong_agrees: float
    current_selected_operator_id: str
    current_reference_loss: float
    agree_selected_operator_id: str
    disagree_selected_operator_id: str
    expected_reference_loss_after: float
    expected_error_reduction: float
    strong_cost: float


def _ranked(supports: Sequence[ProposalSupport]) -> tuple[ProposalSupport, ...]:
    return tuple(sorted(supports, key=lambda row: (-row.posterior, row.operator_id)))


def _selected_operator_id(supports: Sequence[ProposalSupport]) -> str:
    ranked = _ranked(supports)
    if not ranked:
        raise ValueError('supports must be non-empty')
    return ranked[0].operator_id


def replay_supports_excluding(
    proposals: Sequence[OperatorProposal],
    ledger: EvidenceLedger,
    *,
    observation_index: int,
    complexity_weight: float,
) -> tuple[ProposalSupport, ...]:
    """Replay active evidence while withholding exactly one ledger observation.

    This is the leave-one-out reference used by R2.31.  It deliberately uses
    the same proposal-update semantics as the ordinary ledger replay; the only
    intervention is omission of the candidate observation itself.
    """
    proposals = tuple(proposals)
    idx = int(observation_index)
    if idx < 0 or idx >= len(ledger.entries):
        raise ValueError('observation_index out of range')
    proposal_ids = {proposal.operator_id for proposal in proposals}
    supports = initial_proposal_supports(proposals, complexity_weight=float(complexity_weight))
    for row in ledger.entries:
        if not row.active or row.observation_index == idx:
            continue
        labels = row.prediction_map
        if set(labels) != proposal_ids:
            raise ValueError('prediction coverage mismatch')
        supports = update_proposal_supports(
            proposals,
            supports,
            VerifierObservation(row.query_id, row.observed_label, row.reliability),
            labels,
        )
    return supports


def _reference_loss(selected_operator_id: str, reference_mass: dict[str, float]) -> float:
    try:
        mass = reference_mass[selected_operator_id]
    except KeyError as exc:
        raise ValueError('selected operator missing from reference posterior') from exc
    return 1.0 - float(mass)


def _counterfactual_selected_operator(
    proposals: Sequence[OperatorProposal],
    ledger: EvidenceLedger,
    *,
    observation_index: int,
    observed_label: bool,
    regime: VerifierRegime,
    complexity_weight: float,
) -> str:
    replaced = supersede_observation(
        ledger,
        observation_index=observation_index,
        observed_label=bool(observed_label),
        reliability=regime.strong.reliability,
        channel=regime.strong.name,
        cost=regime.strong.cost,
    )
    supports = replay_supports(proposals, replaced, complexity_weight=float(complexity_weight))
    return _selected_operator_id(supports)


def rank_loo_correction_candidates(
    proposals: Sequence[OperatorProposal],
    ledger: EvidenceLedger,
    trust_posterior: ReliabilityPosterior,
    *,
    regime: VerifierRegime,
    complexity_weight: float,
) -> tuple[LOOCorrectionCandidate, ...]:
    """Rank active cheap evidence by expected downstream correction value.

    Each candidate is withheld to build a cross-evidence reference posterior.
    That posterior and the verifier-trust posterior jointly estimate whether
    the old cheap label is correct.  We then simulate the two possible strong
    outcomes and value the probe by expected reduction in 0-1 Bayes decision
    loss under the leave-one-out reference, divided by strong-verifier cost.

    No target truth, seed, domain identifier, held-out flag, or actual verifier
    reliability is consumed by this function.
    """
    proposals = tuple(proposals)
    if not proposals:
        raise ValueError('proposals must be non-empty')
    qbar = float(trust_posterior.posterior_mean())
    strong_reliability = float(regime.strong.reliability)
    strong_cost = float(regime.strong.cost)
    current_supports = replay_supports(proposals, ledger, complexity_weight=float(complexity_weight))
    current_selected = _selected_operator_id(current_supports)

    rows: list[LOOCorrectionCandidate] = []
    for observation in ledger.entries:
        if not observation.active or observation.channel != regime.cheap.name:
            continue

        loo_supports = replay_supports_excluding(
            proposals,
            ledger,
            observation_index=observation.observation_index,
            complexity_weight=float(complexity_weight),
        )
        loo_mass = {row.operator_id: float(row.posterior) for row in loo_supports}
        predictions = observation.prediction_map
        p_same = sum(
            loo_mass[operator_id]
            for operator_id, predicted_label in predictions.items()
            if bool(predicted_label) == observation.observed_label
        )

        numerator = p_same * qbar
        denominator = numerator + (1.0 - p_same) * (1.0 - qbar)
        if denominator <= 0.0:
            raise ValueError('degenerate old-label correctness posterior')
        p_old_correct = numerator / denominator
        p_strong_agrees = (
            p_old_correct * strong_reliability
            + (1.0 - p_old_correct) * (1.0 - strong_reliability)
        )

        agree_selected = _counterfactual_selected_operator(
            proposals,
            ledger,
            observation_index=observation.observation_index,
            observed_label=observation.observed_label,
            regime=regime,
            complexity_weight=float(complexity_weight),
        )
        disagree_selected = _counterfactual_selected_operator(
            proposals,
            ledger,
            observation_index=observation.observation_index,
            observed_label=not observation.observed_label,
            regime=regime,
            complexity_weight=float(complexity_weight),
        )

        current_loss = _reference_loss(current_selected, loo_mass)
        agree_loss = _reference_loss(agree_selected, loo_mass)
        disagree_loss = _reference_loss(disagree_selected, loo_mass)
        expected_after = p_strong_agrees * agree_loss + (1.0 - p_strong_agrees) * disagree_loss
        expected_reduction = current_loss - expected_after
        score = expected_reduction / strong_cost

        rows.append(
            LOOCorrectionCandidate(
                observation_index=observation.observation_index,
                query_id=observation.query_id,
                score=float(score),
                loo_same_label_mass=float(p_same),
                p_old_label_correct=float(p_old_correct),
                p_strong_agrees=float(p_strong_agrees),
                current_selected_operator_id=current_selected,
                current_reference_loss=float(current_loss),
                agree_selected_operator_id=agree_selected,
                disagree_selected_operator_id=disagree_selected,
                expected_reference_loss_after=float(expected_after),
                expected_error_reduction=float(expected_reduction),
                strong_cost=strong_cost,
            )
        )

    return tuple(sorted(rows, key=lambda row: (-row.score, row.observation_index, row.query_id)))
