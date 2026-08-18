from __future__ import annotations

import copy
from dataclasses import dataclass

from cogcoder.r253_external_cognition import ExternalWorkingState
from cogcoder.r255_lifecycle import ProcedureLifecycleLedger
from cogcoder.r256_operator_dsl import Binary, Field
from cogcoder.r256_operator_invention import OperatorExample, OperatorInventionNeed
from cogcoder.r257_library_learning import (
    AbstractionCandidate,
    VerifiedExpression,
    learn_abstractions,
    promote_abstraction,
)
from cogcoder.r257_vocabulary import CognitiveVocabulary, evaluate_with_vocabulary
from cogcoder.r257_vocabulary_synthesis import (
    execute_with_live_verification,
    synthesize_base_with_budget,
    synthesize_with_vocabulary,
)


def _clamp_expr(value: str, lower: str, upper: str):
    return Binary('min', Binary('max', Field(value), Field(lower)), Field(upper))


def _lerp_expr(start: str, end: str, amount: str):
    return Binary('add', Field(start), Binary('mul', Field(amount), Binary('sub', Field(end), Field(start))))


def _normalize_expr(value: str, lower: str, upper: str):
    return Binary('div', Binary('sub', Field(value), Field(lower)), Binary('sub', Field(upper), Field(lower)))


def _training_corpus() -> tuple[VerifiedExpression, ...]:
    rows: list[VerifiedExpression] = []
    for i in range(6):
        rows.append(VerifiedExpression(f'c{i}', _clamp_expr(f'v{i}', f'p{i}', f'q{i}')))
        rows.append(VerifiedExpression(f'l{i}', _lerp_expr(f'r{i}', f's{i}', f't{i}')))
        rows.append(VerifiedExpression(f'n{i}', _normalize_expr(f'u{i}', f'w{i}', f'z{i}')))
    return tuple(rows)


def _candidate_for_prefix(candidates: tuple[AbstractionCandidate, ...], prefix: str) -> AbstractionCandidate:
    support = tuple(f'{prefix}{i}' for i in range(6))
    matching = [row for row in candidates if row.support_task_ids == support]
    if not matching:
        raise AssertionError(f'missing abstraction for support family {prefix}')
    # Prefer the full verified expression over a smaller subexpression from the same family.
    return max(matching, key=lambda row: (row.abstraction.template.cost, row.compression_gain, row.abstraction.abstraction_id))


def build_promoted_vocabulary() -> tuple[CognitiveVocabulary, ProcedureLifecycleLedger, tuple[AbstractionCandidate, ...]]:
    learned = learn_abstractions(_training_corpus())
    selected = (
        _candidate_for_prefix(learned.candidates, 'c'),
        _candidate_for_prefix(learned.candidates, 'l'),
        _candidate_for_prefix(learned.candidates, 'n'),
    )
    vocabulary = CognitiveVocabulary()
    lifecycle = ProcedureLifecycleLedger()
    challenges = (
        (selected[0], (VerifiedExpression('hc0', _clamp_expr('aa', 'bb', 'cc')), VerifiedExpression('hc1', _clamp_expr('dd', 'ee', 'ff')))),
        (selected[1], (VerifiedExpression('hl0', _lerp_expr('gg', 'hh', 'ii')), VerifiedExpression('hl1', _lerp_expr('jj', 'kk', 'll')))),
        (selected[2], (VerifiedExpression('hn0', _normalize_expr('mm', 'nn', 'oo')), VerifiedExpression('hn1', _normalize_expr('pp', 'qq', 'rr')))),
    )
    for candidate, heldout in challenges:
        if not promote_abstraction(candidate, heldout, vocabulary=vocabulary, lifecycle=lifecycle):
            raise AssertionError(f'failed to promote {candidate.abstraction.abstraction_id}')
    return vocabulary, lifecycle, selected


def _fraction(x: float, a: float, b: float) -> float:
    return min(max((x - a) / (b - a), 0.0), 1.0)


def _linearstep(x: float, a: float, b: float, fa: float, fb: float) -> float:
    t = _fraction(x, a, b)
    return fa + t * (fb - fa)


@dataclass(frozen=True, slots=True)
class Episode:
    name: str
    fields: tuple[str, str, str, str, str]
    bounds: tuple[float, float]
    endpoints: tuple[float, float]


def _episodes() -> tuple[Episode, ...]:
    return (
        Episode('e0', ('k0', 'k1', 'k2', 'k3', 'k4'), (0.0, 8.0), (2.0, 10.0)),
        Episode('e1', ('m7', 'm2', 'm9', 'm4', 'm1'), (-4.0, 4.0), (-2.0, 6.0)),
        Episode('e2', ('q3', 'q8', 'q1', 'q6', 'q0'), (2.0, 10.0), (-4.0, 4.0)),
        Episode('e3', ('z5', 'z0', 'z7', 'z2', 'z9'), (-8.0, 0.0), (1.0, 5.0)),
        Episode('e4', ('r4', 'r6', 'r3', 'r8', 'r1'), (4.0, 12.0), (-6.0, 2.0)),
        Episode('e5', ('p9', 'p5', 'p2', 'p7', 'p0'), (-2.0, 6.0), (3.0, 11.0)),
    )


def _probe_examples(ep: Episode) -> tuple[OperatorExample, ...]:
    x, a, b, _fa, _fb = ep.fields
    lo, hi = ep.bounds
    width = hi - lo
    points = (lo - width / 2, lo, lo + width / 4, lo + width / 2, lo + 3 * width / 4, hi, hi + width / 2)
    return tuple(OperatorExample(f'{ep.name}:probe:{i}', {x: px, a: lo, b: hi}, _fraction(px, lo, hi)) for i, px in enumerate(points))


