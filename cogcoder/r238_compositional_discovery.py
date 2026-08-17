from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from .r219_representation_types import VerifierObservation
from .r220_language_synthesis import OperatorProposal
from .r220_operator_discovery import choose_operator_query, initial_proposal_supports, update_proposal_supports
from .r237_query_generation import GeneratedQuery, synthesize_counterexample_probe
from .r238_probe_language import ProbeProgram, atom_probe, probe_prediction_row
from .r238_probe_synthesis import synthesize_compositional_probe


@dataclass(frozen=True)
class CompositionalDiscoveryDecision:
    status: str
    operator_id: str | None
    posterior: float
    margin: float
    mdl_cost: int | None
    queries: tuple[str, ...]
    composite_probe_ids: tuple[str, ...]
    atomic_generated_query_ids: tuple[str, ...]
    synthesis_candidates_evaluated: int
    reason: str


def _rank(supports):
    ranked = sorted(supports, key=lambda s: (-s.posterior, s.operator_id))
    top = ranked[0]
    second = ranked[1].posterior if len(ranked) > 1 else 0.0
    return top, top.posterior - second


def discover_with_compositional_probes(
    proposals: Sequence[OperatorProposal],
    universe: Sequence[GeneratedQuery],
    initial_pool: Sequence[GeneratedQuery],
    atom_predictions: Mapping[str, Mapping[str, bool]],
    *,
    verifier: Callable[[ProbeProgram], VerifierObservation],
    counterexample_check: Callable[[OperatorProposal], bool],
    query_budget: int,
    accept_probability: float,
    accept_margin: float,
    max_mdl_cost: int,
    complexity_weight: float,
    atom_shortlist_size: int = 16,
    mode: str = 'compositional',
) -> CompositionalDiscoveryDecision:
    if mode not in {'compositional', 'atomic_only', 'pool_only'}:
        raise ValueError('unknown R2.38 discovery mode')
    proposals = tuple(p for p in proposals if p.mdl_cost <= int(max_mdl_cost))
    if not proposals:
        return CompositionalDiscoveryDecision('abstain', None, 0.0, 0.0, None, (), (), (), 0, 'no_proposals_within_complexity_budget')
    universe = tuple(universe)
    initial_pool = tuple(initial_pool)
    if not universe or not initial_pool:
        raise ValueError('universe and initial_pool must be non-empty')
    by_query = {q.query_id: q for q in universe}
    if len(by_query) != len(universe):
        raise ValueError('query universe must have unique ids')
    if any(q.query_id not in by_query for q in initial_pool):
        raise ValueError('initial_pool must be contained in universe')
    proposal_ids = {p.operator_id for p in proposals}
    for q in universe:
        row = atom_predictions.get(q.query_id)
        if row is None or set(row) != proposal_ids:
            raise ValueError('prediction coverage mismatch')

    supports = initial_proposal_supports(proposals, complexity_weight=float(complexity_weight))
    by_proposal = {p.operator_id: p for p in proposals}
    remaining_initial = [q.query_id for q in initial_pool]
    observed_atomic: set[str] = set()
    observed_probe_ids: set[str] = set()
    queries: list[str] = []
    composite_ids: list[str] = []
    atomic_generated: list[str] = []
    candidate_evals = 0

    for _ in range(max(0, int(query_budget))):
        if remaining_initial:
            qid = choose_operator_query(proposals, supports, remaining_initial, atom_predictions)
            program = atom_probe(qid)
            row = atom_predictions[qid]
            remaining_initial.remove(qid)
            observed_atomic.add(qid)
        else:
            if mode == 'pool_only':
                break
            if mode == 'atomic_only':
                query = synthesize_counterexample_probe(universe, supports, observed_atomic, atom_predictions)
                qid = query.query_id
                program = atom_probe(qid)
                row = atom_predictions[qid]
                observed_atomic.add(qid)
                atomic_generated.append(qid)
            else:
                candidate_atoms = tuple(q.query_id for q in universe if q.query_id not in observed_atomic)
                if len(candidate_atoms) < 2:
                    break
                receipt = synthesize_compositional_probe(
                    candidate_atoms,
                    supports,
                    atom_predictions,
                    observed_probe_ids,
                    atom_shortlist_size=atom_shortlist_size,
                )
                program = receipt.probe
                row = probe_prediction_row(program, atom_predictions)
                composite_ids.append(program.probe_id)
                candidate_evals += receipt.candidates_evaluated

        observation = verifier(program)
        if observation.query_id != program.probe_id:
            raise ValueError('verifier returned wrong probe id')
        supports = update_proposal_supports(proposals, supports, observation, row)
        observed_probe_ids.add(program.probe_id)
        queries.append(program.probe_id)
        top, margin = _rank(supports)
        if top.posterior >= float(accept_probability) and margin >= float(accept_margin):
            proposal = by_proposal[top.operator_id]
            if counterexample_check(proposal):
                return CompositionalDiscoveryDecision(
                    'accept', proposal.operator_id, top.posterior, margin, proposal.mdl_cost,
                    tuple(queries), tuple(composite_ids), tuple(atomic_generated), candidate_evals,
                    'supported_operator_survived_counterexample',
                )
            return CompositionalDiscoveryDecision(
                'abstain', None, top.posterior, margin, proposal.mdl_cost,
                tuple(queries), tuple(composite_ids), tuple(atomic_generated), candidate_evals,
                'counterexample_rejected_top_operator',
            )

    top, margin = _rank(supports)
    return CompositionalDiscoveryDecision(
        'abstain', None, top.posterior, margin, by_proposal[top.operator_id].mdl_cost,
        tuple(queries), tuple(composite_ids), tuple(atomic_generated), candidate_evals,
        'insufficient_identifiability_or_budget',
    )
