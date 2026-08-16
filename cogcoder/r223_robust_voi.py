from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Mapping, Sequence

from .r219_representation_types import VerifierObservation
from .r220_language_synthesis import OperatorProposal
from .r220_operator_discovery import (
    ProposalSupport,
    choose_operator_query,
    initial_proposal_supports,
    update_proposal_supports,
)
from .r222_voi_types import VerifierRegime
from .r223_information_anchor import expected_channel_information
from .r223_pairwise_regret import PairwiseRegretEnsemble, _pairwise_features


@dataclass(frozen=True)
class RobustVOIDecision:
    status: str
    operator_id: str | None
    posterior: float
    margin: float
    queries: tuple[str, ...]
    channels: tuple[str, ...]
    total_cost: float
    actions: tuple[str, ...]
    cheap_q25: tuple[float, ...]
    stop_q25: tuple[float, ...]
    analytic_preference: tuple[str, ...]
    stop_reason: str


def _rank(supports: Sequence[ProposalSupport]) -> tuple[ProposalSupport, ...]:
    return tuple(sorted(supports, key=lambda row: (-row.posterior, row.operator_id)))


def _top_margin(supports: Sequence[ProposalSupport]) -> tuple[ProposalSupport, float]:
    ranked = _rank(supports)
    top = ranked[0]
    second = ranked[1].posterior if len(ranked) > 1 else 0.0
    return top, top.posterior - second


def _decision(
    *,
    status: str,
    operator_id: str | None,
    supports: Sequence[ProposalSupport],
    queries: Sequence[str],
    channels: Sequence[str],
    total_cost: float,
    actions: Sequence[str],
    cheap_q25: Sequence[float],
    stop_q25: Sequence[float],
    analytic_preference: Sequence[str],
    stop_reason: str,
) -> RobustVOIDecision:
    top, margin = _top_margin(supports)
    return RobustVOIDecision(
        status=status,
        operator_id=operator_id,
        posterior=float(top.posterior),
        margin=float(margin),
        queries=tuple(queries),
        channels=tuple(channels),
        total_cost=float(total_cost),
        actions=tuple(actions),
        cheap_q25=tuple(float(v) for v in cheap_q25),
        stop_q25=tuple(float(v) for v in stop_q25),
        analytic_preference=tuple(str(v) for v in analytic_preference),
        stop_reason=str(stop_reason),
    )


def route_with_robust_voi(
    proposals: Sequence[OperatorProposal],
    query_ids: Sequence[str],
    predictions: Mapping[str, Mapping[str, bool]],
    *,
    regime: VerifierRegime,
    ensemble: PairwiseRegretEnsemble,
    verifier_by_channel: Mapping[str, Callable[[str], VerifierObservation]],
    counterexample_check: Callable[[OperatorProposal], bool],
    max_queries: int,
    accept_probability: float,
    accept_margin: float,
    max_mdl_cost: int,
    complexity_weight: float,
    require_analytic_anchor: bool = True,
    use_lower_quartile_guard: bool = True,
) -> RobustVOIDecision:
    proposals = tuple(p for p in proposals if p.mdl_cost <= int(max_mdl_cost))
    if not proposals:
        raise ValueError('proposals must contain at least one operator within the complexity budget')
    if set(verifier_by_channel) != {regime.cheap.name, regime.strong.name}:
        raise ValueError('verifier channel coverage mismatch')
    by_proposal = {p.operator_id: p for p in proposals}
    supports = initial_proposal_supports(proposals, complexity_weight=float(complexity_weight))
    remaining = list(dict.fromkeys(map(str, query_ids)))
    max_queries = min(int(max_queries), len(remaining))
    if max_queries < 0:
        raise ValueError('max_queries must be non-negative')

    queries: list[str] = []
    channels: list[str] = []
    actions: list[str] = []
    cheap_trace: list[float] = []
    stop_trace: list[float] = []
    anchor_trace: list[str] = []
    total_cost = 0.0

    while True:
        top, margin = _top_margin(supports)
        if top.posterior >= float(accept_probability) and margin >= float(accept_margin):
            proposal = by_proposal[top.operator_id]
            if counterexample_check(proposal):
                return _decision(
                    status='accept', operator_id=proposal.operator_id, supports=supports,
                    queries=queries, channels=channels, total_cost=total_cost, actions=actions,
                    cheap_q25=cheap_trace, stop_q25=stop_trace, analytic_preference=anchor_trace,
                    stop_reason='accepted',
                )
            # Counterexample rejection means the current top is not terminal.
            # Continue collecting evidence while the hard budget permits.

        if len(queries) >= max_queries or not remaining:
            return _decision(
                status='abstain', operator_id=None, supports=supports,
                queries=queries, channels=channels, total_cost=total_cost, actions=actions,
                cheap_q25=cheap_trace, stop_q25=stop_trace, analytic_preference=anchor_trace,
                stop_reason='hard_cap_or_evidence_exhausted',
            )

        features = _pairwise_features(
            supports,
            remaining,
            predictions,
            queries_used=len(queries),
            max_queries=max(max_queries, 1),
            accumulated_cost=total_cost,
            regime=regime,
        )
        cheap_dist = ensemble.advantage_distribution(features, 'cheap_minus_strong')
        stop_dist = ensemble.advantage_distribution(features, 'stop_minus_strong')
        cheap_trace.append(float(cheap_dist.q25))
        stop_trace.append(float(stop_dist.q25))

        q = choose_operator_query(proposals, supports, remaining, predictions)
        labels = predictions[q]
        cheap_info = expected_channel_information(
            supports, labels, reliability=regime.cheap.reliability, cost=regime.cheap.cost,
        )
        strong_info = expected_channel_information(
            supports, labels, reliability=regime.strong.reliability, cost=regime.strong.cost,
        )
        cheap_anchor_ok = cheap_info.information_per_cost >= strong_info.information_per_cost
        anchor_trace.append('cheap' if cheap_anchor_ok else 'strong')

        stop_advantage = stop_dist.q25 if use_lower_quartile_guard else stop_dist.mean
        cheap_advantage = cheap_dist.q25 if use_lower_quartile_guard else cheap_dist.mean

        if stop_advantage > 0.0:
            actions.append('stop')
            # The frozen correctness gate above is the only acceptance authority.
            return _decision(
                status='abstain', operator_id=None, supports=supports,
                queries=queries, channels=channels, total_cost=total_cost, actions=actions,
                cheap_q25=cheap_trace, stop_q25=stop_trace, analytic_preference=anchor_trace,
                stop_reason='robust_stop_without_identifiability',
            )

        if cheap_advantage > 0.0 and (cheap_anchor_ok or not require_analytic_anchor):
            action = 'cheap'
            channel = regime.cheap
        else:
            action = 'strong'
            channel = regime.strong
        actions.append(action)

        observation = verifier_by_channel[channel.name](q)
        if observation.query_id != q:
            raise ValueError('verifier returned wrong query')
        if abs(float(observation.reliability) - float(channel.reliability)) > 1e-12:
            raise ValueError('verifier reliability does not match channel contract')
        supports = update_proposal_supports(proposals, supports, observation, predictions[q])
        queries.append(q)
        channels.append(channel.name)
        total_cost += channel.cost
        remaining.remove(q)
