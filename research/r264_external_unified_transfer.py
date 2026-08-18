from __future__ import annotations

from collections.abc import Callable

from cogcoder.r247_executable_patch_cegis import PatchMacro
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_expansion_proof import repository_content_digest
from cogcoder.r261_version_space_expansion import expand_repository_candidates
from cogcoder.r263_compositional_repository_repair import solve_compositional_repository_patch
from cogcoder.r264_unified_adaptive_repository_search import solve_unified_adaptive_repository_patch


def _candidate(candidate_id: str, files: dict[str, str], *, edits: int = 0) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id, (), tuple(sorted(files.items())), 0, edits)


def _files(*, pos_expr: str, neg_expr: str, aux_expr: str = 'x + x') -> dict[str, str]:
    return {
        'pos_leaf.py': f'def pos_leaf(x):\n    return {pos_expr}\n',
        'neg_leaf.py': f'def neg_leaf(x):\n    return {neg_expr}\n',
        'aux.py': f'def aux(x):\n    return {aux_expr}\n',
        'pos_relay.py': 'from pos_leaf import pos_leaf\n\ndef pos_relay(x):\n    return pos_leaf(x)\n',
        'entry.py': (
            'from aux import aux\n'
            'from neg_leaf import neg_leaf\n'
            'from pos_relay import pos_relay\n\n'
            'def solve(x):\n'
            '    aux(x)\n'
            '    if x >= 0:\n'
            '        return pos_relay(x)\n'
            '    return neg_leaf(x)\n'
        ),
    }


def _macro() -> PatchMacro:
    return PatchMacro('pm:r264:add-to-mult', 'binop', 'replace', 'Add', 'Mult', support=5)


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


def _counted_oracle(target: Callable[[int], object]):
    calls = {'count': 0}
    def wrapped(x: int) -> object:
        calls['count'] += 1
        return _normalize_scalar(target(x))
    return wrapped, calls


def _verification_inputs() -> tuple[RepositoryProbe, ...]:
    return tuple(
        RepositoryProbe((value,))
        for value in range(-24, 25)
        if value not in {-5, 0, 5}
    )


