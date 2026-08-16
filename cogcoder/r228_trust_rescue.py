from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from .r219_representation_types import VerifierObservation
from .r220_language_synthesis import OperatorProposal
from .r220_operator_discovery import choose_operator_query, initial_proposal_supports, update_proposal_supports
from .r222_counterfactual_trainer import ACTIONS, PolicyBundle
from .r222_learned_voi import (
    LearnedVOIDecision,
    _max_disagreement,
    _stop_decision,
    _terminal_decision_if_ready,
)
from .r222_voi_types import MetaState, VerifierRegime, expand_meta_features, extract_meta_features
from .r227_evidence_ledger import EvidenceLedger, append_observation, replay_supports, supersede_observation
from .r228_recalibration import replay_with_calibrated_cheap_reliability
from .r228_trust_model import ReliabilityPosterior, make_reliability_prior, update_reliability_from_agreement


@dataclass(frozen=True)
class TrustRescueDecision:
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
    probe_ids: tuple[str, ...]
    probe_strong_labels: tuple[bool, ...]
    mode: str
    ledger: EvidenceLedger
    trust_posterior: ReliabilityPosterior


def _convert(
    decision: LearnedVOIDecision,
    *,
    escalated: bool,
    escalation_at_query: int | None,
    probe_ids: Sequence[str],
    probe_strong_labels: Sequence[bool],
    mode: str,
    ledger: EvidenceLedger,
    trust_posterior: ReliabilityPosterior,
) -> TrustRescueDecision:
    return TrustRescueDecision(
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
        probe_ids=tuple(probe_ids),
        probe_strong_labels=tuple(bool(x) for x in probe_strong_labels),
        mode=mode,
        ledger=ledger,
        trust_posterior=trust_posterior,
    )


def _replay(
    proposals: Sequence[OperatorProposal],
    ledger: EvidenceLedger,
    *,
    regime: VerifierRegime,
    trust: ReliabilityPosterior,
    mode: str,
    complexity_weight: float,
):
    if mode == 'calibrated':
        return replay_with_calibrated_cheap_reliability(
            proposals,
            ledger,
            cheap_channel=regime.cheap.name,
            calibrated_reliability=trust.posterior_mean(),
            complexity_weight=complexity_weight,
        )
    return replay_supports(proposals, ledger, complexity_weight=complexity_weight)


