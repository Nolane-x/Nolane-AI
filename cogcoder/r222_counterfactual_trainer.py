from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from collections.abc import Mapping, Sequence

from benchmarks.kfigg import r220_language_synthesis as r220

from .r219_representation_types import VerifierObservation
from .r220_operator_discovery import (
    ProposalSupport,
    choose_operator_query,
    initial_proposal_supports,
    update_proposal_supports,
)
from .r222_voi_types import MetaState, VerifierChannel, VerifierRegime, extract_meta_features, expand_meta_features
from .r222_value_model import RidgeValueModel

ACTIONS = ('stop', 'cheap', 'strong')


@dataclass(frozen=True)
class TrainingExample:
    features: tuple[float, ...]
    action_values: Mapping[str, float]
    best_action: str

    def __post_init__(self) -> None:
        if set(self.action_values) != set(ACTIONS):
            raise ValueError('action_values must cover all actions')
        if self.best_action not in ACTIONS:
            raise ValueError('invalid best_action')


@dataclass(frozen=True)
class PolicyBundle:
    models: Mapping[str, RidgeValueModel]
    training_regime_ids: tuple[str, ...]
    training_seed_count: int
    example_count: int
    lambda_cost: float
    rollout_depth: int
    max_steps: int
    l2: float

    def __post_init__(self) -> None:
        if set(self.models) != set(ACTIONS):
            raise ValueError('models must cover all actions')

    def to_payload(self) -> dict:
        return {
            'schema_version': 1,
            'actions': list(ACTIONS),
            'models': {a: self.models[a].to_payload() for a in ACTIONS},
            'training_regime_ids': list(self.training_regime_ids),
            'training_seed_count': int(self.training_seed_count),
            'example_count': int(self.example_count),
            'lambda_cost': float(self.lambda_cost),
            'rollout_depth': int(self.rollout_depth),
            'max_steps': int(self.max_steps),
            'l2': float(self.l2),
        }

    def to_canonical_json(self) -> str:
        return json.dumps(self.to_payload(), sort_keys=True, separators=(',', ':'), allow_nan=False)

    @property
    def bundle_hash(self) -> str:
        return hashlib.sha256(self.to_canonical_json().encode('utf-8')).hexdigest()


@lru_cache(maxsize=1)
def _proposal_library():
    return r220.synthesize_operator_proposals(
        r220.WIDTH,
        max_nodes=r220.MAX_NODES,
        primitive_budget=r220.PRIMITIVE_BUDGET,
    )


def _rank(supports: Sequence[ProposalSupport]) -> tuple[ProposalSupport, ...]:
    return tuple(sorted(supports, key=lambda s: (-s.posterior, s.operator_id)))


def _max_disagreement(
    supports: Sequence[ProposalSupport],
    remaining: Sequence[str],
    predictions: Mapping[str, Mapping[str, bool]],
) -> float:
    if not remaining:
        return 0.0
    post = {s.operator_id: s.posterior for s in supports}
    best = 0.0
    for q in remaining:
        p_true = sum(post[oid] for oid, label in predictions[q].items() if bool(label))
        best = max(best, 2.0 * p_true * (1.0 - p_true))
    return best


def _meta_state(
    supports: Sequence[ProposalSupport],
    remaining: Sequence[str],
    predictions: Mapping[str, Mapping[str, bool]],
    *,
    queries_used: int,
    max_queries: int,
    accumulated_cost: float,
    regime: VerifierRegime,
) -> MetaState:
    return MetaState(
        supports=tuple(supports),
        max_remaining_disagreement=_max_disagreement(supports, remaining, predictions),
        queries_used=queries_used,
        max_queries=max_queries,
        remaining_queries=len(remaining),
        accumulated_cost=accumulated_cost,
        cheap=regime.cheap,
        strong=regime.strong,
    )


