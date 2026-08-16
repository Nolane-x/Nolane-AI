from __future__ import annotations

from collections import Counter
from functools import lru_cache
import json
from pathlib import Path

from cogcoder.r219_representation_types import VerifierObservation
from cogcoder.r220_language_synthesis import synthesize_operator_proposals
from cogcoder.r220_operator_discovery import (
    discover_operator,
    initial_proposal_supports,
    update_proposal_supports,
    choose_operator_query,
)
from cogcoder.r221_adaptive_evidence import discover_operator_adaptive
from cogcoder.r222_counterfactual_trainer import (
    PolicyBundle,
    simulate_channel_observation,
    train_voi_policy,
)
from cogcoder.r222_learned_voi import route_with_learned_voi
from cogcoder.r222_voi_types import VerifierChannel, VerifierRegime
from cogcoder.r222_value_model import RidgeValueModel

from . import r220_language_synthesis as r220

LAMBDA_COST = 0.15
ROLLOUT_DEPTH = 2
TRAIN_MAX_STEPS = 20
MAX_QUERIES = 32
MODEL_L2 = 0.02

TRAINING_SEEDS = (91103, 91229, 91419, 91577, 91811)
DEVELOPMENT_SEEDS = (93103, 93229, 93419)

TRAINING_REGIMES = (
    VerifierRegime('train-balanced', VerifierChannel('cheap', .72, 1.0), VerifierChannel('strong', .96, 3.8)),
    VerifierRegime('train-cheap-good', VerifierChannel('cheap', .84, .8), VerifierChannel('strong', .985, 5.2)),
    VerifierRegime('train-cheap-noisy', VerifierChannel('cheap', .63, .55), VerifierChannel('strong', .93, 2.4)),
    VerifierRegime('train-mid', VerifierChannel('cheap', .77, 1.35), VerifierChannel('strong', .95, 3.1)),
    VerifierRegime('train-floor', VerifierChannel('cheap', .53, .28), VerifierChannel('strong', .96, 3.0)),
    VerifierRegime('train-low', VerifierChannel('cheap', .58, .45), VerifierChannel('strong', .98, 4.0)),
    VerifierRegime('train-highcheap', VerifierChannel('cheap', .89, .72), VerifierChannel('strong', .98, 5.8)),
    VerifierRegime('train-highcoststrong', VerifierChannel('cheap', .84, 1.05), VerifierChannel('strong', .995, 7.5)),
)

DEVELOPMENT_REGIMES = (
    VerifierRegime('dev-balanced-shift', VerifierChannel('cheap', .76, .9), VerifierChannel('strong', .975, 4.1)),
    VerifierRegime('dev-noisy-cheap-shift', VerifierChannel('cheap', .59, .42), VerifierChannel('strong', .955, 2.9)),
    VerifierRegime('dev-expensive-strong-shift', VerifierChannel('cheap', .87, 1.15), VerifierChannel('strong', .99, 6.4)),
)

HELDOUT_REGIMES = (
    VerifierRegime('heldout-r1', VerifierChannel('cheap', .67, .62), VerifierChannel('strong', .982, 4.8)),
    VerifierRegime('heldout-r2', VerifierChannel('cheap', .89, 1.40), VerifierChannel('strong', .945, 2.65)),
    VerifierRegime('heldout-r3', VerifierChannel('cheap', .57, .33), VerifierChannel('strong', .991, 5.7)),
)


@lru_cache(maxsize=1)
def _proposals():
    return synthesize_operator_proposals(
        r220.WIDTH, max_nodes=r220.MAX_NODES, primitive_budget=r220.PRIMITIVE_BUDGET
    )


@lru_cache(maxsize=1)
def get_policy_bundle() -> PolicyBundle:
    return train_voi_policy(
        TRAINING_REGIMES,
        TRAINING_SEEDS,
        lambda_cost=LAMBDA_COST,
        rollout_depth=ROLLOUT_DEPTH,
        max_steps=TRAIN_MAX_STEPS,
        l2=MODEL_L2,
    )


@lru_cache(maxsize=1)
def _get_no_cost_policy() -> PolicyBundle:
    payload = json.loads(
        (Path(__file__).with_name('r222_no_cost_policy.json')).read_text(encoding='utf-8')
    )
    models = {
        action: RidgeValueModel(
            tuple(payload['models'][action]['weights']),
            payload['models'][action]['l2'],
        )
        for action in ('stop', 'cheap', 'strong')
    }
    bundle = PolicyBundle(
        models=models,
        training_regime_ids=tuple(payload['training_regime_ids']),
        training_seed_count=payload['training_seed_count'],
        example_count=payload['example_count'],
        lambda_cost=payload['lambda_cost'],
        rollout_depth=payload['rollout_depth'],
        max_steps=payload['max_steps'],
        l2=payload['l2'],
    )
    if bundle.lambda_cost != 0.0:
        raise ValueError('no-cost ablation artifact must have lambda_cost=0')
    if bundle.training_regime_ids != tuple(r.regime_id for r in TRAINING_REGIMES):
        raise ValueError('no-cost ablation training regimes do not match production curriculum')
    return bundle