def route_with_trust_recalibration(
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
    prior_concentration: float,
    max_probes: int,
    mode: str = 'calibrated',
) -> TrustRescueDecision:
    mode=str(mode).strip().lower()
    if mode not in {'calibrated','probe_only'}:
        raise ValueError('mode must be calibrated or probe_only')
    hard_cap=int(max_queries)
    if hard_cap < 0:
        raise ValueError('max_queries must be non-negative')
    max_probes=int(max_probes)
    if max_probes < 0:
        raise ValueError('max_probes must be non-negative')
    proposals=tuple(p for p in proposals if p.mdl_cost <= int(max_mdl_cost))
    trust=make_reliability_prior(regime.cheap.reliability, concentration=float(prior_concentration))
    if not proposals:
        return TrustRescueDecision(
            'abstain',None,0.0,0.0,(),(),0.0,(),'no_proposals_within_complexity_budget',
            False,None,(),(),mode,EvidenceLedger(),trust,
        )
    if set(policy.models) != set(ACTIONS):
        raise ValueError('policy action coverage mismatch')
    if set(verifier_by_channel) != {regime.cheap.name, regime.strong.name}:
        raise ValueError('verifier channel coverage mismatch')

    by_proposal={p.operator_id:p for p in proposals}
    supports=initial_proposal_supports(proposals, complexity_weight=float(complexity_weight))
    remaining=list(dict.fromkeys(map(str,query_ids)))
    queries: list[str]=[]
    channels: list[str]=[]
    actions: list[str]=[]
    total_cost=0.0
    ledger=EvidenceLedger()
    escalated=False
    escalation_at_query: int|None=None
    probe_ids: list[str]=[]
    probe_strong_labels: list[bool]=[]

    # Frozen R2.22 point-policy prefix. A successful terminal returns exactly.
    while True:
        terminal=_terminal_decision_if_ready(
            supports,by_proposal,counterexample_check=counterexample_check,
            accept_probability=accept_probability,accept_margin=accept_margin,
            queries=queries,channels=channels,total_cost=total_cost,actions=actions,
        )
        if terminal is not None:
            return _convert(
                terminal,escalated=False,escalation_at_query=None,probe_ids=(),probe_strong_labels=(),
                mode=mode,ledger=ledger,trust_posterior=trust,
            )
        if len(queries)>=hard_cap or not remaining:
            stopped=_stop_decision(
                supports,by_proposal,counterexample_check=counterexample_check,
                accept_probability=accept_probability,accept_margin=accept_margin,
                queries=queries,channels=channels,total_cost=total_cost,actions=actions,
                fallback_reason='hard_cap_or_evidence_exhausted',
            )
            return _convert(
                stopped,escalated=False,escalation_at_query=None,probe_ids=(),probe_strong_labels=(),
                mode=mode,ledger=ledger,trust_posterior=trust,
            )
        state=MetaState(
            supports=tuple(supports),
            max_remaining_disagreement=_max_disagreement(supports,remaining,predictions),
            queries_used=len(queries),max_queries=max(hard_cap,1),remaining_queries=len(remaining),
            accumulated_cost=total_cost,cheap=regime.cheap,strong=regime.strong,
        )
        features=expand_meta_features(extract_meta_features(state))
        values={action:policy.models[action].predict(features) for action in ACTIONS}
        action=max(ACTIONS,key=lambda a:(values[a],-ACTIONS.index(a)))
        actions.append(action)
        if action=='stop':
            escalated=True
            escalation_at_query=len(queries)
            break
        channel=regime.cheap if action=='cheap' else regime.strong
        q=choose_operator_query(proposals,supports,remaining,predictions)
        obs=verifier_by_channel[channel.name](q)
        if obs.query_id != q:
            raise ValueError('verifier returned wrong query')
        if abs(float(obs.reliability)-float(channel.reliability))>1e-12:
            raise ValueError('verifier reliability does not match channel contract')
        supports=update_proposal_supports(proposals,supports,obs,predictions[q])
        ledger=append_observation(
            ledger,query_id=q,predicted_labels=predictions[q],observed_label=obs.observed_label,
            reliability=obs.reliability,channel=channel.name,cost=channel.cost,
        )
        queries.append(q); channels.append(channel.name); total_cost+=channel.cost; remaining.remove(q)

    # Fixed, non-targeted oldest cheap probes. Both causal modes share these probes.
    for _ in range(max_probes):
        if len(queries)>=hard_cap:
            break
        eligible=tuple(
            row for row in ledger.entries
            if row.active and row.channel==regime.cheap.name
        )
        if not eligible:
            break
        old=min(eligible,key=lambda row:(row.observation_index,row.query_id))
        obs=verifier_by_channel[regime.strong.name](old.query_id)
        if obs.query_id != old.query_id:
            raise ValueError('verifier returned wrong query')
        if abs(float(obs.reliability)-float(regime.strong.reliability))>1e-12:
            raise ValueError('verifier reliability does not match channel contract')
        trust=update_reliability_from_agreement(
            trust,agrees=(old.observed_label==obs.observed_label),strong_reliability=regime.strong.reliability,
        )
        ledger=supersede_observation(
            ledger,observation_index=old.observation_index,observed_label=obs.observed_label,
            reliability=obs.reliability,channel=regime.strong.name,cost=regime.strong.cost,
        )
        supports=_replay(
            proposals,ledger,regime=regime,trust=trust,mode=mode,complexity_weight=complexity_weight,
        )
        queries.append(old.query_id); channels.append(regime.strong.name); actions.append('trust-probe')
        total_cost+=regime.strong.cost; probe_ids.append(old.query_id); probe_strong_labels.append(obs.observed_label)
        terminal=_terminal_decision_if_ready(
            supports,by_proposal,counterexample_check=counterexample_check,
            accept_probability=accept_probability,accept_margin=accept_margin,
            queries=queries,channels=channels,total_cost=total_cost,actions=actions,
        )
        if terminal is not None:
            return _convert(
                terminal,escalated=escalated,escalation_at_query=escalation_at_query,
                probe_ids=probe_ids,probe_strong_labels=probe_strong_labels,mode=mode,ledger=ledger,trust_posterior=trust,
            )

    # Strong continuation over previously unseen queries only, under the same call cap.
    while len(queries)<hard_cap and remaining:
        terminal=_terminal_decision_if_ready(
            supports,by_proposal,counterexample_check=counterexample_check,
            accept_probability=accept_probability,accept_margin=accept_margin,
            queries=queries,channels=channels,total_cost=total_cost,actions=actions,
        )
        if terminal is not None:
            return _convert(
                terminal,escalated=escalated,escalation_at_query=escalation_at_query,
                probe_ids=probe_ids,probe_strong_labels=probe_strong_labels,mode=mode,ledger=ledger,trust_posterior=trust,
            )
        q=choose_operator_query(proposals,supports,remaining,predictions)
        obs=verifier_by_channel[regime.strong.name](q)
        if obs.query_id != q:
            raise ValueError('verifier returned wrong query')
        if abs(float(obs.reliability)-float(regime.strong.reliability))>1e-12:
            raise ValueError('verifier reliability does not match channel contract')
        supports=update_proposal_supports(proposals,supports,obs,predictions[q])
        ledger=append_observation(
            ledger,query_id=q,predicted_labels=predictions[q],observed_label=obs.observed_label,
            reliability=obs.reliability,channel=regime.strong.name,cost=regime.strong.cost,
        )
        queries.append(q); channels.append(regime.strong.name); actions.append('strong-rescue')
        total_cost+=regime.strong.cost; remaining.remove(q)

    stopped=_stop_decision(
        supports,by_proposal,counterexample_check=counterexample_check,
        accept_probability=accept_probability,accept_margin=accept_margin,
        queries=queries,channels=channels,total_cost=total_cost,actions=actions,
        fallback_reason='hard_cap_or_evidence_exhausted',
    )
    return _convert(
        stopped,escalated=escalated,escalation_at_query=escalation_at_query,
        probe_ids=probe_ids,probe_strong_labels=probe_strong_labels,mode=mode,ledger=ledger,trust_posterior=trust,
    )