def simulate_channel_observation(
    seed: int,
    regime: VerifierRegime,
    channel: VerifierChannel,
    row,
) -> VerifierObservation:
    qid, _, _, true_label = row
    digest = hashlib.sha256(
        f'r222|{int(seed)}|{regime.regime_id}|{channel.name}|{qid}'.encode('utf-8')
    ).digest()
    u = int.from_bytes(digest[:8], 'big') / float(2**64)
    observed = bool(true_label) if u < channel.reliability else (not bool(true_label))
    return VerifierObservation(str(qid), observed, channel.reliability)


def _correct_mass(supports: Sequence[ProposalSupport], equiv: set[str]) -> float:
    return sum(s.posterior for s in supports if s.operator_id in equiv)


def _stop_utility(supports: Sequence[ProposalSupport], equiv: set[str]) -> float:
    ranked = _rank(supports)
    top = ranked[0]
    second = ranked[1].posterior if len(ranked) > 1 else 0.0
    margin = top.posterior - second
    if top.posterior >= r220.ACCEPT_PROBABILITY and margin >= r220.ACCEPT_MARGIN:
        return 1.0 if top.operator_id in equiv else -1.0
    return 0.0


def _transition(
    *,
    action: str,
    seed: int,
    regime: VerifierRegime,
    supports: Sequence[ProposalSupport],
    remaining: Sequence[str],
    predictions: Mapping[str, Mapping[str, bool]],
    byrow: Mapping[str, tuple],
    proposals,
):
    if action == 'stop' or not remaining:
        return tuple(supports), tuple(remaining), 0.0
    channel = regime.cheap if action == 'cheap' else regime.strong
    q = choose_operator_query(proposals, supports, remaining, predictions)
    obs = simulate_channel_observation(seed, regime, channel, byrow[q])
    nxt = update_proposal_supports(proposals, supports, obs, predictions[q])
    rem = tuple(x for x in remaining if x != q)
    return tuple(nxt), rem, channel.cost


def _oracle_value(
    *,
    action: str,
    seed: int,
    regime: VerifierRegime,
    supports: Sequence[ProposalSupport],
    remaining: Sequence[str],
    predictions: Mapping[str, Mapping[str, bool]],
    byrow: Mapping[str, tuple],
    proposals,
    equiv: set[str],
    lambda_cost: float,
    depth: int,
    cost_horizon: int,
) -> float:
    if action == 'stop' or not remaining:
        return _stop_utility(supports, equiv)
    nxt, rem, query_cost = _transition(
        action=action, seed=seed, regime=regime, supports=supports, remaining=remaining,
        predictions=predictions, byrow=byrow, proposals=proposals,
    )
    # Dense teacher signal uses log posterior-mass gain, a bounded proxy for
    # information progress that does not vanish at the beginning of an episode.
    # Cost is normalized by the planned episode budget so lambda_cost prices
    # total evidence acquisition rather than a single query.
    scale = max(int(cost_horizon), 1) * max(regime.cheap.cost, regime.strong.cost)
    before_mass = max(_correct_mass(supports, equiv), 1e-15)
    after_mass = max(_correct_mass(nxt, equiv), 1e-15)
    progress_gain = 0.10 * (math.log(after_mass) - math.log(before_mass))
    immediate = progress_gain - float(lambda_cost) * (query_cost / scale)
    if depth <= 1 or not rem:
        return immediate + _stop_utility(nxt, equiv)
    future = max(
        _oracle_value(
            action=a, seed=seed, regime=regime, supports=nxt, remaining=rem,
            predictions=predictions, byrow=byrow, proposals=proposals, equiv=equiv,
            lambda_cost=lambda_cost, depth=depth - 1, cost_horizon=cost_horizon,
        )
        for a in ACTIONS
    )
    return immediate + future


