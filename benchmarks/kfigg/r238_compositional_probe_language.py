from __future__ import annotations

import hashlib
import inspect
from functools import lru_cache

from cogcoder.r219_representation_types import VerifierObservation
from cogcoder.r220_language_synthesis import synthesize_operator_proposals
from cogcoder.r220_operator_language import apply_operator
from cogcoder.r237_query_generation import enumerate_query_universe, initial_query_pool
from cogcoder.r238_compositional_discovery import discover_with_compositional_probes
from cogcoder.r238_probe_language import evaluate_probe
from cogcoder.r238_probe_synthesis import synthesize_compositional_probe

DEV_SEEDS = (151, 157, 163)
DEV_REGIMES = ('clean', 'noisy')
TRANSFER_DRY_RUN_SEEDS = (499, 509)

ACCEPT_PROBABILITY = 0.95
ACCEPT_MARGIN = 0.75
COMPLEXITY_WEIGHT = 0.03
MAX_MDL_COST = 3
ATOM_SHORTLIST_SIZE = 12


def _transition_nonlinear_local(state):
    row = tuple(int(v) for v in state)
    width = len(row)
    return tuple(
        row[(i + 1) % width] ^ (row[i] & row[(i + 2) % width]) ^ (1 if i == width - 1 else 0)
        for i in range(width)
    )


def _transition_global_asym(state):
    row = tuple(int(v) for v in state)
    width = len(row)
    parity = sum(row) % 2
    return tuple(
        (row[(i + 1) % width] & (1 - row[(i + 2) % width]))
        ^ (parity if i == 0 else row[i])
        ^ (1 if i == 2 else 0)
        for i in range(width)
    )


def _transition(family: str, state):
    if family == 'nonlinear_local':
        return _transition_nonlinear_local(state)
    if family == 'global_asym':
        return _transition_global_asym(state)
    raise ValueError('unknown transition family')


def _primitive_budget(width: int) -> int:
    return 8 * int(width) - 4


def _initial_pool_size(width: int) -> int:
    width = int(width)
    return width * (width - 1)


def _query_budget(width: int) -> int:
    # Intentionally tighter than R2.37 so the language itself, rather than a larger
    # evidence allowance, must carry the causal gain.
    return _initial_pool_size(width) + 3 * int(width)


@lru_cache(maxsize=4)
def _proposals_universe(width: int):
    width = int(width)
    proposals = synthesize_operator_proposals(width, max_nodes=3, primitive_budget=_primitive_budget(width))
    universe = enumerate_query_universe(width)
    cost3 = tuple(p for p in proposals if p.mdl_cost == 3)
    if not cost3:
        raise RuntimeError('R2.38 requires cost-3 target candidates')
    return proposals, universe, cost3


@lru_cache(maxsize=8)
def _prepared(width: int, family: str):
    proposals, universe, cost3 = _proposals_universe(width)
    predictions = {
        q.query_id: {
            p.operator_id: _transition(family, apply_operator(p.program, q.before)) == apply_operator(p.program, q.after)
            for p in proposals
        }
        for q in universe
    }
    return proposals, universe, predictions, cost3


def _target_index(width: int, family: str, episode_key: int, count: int) -> int:
    digest = hashlib.sha256(f'r238-target:{width}:{family}:{int(episode_key)}'.encode()).hexdigest()
    return int(digest[:16], 16) % count


@lru_cache(maxsize=128)
def _truth(width: int, family: str, episode_key: int):
    proposals, universe, predictions, cost3 = _prepared(width, family)
    target = cost3[_target_index(width, family, episode_key, len(cost3))]
    atom_labels = {
        q.query_id: _transition(family, apply_operator(target.program, q.before)) == apply_operator(target.program, q.after)
        for q in universe
    }
    signature = tuple(atom_labels[q.query_id] for q in universe)
    equivalent = frozenset(
        p.operator_id
        for p in proposals
        if tuple(predictions[q.query_id][p.operator_id] for q in universe) == signature
    )
    return target.operator_id, atom_labels, equivalent


def _observation(episode_key: int, regime: str, probe, label: bool) -> VerifierObservation:
    if regime == 'clean':
        return VerifierObservation(probe.probe_id, bool(label), .995)
    if regime != 'noisy':
        raise ValueError('unknown verifier regime')
    digest = hashlib.sha256(f'r238-noise:{int(episode_key)}:{probe.probe_id}'.encode()).hexdigest()
    if int(digest[:8], 16) % 31 == 0:
        return VerifierObservation(probe.probe_id, not bool(label), .62)
    return VerifierObservation(probe.probe_id, bool(label), .985)