def run_external_transfer(
    external_callable: Callable[[int], object],
    *,
    source_id: str,
    source_version: str,
) -> dict[str, object]:
    if not callable(external_callable):
        raise TypeError('external_callable must be callable')
    if not source_id or not source_version:
        raise ValueError('source_id and source_version must be non-empty')

    source = _candidate(
        'r264:external:source',
        _files(pos_expr='x + x', neg_expr='x + x'),
    )
    wrong = _candidate(
        'r264:external:wrong-positive',
        _files(pos_expr='x - 1', neg_expr='x + x'),
        edits=1,
    )
    target = _candidate(
        'r264:external:target-evaluation-only',
        _files(pos_expr='x * x', neg_expr='x * x'),
        edits=2,
    )
    target_digest = repository_content_digest(target)
    initial_digests = {repository_content_digest(source), repository_content_digest(wrong)}
    one_step = expand_repository_candidates(
        (source,), (_macro(),), max_generated_candidates=16, max_sites_per_macro=16,
    )
    one_step_digests = {repository_content_digest(row.candidate) for row in one_step}

    diagnostic = (RepositoryProbe((5,)),)
    refinement = (RepositoryProbe((-5,)),)
    final = _verification_inputs()

    r263_oracle, r263_counter = _counted_oracle(external_callable)
    r263 = solve_compositional_repository_patch(
        (source, wrong), (), diagnostic, refinement, r263_oracle,
        final_verification_inputs=final,
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_refinement_oracle_calls=1,
        max_expansion_rounds=2,
        max_generated_candidates_per_round=16,
        max_sites_per_macro=16,
    )

    r264_oracle, r264_counter = _counted_oracle(external_callable)
    r264 = solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, r264_oracle,
        refinement_inputs=refinement,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        expansion_macros=(_macro(),),
        max_selection_oracle_calls=1,
        max_refinement_oracle_calls=1,
        max_expansion_rounds=2,
        max_composition_depth=2,
        max_generated_candidates_per_round=16,
        max_sites_per_macro=16,
    )

    accepted_digest = r264.accepted_content_digest
    exact = bool(
        r264.status == 'accept'
        and r264.exact
        and accepted_digest == target_digest
    )
    verification_exact = len(final) if exact and r264.verification_failures == 0 else 0
    total_calls = int(r263_counter['count']) + int(r264_counter['count'])

    return {
        'schema_version': 1,
        'milestone': 'R2.64',
        'capability': 'unified-diagnostic-out-of-space-and-compositional-refinement-search',
        'claim_boundary': (
            'Pinned callable-I/O evidence that R2.64 can escape an initial multi-candidate version-space boundary '
            'using a diagnostic counterexample and then compose a second trusted Add->Mult repository edit from a '
            'separate refinement counterexample. The exact target repository is evaluation-only and never supplied '
            'to either solver. The repository wrapper, probe pools and patch vocabulary remain host-authored. This '
            'does not establish source inspection, arbitrary code generation, patch-language invention, effectful '
            'experimentation, broad repository autonomy, or AGI.'
        ),
        'source_id': str(source_id),
        'source_version': str(source_version),
        'source_exposure': 'io_only',
        'source_implementation_inspected': False,
        'external_function_family': 'square',
        'repository_file_count': len(source.files),
        'repository_call_depth': 3,
        'correct_target_absent_initial': target_digest not in initial_digests,
        'correct_target_absent_complete_one_step_space': target_digest not in one_step_digests,
        'complete_one_step_candidates': len(one_step),
        'host_authored_exact_candidate': False,
        'exact_target_supplied_to_solver': False,
        'trusted_patch_macro': ['binop', 'replace', 'Add', 'Mult'],
        'diagnostic_args': list(diagnostic[0].args),
        'refinement_args': list(refinement[0].args),
        'verification_cases': len(final),
        'verification_exact': verification_exact,
        'r263_baseline': {
            'status': r263.status,
            'reason': r263.reason,
            'expansion_rounds': r263.expansion_round_count,
            'oracle_calls': int(r263_counter['count']),
            'selection_oracle_calls': r263.selection_oracle_calls,
            'refinement_oracle_calls': r263.refinement_oracle_calls,
            'final_verification_oracle_calls': r263.final_verification_oracle_calls,
        },
        'r264': {
            'status': r264.status,
            'reason': r264.reason,
            'exact': exact,
            'diagnostic_counterexamples': r264.diagnostic_counterexamples,
            'refinement_counterexamples': r264.refinement_counterexamples,
            'composition_depth': r264.max_composition_depth_reached,
            'expansion_rounds': r264.expansion_round_count,
            'generated_candidates': r264.generated_candidates,
            'admitted_generated_candidates': r264.admitted_generated_candidates,
            'accepted_edit_count': r264.accepted_edit_count,
            'accepted_mutation_chain': list(r264.accepted_mutation_chain),
            'accepted_content_digest': accepted_digest,
            'generation_used_target_outputs': r264.generation_used_target_outputs,
            'selection_oracle_calls': r264.selection_oracle_calls,
            'refinement_oracle_calls': r264.refinement_oracle_calls,
            'final_verification_oracle_calls': r264.final_verification_oracle_calls,
            'oracle_calls': int(r264_counter['count']),
            'false_terminal_accepts': r264.false_terminal_accepts,
            'verification_failures': r264.verification_failures,
        },
        'total_external_oracle_calls': total_calls,
        'target_digest': target_digest,
        'accepted_digest': accepted_digest,
        'passed': bool(
            target_digest not in initial_digests
            and target_digest not in one_step_digests
            and r263.status == 'abstain'
            and r263.reason == 'oracle_outside_initial_candidate_version_space'
            and r263.expansion_round_count == 0
            and exact
            and r264.diagnostic_counterexamples == 1
            and r264.refinement_counterexamples == 1
            and r264.expansion_round_count == 2
            and r264.max_composition_depth_reached == 2
            and r264.accepted_edit_count == 2
            and len(r264.accepted_mutation_chain) == 2
            and len(set(r264.accepted_mutation_chain)) == 2
            and r264.generation_used_target_outputs is False
            and r264.false_terminal_accepts == 0
            and r264.verification_failures == 0
            and verification_exact == len(final)
        ),
        'trainable_parameter_count': 0,
    }


__all__ = ['run_external_transfer']