@lru_cache(maxsize=128)
def _episode_material(seed: int):
    target = r220._target(seed)
    proposals = _proposals()
    rows = r220._raw_rows(target, r220._latent_step_a)
    predictions = r220._predictions(proposals, rows, r220._latent_step_a)
    byrow = {row[0]: row for row in rows}
    equiv = set(r220._target_equiv(proposals, target, rows, r220._latent_step_a))
    return target, proposals, rows, predictions, byrow, equiv


def _verifiers(seed: int, regime: VerifierRegime, byrow):
    return {
        regime.cheap.name: lambda q: simulate_channel_observation(seed, regime, regime.cheap, byrow[q]),
        regime.strong.name: lambda q: simulate_channel_observation(seed, regime, regime.strong, byrow[q]),
    }


def _correct(decision, equiv: set[str]) -> bool:
    return decision.status == 'accept' and decision.operator_id in equiv


def _net_utility(correct: bool, cost: float, regime: VerifierRegime) -> float:
    scale = len(r220._raw_rows(r220._target(0), r220._latent_step_a)) * max(regime.cheap.cost, regime.strong.cost)
    return (1.0 if correct else 0.0) - LAMBDA_COST * (float(cost) / scale)


def _always_channel(seed: int, regime: VerifierRegime, channel: VerifierChannel):
    _, proposals, rows, predictions, byrow, equiv = _episode_material(seed)
    decision = discover_operator(
        proposals, tuple(row[0] for row in rows), predictions,
        verifier=lambda q: simulate_channel_observation(seed, regime, channel, byrow[q]),
        counterexample_check=lambda p: p.operator_id in equiv,
        query_budget=MAX_QUERIES,
        accept_probability=r220.ACCEPT_PROBABILITY,
        accept_margin=r220.ACCEPT_MARGIN,
        max_mdl_cost=r220.MAX_MDL_COST,
        complexity_weight=r220.COMPLEXITY_WEIGHT,
    )
    cost = len(decision.queries) * channel.cost
    correct = _correct(decision, equiv)
    return {'correct': correct, 'cost': cost, 'queries': len(decision.queries), 'net_utility': _net_utility(correct, cost, regime)}


def _always_max(seed: int, regime: VerifierRegime):
    _, proposals, rows, predictions, byrow, equiv = _episode_material(seed)
    supports = initial_proposal_supports(proposals, complexity_weight=r220.COMPLEXITY_WEIGHT)
    remaining = [row[0] for row in rows]
    used = []
    for _ in range(min(MAX_QUERIES, len(remaining))):
        q = choose_operator_query(proposals, supports, remaining, predictions)
        obs = simulate_channel_observation(seed, regime, regime.strong, byrow[q])
        supports = update_proposal_supports(proposals, supports, obs, predictions[q])
        used.append(q)
        remaining.remove(q)
    ranked = sorted(supports, key=lambda s: (-s.posterior, s.operator_id))
    top = ranked[0]
    second = ranked[1].posterior if len(ranked) > 1 else 0.0
    margin = top.posterior - second
    correct = top.operator_id in equiv and top.posterior >= r220.ACCEPT_PROBABILITY and margin >= r220.ACCEPT_MARGIN
    cost = len(used) * regime.strong.cost
    return {'correct': correct, 'cost': cost, 'queries': len(used), 'net_utility': _net_utility(correct, cost, regime)}


def _r221_strong(seed: int, regime: VerifierRegime):
    _, proposals, rows, predictions, byrow, equiv = _episode_material(seed)
    decision = discover_operator_adaptive(
        proposals, tuple(row[0] for row in rows), predictions,
        verifier=lambda q: simulate_channel_observation(seed, regime, regime.strong, byrow[q]),
        counterexample_check=lambda p: p.operator_id in equiv,
        base_budget=12, max_budget=24,
        accept_probability=r220.ACCEPT_PROBABILITY,
        accept_margin=r220.ACCEPT_MARGIN,
        max_mdl_cost=r220.MAX_MDL_COST,
        complexity_weight=r220.COMPLEXITY_WEIGHT,
        continuation_min_disagreement=.01,
        recoverability_floor=.01,
    )
    correct = decision.status == 'accept' and decision.operator_id in equiv
    cost = len(decision.queries) * regime.strong.cost
    return {'correct': correct, 'cost': cost, 'queries': len(decision.queries), 'net_utility': _net_utility(correct, cost, regime)}


def _run_policy(seed: int, regime: VerifierRegime, policy: PolicyBundle):
    _, proposals, rows, predictions, byrow, equiv = _episode_material(seed)
    decision = route_with_learned_voi(
        proposals, tuple(row[0] for row in rows), predictions,
        regime=regime,
        policy=policy,
        verifier_by_channel=_verifiers(seed, regime, byrow),
        counterexample_check=lambda p: p.operator_id in equiv,
        max_queries=MAX_QUERIES,
        accept_probability=r220.ACCEPT_PROBABILITY,
        accept_margin=r220.ACCEPT_MARGIN,
        max_mdl_cost=r220.MAX_MDL_COST,
        complexity_weight=r220.COMPLEXITY_WEIGHT,
    )
    correct = _correct(decision, equiv)
    return decision, correct