def run_episode(width: int, family: str, episode_key: int, regime: str, mode: str) -> dict:
    width = int(width)
    proposals, universe, predictions, _ = _prepared(width, family)
    _, atom_labels, equivalent = _truth(width, family, int(episode_key))
    pool = initial_query_pool(
        universe,
        _initial_pool_size(width),
        salt=f'r238-pool:{width}:{family}:{int(episode_key)}:{regime}',
    )

    def verifier(probe):
        label = evaluate_probe(probe, atom_labels)
        return _observation(int(episode_key), str(regime), probe, label)

    decision = discover_with_compositional_probes(
        proposals,
        universe,
        pool,
        predictions,
        verifier=verifier,
        counterexample_check=lambda proposal: proposal.operator_id in equivalent,
        query_budget=_query_budget(width),
        accept_probability=ACCEPT_PROBABILITY,
        accept_margin=ACCEPT_MARGIN,
        max_mdl_cost=MAX_MDL_COST,
        complexity_weight=COMPLEXITY_WEIGHT,
        atom_shortlist_size=ATOM_SHORTLIST_SIZE,
        mode=str(mode),
    )
    correct = decision.status == 'accept' and decision.operator_id in equivalent
    false_accept = decision.status == 'accept' and decision.operator_id not in equivalent
    return {
        'schema_version': 1,
        'milestone': 'R2.38 Compositional Probe-Language Synthesis',
        'width': width,
        'family': str(family),
        'episode_key': int(episode_key),
        'regime': str(regime),
        'mode': str(mode),
        'proposal_count': len(proposals),
        'universe_size': len(universe),
        'initial_pool_size': len(pool),
        'query_budget': _query_budget(width),
        'status': decision.status,
        'correct': bool(correct),
        'false_accept': bool(false_accept),
        'queries_used': len(decision.queries),
        'composite_probe_count': len(decision.composite_probe_ids),
        'composite_probe_ids': list(decision.composite_probe_ids),
        'atomic_generated_query_count': len(decision.atomic_generated_query_ids),
        'synthesis_candidates_evaluated': decision.synthesis_candidates_evaluated,
        'posterior': decision.posterior,
        'margin': decision.margin,
        'reason': decision.reason,
    }


def _aggregate(rows, family: str) -> dict:
    subset = [r for r in rows if r['family'] == family]
    comp = [r for r in subset if r['mode'] == 'compositional']
    atom = [r for r in subset if r['mode'] == 'atomic_only']
    pool = [r for r in subset if r['mode'] == 'pool_only']
    return {
        'episodes_per_mode': len(comp),
        'compositional_correct': sum(r['correct'] for r in comp),
        'atomic_only_correct': sum(r['correct'] for r in atom),
        'pool_only_correct': sum(r['correct'] for r in pool),
        'composite_probe_count': sum(r['composite_probe_count'] for r in comp),
        'compositional_mean_queries': sum(r['queries_used'] for r in comp) / len(comp),
        'atomic_only_mean_queries': sum(r['queries_used'] for r in atom) / len(atom),
    }


def run_dev_matrix() -> dict:
    rows = [
        run_episode(3, 'nonlinear_local', seed, regime, mode)
        for regime in DEV_REGIMES
        for seed in DEV_SEEDS
        for mode in ('compositional', 'atomic_only', 'pool_only')
    ]
    summary = _aggregate(rows, 'nonlinear_local')
    comp = [r for r in rows if r['mode'] == 'compositional']
    gates = {
        'compositional_all_correct': summary['compositional_correct'] == summary['episodes_per_mode'],
        'strictly_beats_pool_only': summary['compositional_correct'] > summary['pool_only_correct'],
        'beats_atomic_correctness_or_efficiency': (
            summary['compositional_correct'] > summary['atomic_only_correct'] or
            (
                summary['compositional_correct'] == summary['atomic_only_correct'] and
                summary['compositional_mean_queries'] < summary['atomic_only_mean_queries']
            )
        ),
        'composite_language_exercised': summary['composite_probe_count'] > 0 and all(r['composite_probe_count'] > 0 for r in comp),
        'zero_false_accepts': not any(r['false_accept'] for r in rows),
        'same_total_budget': len({r['query_budget'] for r in rows}) == 1,
    }
    return {'schema_version': 1, 'rows': rows, 'summary': summary, 'gates': gates, 'all_gates_pass': all(gates.values())}


def dry_run_transfer_family() -> dict:
    rows = [
        run_episode(4, 'global_asym', seed, regime, mode)
        for regime in DEV_REGIMES
        for seed in TRANSFER_DRY_RUN_SEEDS
        for mode in ('compositional', 'atomic_only', 'pool_only')
    ]
    summary = _aggregate(rows, 'global_asym')
    comp = [r for r in rows if r['mode'] == 'compositional']
    gates = {
        'compositional_all_correct': summary['compositional_correct'] == summary['episodes_per_mode'],
        'composite_language_exercised': all(r['composite_probe_count'] > 0 for r in comp),
        'zero_false_accepts': not any(r['false_accept'] for r in rows),
        'same_generator_code_path': 'family' not in inspect.signature(synthesize_compositional_probe).parameters,
        'same_budget': len({r['query_budget'] for r in rows}) == 1,
    }
    return {'schema_version': 1, 'rows': rows, 'summary': summary, 'gates': gates, 'all_gates_pass': all(gates.values())}
