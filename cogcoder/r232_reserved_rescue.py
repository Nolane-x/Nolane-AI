from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from .r219_representation_types import VerifierObservation
from .r220_language_synthesis import OperatorProposal
from .r220_operator_discovery import choose_operator_query, initial_proposal_supports, update_proposal_supports
from .r222_counterfactual_trainer import ACTIONS, PolicyBundle
from .r222_learned_voi import _max_disagreement, _stop_decision, _terminal_decision_if_ready
from .r222_voi_types import MetaState, VerifierRegime, expand_meta_features, extract_meta_features
from .r227_evidence_ledger import EvidenceLedger, append_observation, replay_supports, supersede_observation
from .r228_trust_model import ReliabilityPosterior, update_reliability_from_agreement
from .r231_loo_probe_rescue import LOOProbeRescueDecision, route_with_loo_probe_rescue, select_probe_observation


@dataclass(frozen=True)
class ReservedRescueDecision:
    status: str
    operator_id: str | None
    posterior: float
    margin: float
    queries: tuple[str, ...]
    channels: tuple[str, ...]
    total_cost: float
    actions: tuple[str, ...]
    stop_reason: str
    escalated: bool
    escalation_at_query: int | None
    reverification_count: int
    reverified_queries: tuple[str, ...]
    selection_mode: str
    ledger: EvidenceLedger
    trust_posterior: ReliabilityPosterior
    reserve_calls: int
    point_prefix_limit: int
    point_policy_horizon: int
    reserve_triggered: bool


def _wrap_parent(
    parent: LOOProbeRescueDecision,
    *,
    reserve_calls: int,
    point_prefix_limit: int,
    point_policy_horizon: int,
    reserve_triggered: bool,
) -> ReservedRescueDecision:
    return ReservedRescueDecision(
        status=parent.status,
        operator_id=parent.operator_id,
        posterior=float(parent.posterior),
        margin=float(parent.margin),
        queries=tuple(parent.queries),
        channels=tuple(parent.channels),
        total_cost=float(parent.total_cost),
        actions=tuple(parent.actions),
        stop_reason=str(parent.stop_reason),
        escalated=bool(parent.escalated),
        escalation_at_query=parent.escalation_at_query,
        reverification_count=int(parent.reverification_count),
        reverified_queries=tuple(parent.reverified_queries),
        selection_mode=str(parent.selection_mode),
        ledger=parent.ledger,
        trust_posterior=parent.trust_posterior,
        reserve_calls=int(reserve_calls),
        point_prefix_limit=int(point_prefix_limit),
        point_policy_horizon=int(point_policy_horizon),
        reserve_triggered=bool(reserve_triggered),
    )


def _build(
    decision,
    *,
    escalated: bool,
    escalation_at_query: int | None,
    reverified_queries: Sequence[str],
    selection_mode: str,
    ledger: EvidenceLedger,
    trust_posterior: ReliabilityPosterior,
    reserve_calls: int,
    point_prefix_limit: int,
    point_policy_horizon: int,
    reserve_triggered: bool,
) -> ReservedRescueDecision:
    return ReservedRescueDecision(
        status=decision.status,
        operator_id=decision.operator_id,
        posterior=float(decision.posterior),
        margin=float(decision.margin),
        queries=tuple(decision.queries),
        channels=tuple(decision.channels),
        total_cost=float(decision.total_cost),
        actions=tuple(decision.actions),
        stop_reason=str(decision.stop_reason),
        escalated=bool(escalated),
        escalation_at_query=escalation_at_query,
        reverification_count=len(tuple(reverified_queries)),
        reverified_queries=tuple(reverified_queries),
        selection_mode=str(selection_mode),
        ledger=ledger,
        trust_posterior=trust_posterior,
        reserve_calls=int(reserve_calls),
        point_prefix_limit=int(point_prefix_limit),
        point_policy_horizon=int(point_policy_horizon),
        reserve_triggered=bool(reserve_triggered),
    )


