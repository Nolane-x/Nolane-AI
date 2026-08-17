from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from .r219_representation_types import VerifierObservation
from .r220_language_synthesis import OperatorProposal
from .r220_operator_discovery import (
    choose_operator_query,
    initial_proposal_supports,
    update_proposal_supports,
)
from .r237_query_generation import GeneratedQuery, synthesize_counterexample_probe


@dataclass(frozen=True)
class GenerativeDiscoveryDecision:
    status: str
    operator_id: str | None
    posterior: float
    margin: float
    mdl_cost: int | None
    queries: tuple[str, ...]
    generated_queries: tuple[str, ...]
    reason: str


def _rank(supports):
    rows = sorted(supports, key=lambda s: (-s.posterior, s.operator_id))
    top = rows[0]
    second = rows[1].posterior if len(rows) > 1 else 0.0
    return top, top.posterior - second


def discover_with_generated_probes(
    proposals: Sequence[OperatorProposal],
    universe: Sequence[GeneratedQuery],
    initial_pool: Sequence[GeneratedQuery],
    predictions: Mapping[str, Mapping[str, bool]],
    *,
    verifier: Callable[[GeneratedQuery], VerifierObservation],
    counterexample_check: Callable[[OperatorProposal], bool],
    query_budget: int,
    accept_probability: float,
    accept_margin: float,
    max_mdl_cost: int,
    complexity_weight: float,
    generation_mode: str = 'guided',
) -> GenerativeDiscoveryDecision:
    proposals = tuple(p for p in proposals if p.mdl_cost <= int(max_mdl_cost))
    universe = tuple(universe)
    initial_pool = tuple(initial_pool)
    if generation_mode not in {'guided', 'unguided', 'pool_only'}:
        raise ValueError('unknown generation mode')
    if not proposals:
        return GenerativeDiscoveryDecision('abstain', None, 0.0, 0.0, None, (), (), 'no_proposals_within_complexity_budget')
    if not universe or not initial_pool:
        raise ValueError('universe and initial_pool must be non-empty')
    universe_by_id = {q.query_id: q for q in universe}
    if len(universe_by_id) != len(universe):
        raise ValueError('query universe must contain unique ids')
    if any(q.query_id not in universe_by_id for q in initial_pool):
        raise ValueError('initial pool must be contained in universe')

    proposal_ids = {p.operator_id for p in proposals}
    for query in universe:
        row = predictions.get(query.query_id)
        if row is None or set(row) != proposal_ids:
            raise ValueError('prediction coverage mismatch')

    by_proposal = {p.operator_id: p for p in proposals}
    supports = initial_proposal_supports(proposals, complexity_weight=float(complexity_weight))
    remaining_initial = [q.query_id for q in initial_pool]
    observed: set[str] = set()
    queried: list[str] = []
    generated: list[str] = []
    budget = max(0, int(query_budget))

    for _ in range(budget):
        if remaining_initial:
            qid = choose_operator_query(proposals, supports, remaining_initial, predictions)
            query = universe_by_id[qid]
            remaining_initial.remove(qid)
        else:
            if generation_mode == 'pool_only':
                break
            if generation_mode == 'guided':
                query = synthesize_counterexample_probe(universe, supports, observed, predictions)
            else:
                candidates = sorted((q for q in universe if q.query_id not in observed), key=lambda q: q.query_id)
                if not candidates:
                    break
                query = candidates[0]
            qid = query.query_id
            generated.append(qid)

        observation = verifier(query)
        if observation.query_id != qid:
            raise ValueError('verifier returned wrong query')
        supports = update_proposal_supports(proposals, supports, observation, predictions[qid])
        observed.add(qid)
        queried.append(qid)
        top, margin = _rank(supports)
        if top.posterior >= float(accept_probability) and margin >= float(accept_margin):
            proposal = by_proposal[top.operator_id]
            if counterexample_check(proposal):
                return GenerativeDiscoveryDecision(
                    'accept', proposal.operator_id, top.posterior, margin, proposal.mdl_cost,
                    tuple(queried), tuple(generated), 'supported_operator_survived_counterexample',
                )
            return GenerativeDiscoveryDecision(
                'abstain', None, top.posterior, margin, proposal.mdl_cost,
                tuple(queried), tuple(generated), 'counterexample_rejected_top_operator',
            )

    top, margin = _rank(supports)
    return GenerativeDiscoveryDecision(
        'abstain', None, top.posterior, margin, by_proposal[top.operator_id].mdl_cost,
        tuple(queried), tuple(generated), 'insufficient_identifiability_or_budget',
    )
