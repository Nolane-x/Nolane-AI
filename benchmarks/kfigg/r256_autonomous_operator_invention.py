from __future__ import annotations

import copy
from dataclasses import dataclass

from cogcoder.r253_external_cognition import CognitiveOperatorRegistry, CognitiveOperatorSpec, ExternalWorkingState
from cogcoder.r255_lifecycle import ProcedureLifecycleLedger
from cogcoder.r256_operator_invention import AutonomousOperatorInventionEngine, OperatorExample, OperatorInventionNeed


@dataclass(frozen=True, slots=True)
class Episode:
    name: str
    fields: tuple[str, ...]
    constants: tuple[object, ...]
    max_depth: int
    train: tuple[OperatorExample, ...]
    challenges: tuple[OperatorExample, ...]
    live: OperatorExample
    max_candidates: int = 8000
    rollback_context: dict[str, object] | None = None


def _e(name: str, expected: object, **context: object) -> OperatorExample:
    return OperatorExample(name, context, expected)


def _episodes() -> tuple[Episode, ...]:
    return (
        Episode(
            'opaque-identity-cegis', ('q9',), (1,), 0,
            (_e('train-a', 1, q9=1),),
            (_e('held-a', 2, q9=2), _e('held-b', 7, q9=7)),
            _e('live', -3, q9=-3),
        ),
        Episode(
            'offset-plus-one', ('m4',), (1,), 1,
            (_e('train-a', 2, m4=1), _e('train-b', 5, m4=4)),
            (_e('held-a', -1, m4=-2), _e('held-b', 11, m4=10)),
            _e('live', 21, m4=20),
        ),
        Episode(
            'absolute-scalar', ('r2',), (), 1,
            (_e('train-a', 4, r2=-4), _e('train-b', 2, r2=2)),
            (_e('held-a', 9, r2=-9), _e('held-b', 0, r2=0)),
            _e('live', 7, r2=-7),
        ),
        Episode(
            'numeric-negation', ('v8',), (), 1,
            (_e('train-a', -3, v8=3), _e('train-b', 2, v8=-2)),
            (_e('held-a', -5, v8=5), _e('held-b', 8, v8=-8)),
            _e('live', -11, v8=11),
        ),
        Episode(
            'pair-addition', ('a7', 'b3'), (), 1,
            (_e('train-a', 3, a7=1, b3=2), _e('train-b', 3, a7=4, b3=-1)),
            (_e('held-a', 13, a7=8, b3=5), _e('held-b', -9, a7=-2, b3=-7)),
            _e('live', 17, a7=12, b3=5),
        ),
        Episode(
            'pair-maximum', ('c4', 'd6'), (), 1,
            (_e('train-a', 2, c4=1, d6=2), _e('train-b', 5, c4=5, d6=3)),
            (_e('held-a', -1, c4=-1, d6=-4), _e('held-b', 9, c4=7, d6=9)),
            _e('live', 14, c4=14, d6=8),
        ),
        Episode(
            'guarded-ratio', ('n2', 'k5'), (), 1,
            (_e('train-a', 2.0, n2=4, k5=2), _e('train-b', 3.0, n2=9, k5=3)),
            (_e('held-a', 2.5, n2=10, k5=4), _e('held-b', -4.0, n2=-8, k5=2)),
            _e('live', 7.0, n2=21, k5=3),
            rollback_context={'n2': 5, 'k5': 0, 'sentinel': {'keep': [1, 2, 3]}},
        ),
        Episode(
            'absolute-difference', ('u1', 'u8'), (), 2,
            (_e('train-a', 3, u1=5, u8=2), _e('train-b', 3, u1=2, u8=5)),
            (_e('held-a', 5, u1=-1, u8=4), _e('held-b', 12, u1=10, u8=-2)),
            _e('live', 5, u1=8, u8=3),
            max_candidates=12000,
        ),
        Episode(
            'strip-and-lower', ('s5',), (), 2,
            (_e('train-a', 'a', s5=' A '), _e('train-b', 'hello', s5='  HELLO')),
            (_e('held-a', 'world', s5='World  '), _e('held-b', 'x y', s5=' x Y ')),
            _e('live', 'mixed case', s5='  MIXED Case '),
            max_candidates=4000,
        ),
    )


