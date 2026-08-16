from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from .r219_representation_types import VerifierObservation
from .r220_language_synthesis import OperatorProposal
from .r220_operator_discovery import (
    choose_operator_query,
    initial_proposal_supports,
    update_proposal_supports,
)
from .r222_counterfactual_trainer import ACTIONS, PolicyBundle
from .r222_learned_voi import (
    LearnedVOIDecision,
    _max_disagreement,
    _stop_decision,
    _terminal_decision_if_ready,
)
from .r222_voi_types import MetaState, VerifierRegime, expand_meta_features, extract_meta_features
from .r227_evidence_ledger import (
    EvidenceLedger,
    LedgerObservation,
    append_observation,
    replay_supports,
    supersede_observation,
)
from .r227_reverification import rank_reverification_candidates
from .r228_trust_model import ReliabilityPosterior, update_reliability_from_agreement
from .r230_probe_value import rank_bayesian_probe_candidates

_SELECTION_MODES = {'bayes_value', 'r227_targeted', 'oldest', 'random', 'no_reverify'}


@dataclass(frozen=True)
class BayesianProbeRescueDecision:
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


def _convert(
    decision: LearnedVOIDecision,
    *,
    escalated: bool,
    escalation_at_query: int | None,
    reverified_queries: Sequence[str],
    selection_mode: str,
    ledger: EvidenceLedger,
    trust_posterior: ReliabilityPosterior,
) -> BayesianProbeRescueDecision:
    return BayesianProbeRescueDecision(
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
    )


def _eligible_cheap_rows(ledger: EvidenceLedger, regime: VerifierRegime) -> tuple[LedgerObservation, ...]:
    return tuple(
        row for row in ledger.entries
        if row.active and row.channel == regime.cheap.name
    )


def select_probe_observation(
    proposals: Sequence[OperatorProposal],
    ledger: EvidenceLedger,
    supports,
    trust_posterior: ReliabilityPosterior,
    *,
    regime: VerifierRegime,
    complexity_weight: float,
    selection_mode: str,
):
    """Choose one active historical cheap observation using only inference state."""
    mode = str(selection_mode).strip().lower()
    if mode not in _SELECTION_MODES:
        raise ValueError('invalid selection_mode')
    if mode == 'no_reverify':
        return None
    eligible = _eligible_cheap_rows(ledger, regime)
    if not eligible:
        return None
    if mode == 'bayes_value':
        ranked = rank_bayesian_probe_candidates(
            proposals,
            ledger,
            trust_posterior,
            regime=regime,
            complexity_weight=float(complexity_weight),
        )
        return ranked[0] if ranked else None
    if mode == 'r227_targeted':
        ranked = rank_reverification_candidates(
            proposals,
            ledger,
            supports,
            regime=regime,
            complexity_weight=float(complexity_weight),
        )
        return ranked[0] if ranked else None
    if mode == 'oldest':
        return min(eligible, key=lambda row: (row.observation_index, row.query_id))
    return min(
        eligible,
        key=lambda row: (
            hashlib.sha256(f'{row.query_id}|{row.observation_index}'.encode()).hexdigest(),
            row.observation_index,
            row.query_id,
        ),
    )


def route_with_bayesian_probe_rescue(
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
    initial_trust: ReliabilityPosterior,
    max_reverify: int,
    selection_mode: str = 'bayes_value',
) -> BayesianProbeRescueDecision:
    proposals = tuple(p for p in proposals if p.mdl_cost <= int(max_mdl_cost))
    selection_mode = str(selection_mode).strip().lower()
    if selection_mode not in _SELECTION_MODES:
        raise ValueError('invalid selection_mode')
    if set(policy.models) != set(ACTIONS):
        raise ValueError('policy action coverage mismatch')
    if set(verifier_by_channel) != {regime.cheap.name, regime.strong.name}:
        raise ValueError('verifier channel coverage mismatch')
    hard_cap = int(max_queries)
    if hard_cap < 0:
        raise ValueError('max_queries must be non-negative')
    max_reverify = int(max_reverify)
    if max_reverify < 0:
        raise ValueError('max_reverify must be non-negative')
    trust_posterior = initial_trust

    if not proposals:
        return BayesianProbeRescueDecision(
            'abstain', None, 0.0, 0.0, (), (), 0.0, (),
            'no_proposals_within_complexity_budget', False, None, 0, (),
            selection_mode, EvidenceLedger(), trust_posterior,
        )

    by_proposal = {p.operator_id: p for p in proposals}
    supports = initial_proposal_supports(proposals, complexity_weight=float(complexity_weight))
    remaining = list(dict.fromkeys(map(str, query_ids)))
    point_policy_cap = min(hard_cap, len(remaining))
    queries: list[str] = []
    channels: list[str] = []
    actions: list[str] = []
    total_cost = 0.0
    ledger = EvidenceLedger()
    escalated = False
    escalation_at_query: int | None = None
    reverified_queries: list[str] = []

    # Frozen R2.22 point-policy prefix. Successful point episodes return exactly.
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
            return _convert(
                terminal,
                escalated=False,
                escalation_at_query=None,
                reverified_queries=(),
                selection_mode=selection_mode,
                ledger=ledger,
                trust_posterior=trust_posterior,
            )
        if len(queries) >= point_policy_cap or not remaining:
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
            return _convert(
                stopped,
                escalated=False,
                escalation_at_query=None,
                reverified_queries=(),
                selection_mode=selection_mode,
                ledger=ledger,
                trust_posterior=trust_posterior,
            )

        state = MetaState(
            supports=tuple(supports),
            max_remaining_disagreement=_max_disagreement(supports, remaining, predictions),
            queries_used=len(queries),
            max_queries=max(point_policy_cap, 1),
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
            escalated = True
            escalation_at_query = len(queries)
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

    # Adaptive historical correction. Only the selected row is superseded;
    # unprobed cheap evidence keeps its original reliability in ordinary replay.
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
            return _convert(
                terminal,
                escalated=escalated,
                escalation_at_query=escalation_at_query,
                reverified_queries=reverified_queries,
                selection_mode=selection_mode,
                ledger=ledger,
                trust_posterior=trust_posterior,
            )

    # Same strong continuation for every selector, under the same call cap.
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
            return _convert(
                terminal,
                escalated=escalated,
                escalation_at_query=escalation_at_query,
                reverified_queries=reverified_queries,
                selection_mode=selection_mode,
                ledger=ledger,
                trust_posterior=trust_posterior,
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
    return _convert(
        stopped,
        escalated=escalated,
        escalation_at_query=escalation_at_query,
        reverified_queries=reverified_queries,
        selection_mode=selection_mode,
        ledger=ledger,
        trust_posterior=trust_posterior,
    )
