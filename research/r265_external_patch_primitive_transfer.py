from __future__ import annotations

from collections.abc import Callable

from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_expansion_proof import repository_content_digest
from cogcoder.r264_unified_adaptive_repository_search import solve_unified_adaptive_repository_patch
from cogcoder.r265_verified_patch_primitive_induction import (
    PatchPrimitiveGrammar,
    solve_repository_patch_with_primitive_induction,
)


def _candidate(candidate_id: str, *, target_expr: str, aux_expr: str = 'x + y', edits: int = 0) -> RepositoryPatchCandidate:
    files = {
        'leaf.py': f'def leaf(x, y):\n    return {target_expr}\n',
        'aux.py': f'def aux(x, y):\n    return {aux_expr}\n',
        'relay.py': 'from leaf import leaf\n\ndef relay(x, y):\n    return leaf(x, y)\n',
        'entry.py': (
            'from aux import aux\n'
            'from relay import relay\n\n'
            'def solve(x, y):\n'
            '    aux(x, y)\n'
            '    return relay(x, y)\n'
        ),
    }
    return RepositoryPatchCandidate(candidate_id, (), tuple(sorted(files.items())), 0, edits)


def _grammar() -> PatchPrimitiveGrammar:
    return PatchPrimitiveGrammar(
        allowed_slots=('binop',),
        allowed_operations=('replace',),
        allowed_target_values=('Add', 'Sub', 'Mult', 'Div', 'FloorDiv', 'Mod'),
        max_hypotheses=64,
    )


def _normalize_scalar(value: object) -> object:
    item = getattr(value, 'item', None)
    if callable(item):
        try:
            value = item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, bool): return bool(value)
    if isinstance(value, int): return int(value)
    if isinstance(value, float): return float(value)
    return value


def _counted_oracle(target: Callable[[object, object], object]):
    calls = {'count': 0}
    def wrapped(x: object, y: object) -> object:
        calls['count'] += 1
        return _normalize_scalar(target(x, y))
    return wrapped, calls


def _challenges() -> tuple[RepositoryProbe, ...]:
    return tuple(RepositoryProbe(args) for args in (
        (4, 3), (7, 2), (9, 4), (-3, 5), (6, -2), (-7, -3), (11, 6), (-9, 8),
    ))


def _final_inputs() -> tuple[RepositoryProbe, ...]:
    xs = tuple(range(-30, -15))
    ys = tuple(range(16, 31))
    return tuple(RepositoryProbe((x, y)) for x in xs for y in ys)