def _parent_registry() -> CognitiveOperatorRegistry:
    def keep(state, _snapshot, _signal):
        return {'success': True, 'updates': {'known.out': state.context.get('known.in')}, 'provides': {'known.out'}}

    def zero(_state, _snapshot, _signal):
        return {'success': True, 'updates': {'known.zero': 0}, 'provides': {'known.zero'}}

    return CognitiveOperatorRegistry((
        CognitiveOperatorSpec('known.copy', 'known', frozenset({'known'}), frozenset({'known.in'}), frozenset({'known.out'}), 1.0, 0.0, 'pure', '1', 'nolane://known/copy', keep),
        CognitiveOperatorSpec('known.zero', 'known', frozenset({'known'}), frozenset(), frozenset({'known.zero'}), 1.0, 0.0, 'pure', '1', 'nolane://known/zero', zero),
    ))


def _baseline_can_solve(registry: CognitiveOperatorRegistry, output_field: str) -> bool:
    return any(output_field in op.provides for op in registry.operators())


def run_benchmark() -> dict[str, object]:
    receipts: list[dict[str, object]] = []
    exact = 0
    false_accepts = 0
    baseline_exact = 0
    promoted_count = 0
    live_exact_count = 0
    rollback_count = 0
    cegis_count = 0
    max_search = 0

    for index, episode in enumerate(_episodes()):
        parent = _parent_registry()
        output_field = f'out_{index:02d}'
        baseline_exact += int(_baseline_can_solve(parent, output_field))
        lifecycle = ProcedureLifecycleLedger()
        engine = AutonomousOperatorInventionEngine(parent, lifecycle)
        need = OperatorInventionNeed(
            objective=f'invent missing pure operator for opaque episode {index}',
            field_names=episode.fields,
            output_field=output_field,
            constants=episode.constants,
            max_depth=episode.max_depth,
            max_candidates=episode.max_candidates,
        )
        receipt = engine.synthesize_and_challenge(
            need,
            episode.train,
            episode.challenges,
            max_cegis_rounds=3,
        )
        max_search = max(max_search, receipt.search_evaluations)
        if not receipt.passed or receipt.candidate is None:
            receipts.append({
                'episode': episode.name,
                'passed': False,
                'reason': receipt.reason,
                'search_evaluations': receipt.search_evaluations,
                'cegis_rounds': receipt.cegis_rounds,
            })
            continue

        promoted = engine.promote(receipt)
        promoted_count += 1
        cegis_count += int(receipt.cegis_rounds > 0)
        state = ExternalWorkingState(context=dict(episode.live.context))
        live = engine.execute_promoted(promoted.operator.operator_id, state)
        live_exact = bool(live.success and state.context.get(output_field) == episode.live.expected)
        live_exact_count += int(live_exact)
        episode_exact = bool(live_exact and all(row.passed for row in receipt.challenge_results))
        exact += int(episode_exact)
        false_accepts += int(receipt.passed and not episode_exact)

        rollback_contained = False
        if episode.rollback_context is not None:
            failing = ExternalWorkingState(context=copy.deepcopy(episode.rollback_context))
            before = copy.deepcopy(failing)
            failed = engine.execute_promoted(promoted.operator.operator_id, failing)
            rollback_contained = bool((not failed.success) and failed.rolled_back and failing == before)
            rollback_count += int(rollback_contained)

        receipts.append({
            'episode': episode.name,
            'passed': episode_exact,
            'expression': receipt.candidate.expression.to_data(),
            'expression_digest': receipt.candidate.expression_digest,
            'operator_id': promoted.operator.operator_id,
            'cegis_rounds': receipt.cegis_rounds,
            'training_examples_used': receipt.training_examples_used,
            'challenge_count': len(receipt.challenge_results),
            'search_evaluations': receipt.search_evaluations,
            'live_exact': live_exact,
            'rollback_contained': rollback_contained,
        })

    return {
        'milestone': 'R2.56',
        'capability': 'autonomous-pure-cognitive-operator-invention',
        'episodes': len(_episodes()),
        'exact': exact,
        'false_accepts': false_accepts,
        'r255_no_invention_baseline_exact': baseline_exact,
        'episodes_with_cegis_refinement': cegis_count,
        'episodes_with_promotion': promoted_count,
        'episodes_with_live_exact': live_exact_count,
        'episodes_with_transactional_rollback': rollback_count,
        'max_search_evaluations': max_search,
        'trainable_parameter_count': 0,
        'claim_boundary': 'Bounded deterministic invention inside a closed pure DSL; not arbitrary program synthesis or effectful tool invention.',
        'episode_receipts': receipts,
    }


if __name__ == '__main__':
    import json
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