def generate_training_examples(
    training_regimes: Sequence[VerifierRegime],
    training_seeds: Sequence[int],
    *,
    lambda_cost: float,
    rollout_depth: int,
    max_steps: int,
) -> tuple[TrainingExample, ...]:
    regimes = tuple(training_regimes)
    seeds = tuple(int(s) for s in training_seeds)
    if not regimes or not seeds:
        raise ValueError('training regimes and seeds must be non-empty')
    if len({r.regime_id for r in regimes}) != len(regimes):
        raise ValueError('training regime ids must be unique')
    proposals = _proposal_library()
    examples: list[TrainingExample] = []

    for regime in regimes:
        for seed in seeds:
            target = r220._target(seed)
            rows = r220._raw_rows(target, r220._latent_step_a)
            predictions = r220._predictions(proposals, rows, r220._latent_step_a)
            byrow = {row[0]: row for row in rows}
            equiv = set(r220._target_equiv(proposals, target, rows, r220._latent_step_a))
            supports = initial_proposal_supports(proposals, complexity_weight=r220.COMPLEXITY_WEIGHT)
            remaining = tuple(row[0] for row in rows)
            accumulated_cost = 0.0
            max_queries = min(int(max_steps), len(remaining))
            for step in range(max_queries):
                state = _meta_state(
                    supports, remaining, predictions,
                    queries_used=step, max_queries=max_queries,
                    accumulated_cost=accumulated_cost, regime=regime,
                )
                values = {
                    action: _oracle_value(
                        action=action, seed=seed, regime=regime, supports=supports,
                        remaining=remaining, predictions=predictions, byrow=byrow,
                        proposals=proposals, equiv=equiv, lambda_cost=float(lambda_cost),
                        depth=int(rollout_depth), cost_horizon=max_queries,
                    )
                    for action in ACTIONS
                }
                best = max(ACTIONS, key=lambda a: (values[a], -ACTIONS.index(a)))
                examples.append(TrainingExample(expand_meta_features(extract_meta_features(state)), values, best))
                if best == 'stop':
                    break
                supports, remaining, query_cost = _transition(
                    action=best, seed=seed, regime=regime, supports=supports,
                    remaining=remaining, predictions=predictions, byrow=byrow, proposals=proposals,
                )
                accumulated_cost += query_cost
                if not remaining:
                    break
    return tuple(examples)


def train_voi_policy(
    training_regimes: Sequence[VerifierRegime],
    training_seeds: Sequence[int],
    *,
    lambda_cost: float,
    rollout_depth: int,
    max_steps: int,
    l2: float,
) -> PolicyBundle:
    regimes = tuple(training_regimes)
    seeds = tuple(int(s) for s in training_seeds)
    examples = generate_training_examples(
        regimes, seeds, lambda_cost=lambda_cost, rollout_depth=rollout_depth, max_steps=max_steps,
    )
    rows = tuple(ex.features for ex in examples)

    # The metacontroller only needs *within-state* action ranking. Raw
    # counterfactual utilities span several orders of magnitude (early
    # information-gain states versus near-terminal success states), which
    # makes ordinary MSE overweight a small number of terminal examples.
    # Convert each state's utilities to centered, span-normalized relative
    # advantages before fitting; no oracle quantity is added to inference.
    relative_targets = {action: [] for action in ACTIONS}
    for ex in examples:
        values = [float(ex.action_values[action]) for action in ACTIONS]
        mean = sum(values) / len(values)
        span = max(values) - min(values)
        scale = span if span > 1e-12 else 1.0
        for action in ACTIONS:
            relative_targets[action].append((float(ex.action_values[action]) - mean) / scale)

    models = {
        action: RidgeValueModel.fit(rows, tuple(relative_targets[action]), l2=l2)
        for action in ACTIONS
    }
    return PolicyBundle(
        models=models,
        training_regime_ids=tuple(r.regime_id for r in regimes),
        training_seed_count=len(seeds),
        example_count=len(examples),
        lambda_cost=float(lambda_cost),
        rollout_depth=int(rollout_depth),
        max_steps=int(max_steps),
        l2=float(l2),
    )
