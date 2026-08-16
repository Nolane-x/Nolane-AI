from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from .r219_representation_types import VerifierObservation
from .r220_language_synthesis import OperatorProposal
from .r220_operator_discovery import (
    ProposalSupport,
    choose_operator_query,
    initial_proposal_supports,
    update_proposal_supports,
)


@dataclass(frozen=True)
class AdaptiveEvidenceDecision:
    status: str
    operator_id: str | None
    posterior: float
    margin: float
    mdl_cost: int | None
    queries: tuple[str, ...]
    base_budget: int
    max_budget: int
    extended: bool
    stop_reason: str
    remaining_max_disagreement: float


def _rank(supports: Sequence[ProposalSupport]) -> tuple[ProposalSupport, ...]:
    return tuple(sorted(supports, key=lambda row: (-row.posterior, row.operator_id)))


def _margin(supports: Sequence[ProposalSupport]) -> tuple[ProposalSupport, float]:
    ranked = _rank(supports)
    top = ranked[0]
    second = ranked[1].posterior if len(ranked) > 1 else 0.0
    return top, top.posterior - second


def _query_disagreement(
    q: str,
    supports: Sequence[ProposalSupport],
    predictions: Mapping[str, Mapping[str, bool]],
) -> float:
    posterior = {row.operator_id: row.posterior for row in supports}
    p_true = sum(posterior[oid] for oid, label in predictions[q].items() if bool(label))
    return 2.0 * p_true * (1.0 - p_true)


def _max_remaining_disagreement(
    remaining: Sequence[str],
    supports: Sequence[ProposalSupport],
    predictions: Mapping[str, Mapping[str, bool]],
) -> float:
    if not remaining:
        return 0.0
    return max(_query_disagreement(q, supports, predictions) for q in remaining)


def discover_operator_adaptive(
    proposals: Sequence[OperatorProposal],
    query_ids: Sequence[str],
    predictions: Mapping[str, Mapping[str, bool]],
    *,
    verifier: Callable[[str], VerifierObservation],
    counterexample_check: Callable[[OperatorProposal], bool],
    base_budget: int,
    max_budget: int,
    accept_probability: float,
    accept_margin: float,
    max_mdl_cost: int,
    complexity_weight: float,
    continuation_min_disagreement: float,
    recoverability_floor: float,
) -> AdaptiveEvidenceDecision:
    """Sequentially acquire evidence, extending past a base budget only when useful.

    The policy is deliberately conservative: it can stop before the base budget on a
    fully justified acceptance, but after the base budget it spends another query only
    if unresolved hypotheses still disagree and the live top hypothesis retains enough
    posterior mass to be recoverable.
    """
    base_budget = int(base_budget)
    max_budget = int(max_budget)
    if base_budget < 1 or max_budget < base_budget:
        raise ValueError('budgets must satisfy 1 <= base_budget <= max_budget')

    proposals = tuple(p for p in proposals if p.mdl_cost <= int(max_mdl_cost))
    if not proposals:
        return AdaptiveEvidenceDecision(
            'abstain', None, 0.0, 0.0, None, (), base_budget, max_budget,
            False, 'no_proposals_within_complexity_budget', 0.0,
        )
    by_proposal = {p.operator_id: p for p in proposals}
    supports = initial_proposal_supports(proposals, complexity_weight=float(complexity_weight))
    remaining = list(dict.fromkeys(map(str, query_ids)))
    queried: list[str] = []
    max_queries = min(max_budget, len(remaining))

    while len(queried) < max_queries and remaining:
        q = choose_operator_query(proposals, supports, remaining, predictions)
        obs = verifier(q)
        if obs.query_id != q:
            raise ValueError('verifier returned wrong query')
        supports = update_proposal_supports(proposals, supports, obs, predictions[q])
        queried.append(q)
        remaining.remove(q)

        top, margin = _margin(supports)
        if top.posterior >= float(accept_probability) and margin >= float(accept_margin):
            proposal = by_proposal[top.operator_id]
            if counterexample_check(proposal):
                return AdaptiveEvidenceDecision(
                    'accept', proposal.operator_id, top.posterior, margin, proposal.mdl_cost,
                    tuple(queried), base_budget, max_budget, len(queried) > base_budget,
                    'accepted', _max_remaining_disagreement(remaining, supports, predictions),
                )
            return AdaptiveEvidenceDecision(
                'abstain', None, top.posterior, margin, proposal.mdl_cost,
                tuple(queried), base_budget, max_budget, len(queried) > base_budget,
                'counterexample_rejected_top_operator',
                _max_remaining_disagreement(remaining, supports, predictions),
            )

        if len(queried) >= base_budget:
            voi = _max_remaining_disagreement(remaining, supports, predictions)
            if not remaining or voi < float(continuation_min_disagreement):
                return AdaptiveEvidenceDecision(
                    'abstain', None, top.posterior, margin, by_proposal[top.operator_id].mdl_cost,
                    tuple(queried), base_budget, max_budget, len(queried) > base_budget,
                    'low_value_of_information', voi,
                )
            if top.posterior < float(recoverability_floor):
                return AdaptiveEvidenceDecision(
                    'abstain', None, top.posterior, margin, by_proposal[top.operator_id].mdl_cost,
                    tuple(queried), base_budget, max_budget, len(queried) > base_budget,
                    'posterior_not_recoverable', voi,
                )

    top, margin = _margin(supports)
    return AdaptiveEvidenceDecision(
        'abstain', None, top.posterior, margin, by_proposal[top.operator_id].mdl_cost,
        tuple(queried), base_budget, max_budget, len(queried) > base_budget,
        'max_budget_exhausted' if len(queried) >= max_budget else 'evidence_exhausted',
        _max_remaining_disagreement(remaining, supports, predictions),
    )