def _full_examples(ep: Episode, *, challenge: bool = False) -> tuple[OperatorExample, ...]:
    x, a, b, fa, fb = ep.fields
    lo, hi = ep.bounds
    f0, f1 = ep.endpoints
    width = hi - lo
    fractions = (-0.5, 0.0, 0.25, 0.5, 0.75, 1.0, 1.5)
    if challenge:
        fractions = (-0.25, 0.125, 0.375, 0.625, 0.875, 1.25)
    rows = []
    for i, t in enumerate(fractions):
        px = lo + t * width
        rows.append(OperatorExample(
            f'{ep.name}:{"challenge" if challenge else "train"}:{i}',
            {x: px, a: lo, b: hi, fa: f0, fb: f1},
            _linearstep(px, lo, hi, f0, f1),
        ))
    return tuple(rows)


def _solve_episode(ep: Episode, vocabulary: CognitiveVocabulary) -> tuple[bool, bool, int, int, object | None]:
    x, a, b, fa, fb = ep.fields
    probe_need = OperatorInventionNeed(
        f'{ep.name}:discover-progress', (x, a, b), f'{ep.name}:progress',
        constants=(0, 1), max_depth=2, max_candidates=12000,
    )
    probe = synthesize_with_vocabulary(probe_need, _probe_examples(ep), vocabulary)
    if not probe.passed or probe.expression is None:
        return False, False, 0, probe.candidates_considered, None

    full_need = OperatorInventionNeed(
        f'{ep.name}:compose-output', (x, a, b, fa, fb), f'{ep.name}:out',
        constants=(0, 1), max_depth=3, max_candidates=1000,
    )
    train = _full_examples(ep)
    base = synthesize_base_with_budget(full_need, train)
    extended = synthesize_with_vocabulary(full_need, train, vocabulary, seed_expressions=(probe.expression,))
    if not extended.passed or extended.expression is None:
        return base.passed, False, extended.candidates_considered, probe.candidates_considered, None
    challenge_ok = all(
        evaluate_with_vocabulary(extended.expression, row.context, vocabulary) == row.expected
        for row in _full_examples(ep, challenge=True)
    )
    return base.passed, challenge_ok, extended.candidates_considered, probe.candidates_considered, extended.expression


def run_benchmark() -> dict[str, object]:
    vocabulary, lifecycle, selected = build_promoted_vocabulary()

    # Independent bad-candidate lifecycle: a compressed pattern that does not match its
    # challenge must never enter the usable vocabulary.
    bad_vocabulary = CognitiveVocabulary()
    bad_lifecycle = ProcedureLifecycleLedger()
    bad_ok = promote_abstraction(
        selected[0],
        (VerifiedExpression('bad-heldout', Binary('max', Field('x'), Field('lo'))),),
        vocabulary=bad_vocabulary,
        lifecycle=bad_lifecycle,
    )
    bad_candidate_quarantined = (
        (not bad_ok)
        and bad_lifecycle.state(selected[0].abstraction.abstraction_id) == 'quarantined'
        and bad_vocabulary.abstractions() == ()
    )

    receipts = []
    base_exact = 0
    extended_exact = 0
    false_accepts = 0
    first_expression = None
    first_episode = None
    for ep in _episodes():
        base_passed, challenge_ok, full_candidates, probe_candidates, expression = _solve_episode(ep, vocabulary)
        base_exact += int(base_passed)
        extended_exact += int(challenge_ok)
        false_accepts += int(expression is not None and not challenge_ok)
        if first_expression is None and expression is not None:
            first_expression = expression
            first_episode = ep
        receipts.append({
            'episode': ep.name,
            'base_passed': base_passed,
            'extended_challenge_exact': challenge_ok,
            'full_candidates_considered': full_candidates,
            'probe_candidates_considered': probe_candidates,
        })

    live_revocation_rollback = False
    if first_expression is not None and first_episode is not None:
        x, a, b, fa, fb = first_episode.fields
        lo, hi = first_episode.bounds
        f0, f1 = first_episode.endpoints
        state = ExternalWorkingState(context={x: (lo + hi) / 2, a: lo, b: hi, fa: f0, fb: f1, 'sentinel': {'keep': [1, 2, 3]}})
        before = copy.deepcopy(state)
        live = execute_with_live_verification(
            first_expression,
            state,
            output_field='live.out',
            expected=999999.0,
            vocabulary=vocabulary,
            lifecycle=lifecycle,
        )
        live_revocation_rollback = bool((not live.success) and live.rolled_back and state == before and len(vocabulary.abstractions()) < 3)

    return {
        'milestone': 'R2.57',
        'capability': 'verified-cognitive-vocabulary-growth',
        'learned_abstractions': len(selected),
        'abstraction_digests': [row.abstraction.abstraction_id for row in selected],
        'compression_gains': [row.compression_gain for row in selected],
        'all_positive_compression': all(row.compression_gain > 0 for row in selected),
        'min_support_tasks': min(len(row.support_task_ids) for row in selected),
        'heldout_episodes': len(_episodes()),
        'extended_exact': extended_exact,
        'base_exact': base_exact,
        'false_accepts': false_accepts,
        'bad_candidate_quarantined': bad_candidate_quarantined,
        'live_revocation_rollback': live_revocation_rollback,
        'trainable_parameter_count': 0,
        'claim_boundary': 'Bounded verified library learning over pure R2.56 expressions; not open-ended language or effectful operator invention.',
        'episode_receipts': receipts,
    }


if __name__ == '__main__':
    import json
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