def run_ambiguous_case(regime: VerifierRegime) -> dict:
    proposals = _proposals()[:2]
    a, b = proposals
    predictions = {
        f'amb{i}': {a.operator_id: bool(i % 2), b.operator_id: bool(i % 2)}
        for i in range(8)
    }
    decision = route_with_learned_voi(
        proposals, tuple(predictions), predictions,
        regime=regime, policy=get_policy_bundle(),
        verifier_by_channel={
            regime.cheap.name: lambda q: VerifierObservation(q, predictions[q][a.operator_id], regime.cheap.reliability),
            regime.strong.name: lambda q: VerifierObservation(q, predictions[q][a.operator_id], regime.strong.reliability),
        },
        counterexample_check=lambda p: True,
        max_queries=8, accept_probability=.9, accept_margin=.5,
        max_mdl_cost=3, complexity_weight=0.0,
    )
    return {'abstained': decision.status == 'abstain', 'false_accept': decision.status == 'accept', 'decision': decision}


def run_r222(seed: int, regime: VerifierRegime, *, heldout: bool = False) -> dict:
    seed = int(seed)
    policy = get_policy_bundle()
    learned, learned_correct = _run_policy(seed, regime, policy)
    no_cost_decision, no_cost_correct = _run_policy(seed, regime, _get_no_cost_policy())
    strong = _always_channel(seed, regime, regime.strong)
    cheap = _always_channel(seed, regime, regime.cheap)
    always_max = _always_max(seed, regime)
    r221 = _r221_strong(seed, regime)
    learned_net = _net_utility(learned_correct, learned.total_cost, regime)
    no_cost_net = _net_utility(no_cost_correct, no_cost_decision.total_cost, regime)

    gates = {
        'learned_policy_correct': learned_correct,
        'learned_cost_below_always_strong': learned.total_cost < strong['cost'],
        'learned_cost_below_always_max': learned.total_cost < always_max['cost'],
        'cost_aware_training_beats_no_cost_ablation': learned_net > no_cost_net + 1e-12 or (learned_correct == no_cost_correct and learned.total_cost < no_cost_decision.total_cost),
        'fixed_action_ablation_fails_tradeoff': (not cheap['correct']) or (learned_correct and learned.total_cost < strong['cost']),
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.22 Learned/Transferable Value-of-Information Control',
        'seed': seed,
        'heldout': bool(heldout),
        'regime': {
            'regime_id': regime.regime_id,
            'cheap': {'reliability': regime.cheap.reliability, 'cost': regime.cheap.cost},
            'strong': {'reliability': regime.strong.reliability, 'cost': regime.strong.cost},
        },
        'policy': {'bundle_hash': policy.bundle_hash, 'training_regime_ids': list(policy.training_regime_ids), 'example_count': policy.example_count},
        'learned': {
            'correct': learned_correct,
            'status': learned.status,
            'queries': len(learned.queries),
            'channels': list(learned.channels),
            'actions': list(learned.actions),
            'cost': learned.total_cost,
            'net_utility': learned_net,
        },
        'r221_strong_heuristic': r221,
        'always_strong': strong,
        'always_cheap': cheap,
        'always_max': always_max,
        'no_cost_ablation': {
            'correct': no_cost_correct,
            'cost': no_cost_decision.total_cost,
            'net_utility': no_cost_net,
            'actions': list(no_cost_decision.actions),
        },
        'gates': gates,
        'all_gates_pass': all(gates.values()),
        'claims': {
            'agi_claim': False,
            'broad_generalization_claim': False,
            'boundary': 'Learned evidence-routing policy over the bounded R2.20 operator environment; not unrestricted metareasoning or AGI.',
        },
    }


def run_dev_matrix() -> dict:
    rows = [run_r222(seed, regime) for regime in DEVELOPMENT_REGIMES for seed in DEVELOPMENT_SEEDS]
    counts = Counter(action for row in rows for action in row['learned']['actions'])
    correct_accepts = sum(bool(row['learned']['correct']) for row in rows)
    false_accepts = sum(row['learned']['status'] == 'accept' and not row['learned']['correct'] for row in rows)
    abstentions = sum(row['learned']['status'] == 'abstain' for row in rows)
    return {
        'episodes': len(rows),
        'all_correct': correct_accepts == len(rows),
        'correct_accepts': correct_accepts,
        'false_accepts': false_accepts,
        'abstentions': abstentions,
        'mean_learned_cost': sum(row['learned']['cost'] for row in rows) / len(rows),
        'mean_no_cost_cost': sum(row['no_cost_ablation']['cost'] for row in rows) / len(rows),
        'mean_always_strong_cost': sum(row['always_strong']['cost'] for row in rows) / len(rows),
        'mean_always_max_cost': sum(row['always_max']['cost'] for row in rows) / len(rows),
        'action_counts': {a: counts.get(a, 0) for a in ('stop', 'cheap', 'strong')},
        'strong_only_collapse': counts.get('strong', 0) > 0 and counts.get('cheap', 0) == 0,
        'rows': rows,
    }