def route_with_reserved_rescue(
    proposals: Sequence[OperatorProposal],
    query_ids: Sequence[str],
    predictions: Mapping[str, Mapping[str, bool]],
    *,
    regime: VerifierRegime,
    policy: PolicyBundle,
    verifier_by_channel: Mapping[str, Callable[[str], VerifierObservation]],
    counterexample_check: Callable[[OperatorProposal], bool],
    max_queries: int,
    rescue_reserve_calls: int,
    accept_probability: float,
    accept_margin: float,
    max_mdl_cost: int,
    complexity_weight: float,
    initial_trust: ReliabilityPosterior,
    max_reverify: int,
    selection_mode: str = 'loo_loss',
) -> ReservedRescueDecision:
    hard_cap = int(max_queries)
    reserve = int(rescue_reserve_calls)
    if hard_cap < 0:
        raise ValueError('max_queries must be non-negative')
    if reserve < 0 or reserve > hard_cap:
        raise ValueError('rescue_reserve_calls must satisfy 0 <= reserve <= max_queries')
    point_prefix_limit = hard_cap - reserve

    # The zero-reserve ablation is exactly the frozen R2.31 route, not a
    # reimplementation. This makes the causal control byte-for-byte faithful.
    if reserve == 0:
        parent = route_with_loo_probe_rescue(
            proposals,
            query_ids,
            predictions,
            regime=regime,
            policy=policy,
            verifier_by_channel=verifier_by_channel,
            counterexample_check=counterexample_check,
            max_queries=hard_cap,
            accept_probability=accept_probability,
            accept_margin=accept_margin,
            max_mdl_cost=max_mdl_cost,
            complexity_weight=complexity_weight,
            initial_trust=initial_trust,
            max_reverify=max_reverify,
            selection_mode=selection_mode,
        )
        return _wrap_parent(
            parent,
            reserve_calls=0,
            point_prefix_limit=hard_cap,
            point_policy_horizon=hard_cap,
            reserve_triggered=False,
        )

    proposals = tuple(p for p in proposals if p.mdl_cost <= int(max_mdl_cost))
    if set(policy.models) != set(ACTIONS):
        raise ValueError('policy action coverage mismatch')
    if set(verifier_by_channel) != {regime.cheap.name, regime.strong.name}:
        raise ValueError('verifier channel coverage mismatch')
    max_reverify = int(max_reverify)
    if max_reverify < 0:
        raise ValueError('max_reverify must be non-negative')

    if not proposals:
        stopped = _stop_decision(
            (),
            {},
            counterexample_check=counterexample_check,
            accept_probability=accept_probability,
            accept_margin=accept_margin,
            queries=(),
            channels=(),
            total_cost=0.0,
            actions=(),
            fallback_reason='no_proposals_within_complexity_budget',
        )
        return _build(
            stopped,
            escalated=False,
            escalation_at_query=None,
            reverified_queries=(),
            selection_mode=selection_mode,
            ledger=EvidenceLedger(),
            trust_posterior=initial_trust,
            reserve_calls=reserve,
            point_prefix_limit=point_prefix_limit,
            point_policy_horizon=hard_cap,
            reserve_triggered=False,
        )

    by_proposal = {p.operator_id: p for p in proposals}
    supports = initial_proposal_supports(proposals, complexity_weight=float(complexity_weight))
    remaining = list(dict.fromkeys(map(str, query_ids)))
    queries: list[str] = []
    channels: list[str] = []
    actions: list[str] = []
    total_cost = 0.0
    ledger = EvidenceLedger()
    trust_posterior = initial_trust
    reverified_queries: list[str] = []

    # Frozen point-policy behavior. Crucially, the policy still sees the full
    # hard-cap horizon; only the external controller reserves late calls.
    while True:
        terminal = _terminal_decision_if_ready(
            supports,
            by_proposal,
            counterexample_check=counterexample_check,
            accept_probability=accept_probability,
            accept_margin=accept_margin,
            queries=queries,
            channels=channels,
            total_cost=total_cost,
            actions=actions,
        )
        if terminal is not None:
            return _build(
                terminal,
                escalated=False,
                escalation_at_query=None,
                reverified_queries=(),
                selection_mode=selection_mode,
                ledger=ledger,
                trust_posterior=trust_posterior,
                reserve_calls=reserve,
                point_prefix_limit=point_prefix_limit,
                point_policy_horizon=hard_cap,
                reserve_triggered=False,
            )
        if len(queries) >= point_prefix_limit or not remaining:
            break

        state = MetaState(
            supports=tuple(supports),
            max_remaining_disagreement=_max_disagreement(supports, remaining, predictions),
            queries_used=len(queries),
            max_queries=max(hard_cap, 1),
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
            break

        channel = regime.cheap if action == 'cheap' else regime.strong
        q = choose_operator_query(proposals, supports, remaining, predictions)
        obs = verifier_by_channel[channel.name](q)
        if obs.query_id != q:
            raise ValueError('verifier returned wrong query')
        if abs(float(obs.reliability) - float(channel.reliability)) > 1e-12:
            raise ValueError('verifier reliability does not match channel contract')
        supports = update_proposal_supports(proposals, supports, obs, predictions[q])
        ledger = append_observation(
            ledger,
            query_id=q,
            predicted_labels=predictions[q],
            observed_label=obs.observed_label,
            reliability=obs.reliability,
            channel=channel.name,
            cost=channel.cost,
        )
        queries.append(q)
        channels.append(channel.name)
        total_cost += channel.cost
        remaining.remove(q)

    reserve_triggered = len(queries) >= point_prefix_limit and point_prefix_limit < hard_cap
    escalation_at_query = len(queries)

    # Frozen R2.31 historical correction using only the reserved tail budget.
    for _ in range(max_reverify):
        if len(queries) >= hard_cap:
            break
        candidate = select_probe_observation(
            proposals,
            ledger,
            supports,
            trust_posterior,
            regime=regime,
            complexity_weight=float(complexity_weight),
            selection_mode=selection_mode,
        )
        if candidate is None:
            break
        old = ledger.entries[int(candidate.observation_index)]
        obs = verifier_by_channel[regime.strong.name](old.query_id)
        if obs.query_id != old.query_id:
            raise ValueError('verifier returned wrong query')
        if abs(float(obs.reliability) - float(regime.strong.reliability)) > 1e-12:
            raise ValueError('verifier reliability does not match channel contract')
        trust_posterior = update_reliability_from_agreement(
            trust_posterior,
            agrees=bool(obs.observed_label == old.observed_label),
            strong_reliability=regime.strong.reliability,
        )
        ledger = supersede_observation(
            ledger,
            observation_index=old.observation_index,
            observed_label=obs.observed_label,
            reliability=obs.reliability,
            channel=regime.strong.name,
            cost=regime.strong.cost,
        )
        supports = replay_supports(proposals, ledger, complexity_weight=float(complexity_weight))
        queries.append(old.query_id)
        channels.append(regime.strong.name)
        actions.append('reverify')
        total_cost += regime.strong.cost
        reverified_queries.append(old.query_id)

        terminal = _terminal_decision_if_ready(
            supports,
            by_proposal,
            counterexample_check=counterexample_check,
            accept_probability=accept_probability,
            accept_margin=accept_margin,
            queries=queries,
            channels=channels,
            total_cost=total_cost,
            actions=actions,
        )
        if terminal is not None:
            return _build(
                terminal,
                escalated=True,
                escalation_at_query=escalation_at_query,
                reverified_queries=reverified_queries,
                selection_mode=selection_mode,
                ledger=ledger,
                trust_posterior=trust_posterior,
                reserve_calls=reserve,
                point_prefix_limit=point_prefix_limit,
                point_policy_horizon=hard_cap,
                reserve_triggered=reserve_triggered,
            )

    # Frozen strong continuation on unseen queries until the shared total cap.
    while len(queries) < hard_cap and remaining:
        terminal = _terminal_decision_if_ready(
            supports,
            by_proposal,
            counterexample_check=counterexample_check,
            accept_probability=accept_probability,
            accept_margin=accept_margin,
            queries=queries,
            channels=channels,
            total_cost=total_cost,
            actions=actions,
        )
        if terminal is not None:
            return _build(
                terminal,
                escalated=True,
                escalation_at_query=escalation_at_query,
                reverified_queries=reverified_queries,
                selection_mode=selection_mode,
                ledger=ledger,
                trust_posterior=trust_posterior,
                reserve_calls=reserve,
                point_prefix_limit=point_prefix_limit,
                point_policy_horizon=hard_cap,
                reserve_triggered=reserve_triggered,
            )
        q = choose_operator_query(proposals, supports, remaining, predictions)
        obs = verifier_by_channel[regime.strong.name](q)
        if obs.query_id != q:
            raise ValueError('verifier returned wrong query')
        if abs(float(obs.reliability) - float(regime.strong.reliability)) > 1e-12:
            raise ValueError('verifier reliability does not match channel contract')
        supports = update_proposal_supports(proposals, supports, obs, predictions[q])
        ledger = append_observation(
            ledger,
            query_id=q,
            predicted_labels=predictions[q],
            observed_label=obs.observed_label,
            reliability=obs.reliability,
            channel=regime.strong.name,
            cost=regime.strong.cost,
        )
        queries.append(q)
        channels.append(regime.strong.name)
        actions.append('strong-rescue')
        total_cost += regime.strong.cost
        remaining.remove(q)

    stopped = _stop_decision(
        supports,
        by_proposal,
        counterexample_check=counterexample_check,
        accept_probability=accept_probability,
        accept_margin=accept_margin,
        queries=queries,
        channels=channels,
        total_cost=total_cost,
        actions=actions,
        fallback_reason='hard_cap_or_evidence_exhausted',
    )
    return _build(
        stopped,
        escalated=True,
        escalation_at_query=escalation_at_query,
        reverified_queries=reverified_queries,
        selection_mode=selection_mode,
        ledger=ledger,
        trust_posterior=trust_posterior,
        reserve_calls=reserve,
        point_prefix_limit=point_prefix_limit,
        point_policy_horizon=hard_cap,
        reserve_triggered=reserve_triggered,
    )
