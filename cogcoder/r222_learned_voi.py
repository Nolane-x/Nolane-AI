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
from .r222_counterfactual_trainer import ACTIONS, PolicyBundle
from .r222_voi_types import MetaState, VerifierRegime, extract_meta_features, expand_meta_features


@dataclass(frozen=True)
class LearnedVOIDecision:
    status: str
    operator_id: str | None
    posterior: float
    margin: float
    queries: tuple[str, ...]
    channels: tuple[str, ...]
    total_cost: float
    actions: tuple[str, ...]
    stop_reason: str


def _rank(supports: Sequence[ProposalSupport]) -> tuple[ProposalSupport, ...]:
    return tuple(sorted(supports, key=lambda s: (-s.posterior, s.operator_id)))


def _top_and_margin(supports: Sequence[ProposalSupport]) -> tuple[ProposalSupport, float]:
    ranked = _rank(supports)
    top = ranked[0]
    second = ranked[1].posterior if len(ranked) > 1 else 0.0
    return top, top.posterior - second


def _max_disagreement(supports, remaining, predictions) -> float:
    if not remaining:
        return 0.0
    post = {s.operator_id: s.posterior for s in supports}
    out = 0.0
    for q in remaining:
        p_true = sum(post[oid] for oid, label in predictions[q].items() if bool(label))
        out = max(out, 2.0 * p_true * (1.0 - p_true))
    return out


def _stop_decision(
    supports: Sequence[ProposalSupport],
    by_proposal: Mapping[str, OperatorProposal],
    *,
    counterexample_check: Callable[[OperatorProposal], bool],
    accept_probability: float,
    accept_margin: float,
    queries: Sequence[str],
    channels: Sequence[str],
    total_cost: float,
    actions: Sequence[str],
    fallback_reason: str,
) -> LearnedVOIDecision:
    top, margin = _top_and_margin(supports)
    if top.posterior >= float(accept_probability) and margin >= float(accept_margin):
        proposal = by_proposal[top.operator_id]
        if counterexample_check(proposal):
            return LearnedVOIDecision(
                'accept', proposal.operator_id, top.posterior, margin,
                tuple(queries), tuple(channels), float(total_cost), tuple(actions), 'accepted',
            )
        return LearnedVOIDecision(
            'abstain', None, top.posterior, margin,
            tuple(queries), tuple(channels), float(total_cost), tuple(actions),
            'counterexample_rejected_top_operator',
        )
    return LearnedVOIDecision(
        'abstain', None, top.posterior, margin,
        tuple(queries), tuple(channels), float(total_cost), tuple(actions), fallback_reason,
    )



def _terminal_decision_if_ready(
    supports: Sequence[ProposalSupport],
    by_proposal: Mapping[str, OperatorProposal],
    *,
    counterexample_check: Callable[[OperatorProposal], bool],
    accept_probability: float,
    accept_margin: float,
    queries: Sequence[str],
    channels: Sequence[str],
    total_cost: float,
    actions: Sequence[str],
) -> LearnedVOIDecision | None:
    top, margin = _top_and_margin(supports)
    if top.posterior < float(accept_probability) or margin < float(accept_margin):
        return None
    proposal = by_proposal[top.operator_id]
    if counterexample_check(proposal):
        return LearnedVOIDecision(
            'accept', proposal.operator_id, top.posterior, margin,
            tuple(queries), tuple(channels), float(total_cost), tuple(actions), 'accepted',
        )
    # A rejected current top is evidence that the episode is unresolved, not
    # proof that no recoverable hypothesis remains. Continue metareasoning while
    # evidence budget/value remains; policy STOP or hard-cap handling can still
    # abstain safely later.
    return None


def route_with_learned_voi(
    proposals: Sequence[OperatorProposal],
    query_ids: Sequence[str],
    predictions: Mapping[str, Mapping[str, bool]],
    *,
    regime: VerifierRegime,
    policy: PolicyBundle,
    verifier_by_channel: Mapping[str, Callable[[str], VerifierObservation]],
    counterexample_check: Callable[[OperatorProposal], bool],
    max_queries: int,
    accept_probability: float,
    accept_margin: float,
    max_mdl_cost: int,
    complexity_weight: float,
) -> LearnedVOIDecision:
    proposals = tuple(p for p in proposals if p.mdl_cost <= int(max_mdl_cost))
    if not proposals:
        return LearnedVOIDecision('abstain', None, 0.0, 0.0, (), (), 0.0, (), 'no_proposals_within_complexity_budget')
    if set(policy.models) != set(ACTIONS):
        raise ValueError('policy action coverage mismatch')
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
    total_cost = 0.0

    while True:
        terminal = _terminal_decision_if_ready(
            supports, by_proposal, counterexample_check=counterexample_check,
            accept_probability=accept_probability, accept_margin=accept_margin,
            queries=queries, channels=channels, total_cost=total_cost, actions=actions,
        )
        if terminal is not None:
            return terminal

        if len(queries) >= max_queries or not remaining:
            return _stop_decision(
                supports, by_proposal, counterexample_check=counterexample_check,
                accept_probability=accept_probability, accept_margin=accept_margin,
                queries=queries, channels=channels, total_cost=total_cost, actions=actions,
                fallback_reason='hard_cap_or_evidence_exhausted',
            )

        state = MetaState(
            supports=tuple(supports),
            max_remaining_disagreement=_max_disagreement(supports, remaining, predictions),
            queries_used=len(queries),
            max_queries=max(max_queries, 1),
            remaining_queries=len(remaining),
            accumulated_cost=total_cost,
            cheap=regime.cheap,
            strong=regime.strong,
        )
        features = expand_meta_features(extract_meta_features(state))
        values = {action: policy.models[action].predict(features) for action in ACTIONS}
        action = max(ACTIONS, key=lambda a: (values[a], -ACTIONS.index(a)))
        actions.append(action)

        if action == 'stop':
            return _stop_decision(
                supports, by_proposal, counterexample_check=counterexample_check,
                accept_probability=accept_probability, accept_margin=accept_margin,
                queries=queries, channels=channels, total_cost=total_cost, actions=actions,
                fallback_reason='policy_stop_without_identifiability',
            )

        channel = regime.cheap if action == 'cheap' else regime.strong
        q = choose_operator_query(proposals, supports, remaining, predictions)
        observation = verifier_by_channel[channel.name](q)
        if observation.query_id != q:
            raise ValueError('verifier returned wrong query')
        if abs(observation.reliability - channel.reliability) > 1e-12:
            raise ValueError('verifier reliability does not match channel contract')
        supports = update_proposal_supports(proposals, supports, observation, predictions[q])
        queries.append(q)
        channels.append(channel.name)
        total_cost += channel.cost
        remaining.remove(q)