def run_external_transfer(
    external_callable: Callable[[object, object], object],
    *,
    source_id: str,
    source_version: str,
) -> dict[str, object]:
    if not callable(external_callable):
        raise TypeError('external_callable must be callable')
    if not source_id or not source_version:
        raise ValueError('source_id and source_version must be non-empty')

    source = _candidate('r265:external:source', target_expr='x + y')
    wrong = _candidate('r265:external:wrong-sub', target_expr='x - y', edits=1)
    target = _candidate('r265:external:target-evaluation-only', target_expr='x * y', edits=1)
    target_digest = repository_content_digest(target)
    initial_digests = {repository_content_digest(source), repository_content_digest(wrong)}
    diagnostic = (RepositoryProbe((5, 2)),)
    challenges = _challenges()
    final = _final_inputs()

    baseline_oracle, baseline_counter = _counted_oracle(external_callable)
    baseline = solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, baseline_oracle,
        refinement_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,), expansion_macros=(),
        max_selection_oracle_calls=1,
        max_refinement_oracle_calls=len(challenges),
        max_expansion_rounds=1,
        max_composition_depth=1,
        max_generated_candidates_per_round=64,
        max_sites_per_macro=16,
    )

    learner_oracle, learner_counter = _counted_oracle(external_callable)
    learner = solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, learner_oracle,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,), grammar=_grammar(),
        max_selection_oracle_calls=1,
        max_challenge_oracle_calls=len(challenges),
        max_generated_candidates=128,
        max_sites_per_hypothesis=16,
        min_independent_challenges=len(challenges),
    )

    learned = learner.learned_macro
    exact = bool(
        learner.status == 'accept'
        and learner.exact
        and learner.accepted_content_digest == target_digest
        and learned is not None
        and learned.source_value == 'Add'
        and learned.target_value == 'Mult'
    )
    verification_exact = len(final) if exact and learner.verification_failures == 0 else 0
    total_calls = int(baseline_counter['count']) + int(learner_counter['count'])

    return {
        'schema_version': 1,
        'milestone': 'R2.65',
        'capability': 'closed-grammar-repository-patch-primitive-induction',
        'claim_boundary': (
            'Pinned callable-I/O evidence that a missing Add->Mult repository PatchMacro can be derived from a '
            'finite authorized binop-replacement grammar using public diagnostic/challenge evidence, then verified '
            'on a disjoint heldout set. The exact target repository and exact PatchMacro are not supplied to the '
            'solver. This is not arbitrary code generation, open-ended patch-language invention, effectful '
            'experimentation, broad repository autonomy, or AGI.'
        ),
        'source_id': str(source_id),
        'source_version': str(source_version),
        'source_exposure': 'io_only',
        'source_implementation_inspected': False,
        'external_function_family': 'binary_multiply',
        'repository_file_count': len(source.files),
        'repository_call_depth': 3,
        'exact_patch_macro_supplied': False,
        'host_authored_exact_candidate': False,
        'exact_target_supplied_to_solver': False,
        'correct_target_absent_initial': target_digest not in initial_digests,
        'grammar_targets': list(_grammar().allowed_target_values),
        'diagnostic_args': list(diagnostic[0].args),
        'challenge_cases': len(challenges),
        'verification_cases': len(final),
        'verification_exact': verification_exact,
        'r264_baseline': {
            'status': baseline.status,
            'reason': baseline.reason,
            'oracle_calls': int(baseline_counter['count']),
            'selection_oracle_calls': baseline.selection_oracle_calls,
            'refinement_oracle_calls': baseline.refinement_oracle_calls,
            'final_verification_oracle_calls': baseline.final_verification_oracle_calls,
        },
        'r265': {
            'status': learner.status,
            'reason': learner.reason,
            'exact': exact,
            'primitive_promoted': learner.primitive_promoted,
            'learned_macro_id': learned.macro_id if learned is not None else None,
            'learned_source_value': learned.source_value if learned is not None else None,
            'learned_target_value': learned.target_value if learned is not None else None,
            'hypotheses_enumerated': learner.hypotheses_enumerated,
            'generated_candidates': learner.generated_candidates,
            'candidates_after_diagnostic': learner.candidates_after_diagnostic,
            'independent_challenges_passed': learner.independent_challenges_passed,
            'diagnostic_oracle_calls': learner.diagnostic_oracle_calls,
            'challenge_oracle_calls': learner.challenge_oracle_calls,
            'final_verification_oracle_calls': learner.final_verification_oracle_calls,
            'oracle_calls': int(learner_counter['count']),
            'accepted_content_digest': learner.accepted_content_digest,
            'generation_used_target_outputs': learner.generation_used_target_outputs,
            'false_terminal_accepts': learner.false_terminal_accepts,
            'verification_failures': learner.verification_failures,
        },
        'total_external_oracle_calls': total_calls,
        'target_digest': target_digest,
        'accepted_digest': learner.accepted_content_digest,
        'passed': bool(
            target_digest not in initial_digests
            and baseline.status == 'abstain'
            and baseline.reason == 'no_expansion_macros'
            and exact
            and learner.primitive_promoted
            and learner.independent_challenges_passed == len(challenges)
            and learner.generation_used_target_outputs is False
            and learner.false_terminal_accepts == 0
            and learner.verification_failures == 0
            and verification_exact == len(final)
        ),
        'trainable_parameter_count': 0,
    }


__all__ = ['run_external_transfer']
