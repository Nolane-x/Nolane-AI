from __future__ import annotations

from collections.abc import Callable

from cogcoder.r247_executable_patch_cegis import PatchMacro
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_expansion_proof import repository_content_digest
from cogcoder.r261_version_space_expansion import (
    expand_repository_candidates,
    solve_repository_patch_with_version_space_expansion,
)
from cogcoder.r263_compositional_version_space_expansion import solve_repository_patch_with_compositional_expansion


def _candidate(candidate_id: str, files: dict[str, str], *, edits: int = 0) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id, (), tuple(sorted(files.items())), 0, edits)


def _files(*, pos_expr: str, neg_expr: str) -> dict[str, str]:
    return {
        'pos_leaf.py': f'def pos_leaf(x):\n    return {pos_expr}\n',
        'neg_leaf.py': f'def neg_leaf(x):\n    return {neg_expr}\n',
        'pos_relay.py': 'from pos_leaf import pos_leaf\n\ndef pos_relay(x):\n    return pos_leaf(x)\n',
        'neg_relay.py': 'from neg_leaf import neg_leaf\n\ndef neg_relay(x):\n    return neg_leaf(x)\n',
        'entry.py': (
            'from neg_relay import neg_relay\n'
            'from pos_relay import pos_relay\n\n'
            'def solve(x):\n'
            '    if x >= 0:\n'
            '        return pos_relay(x)\n'
            '    return neg_relay(x)\n'
        ),
    }


def _macro() -> PatchMacro:
    return PatchMacro('pm:r263:add-to-mult', 'binop', 'replace', 'Add', 'Mult', support=4)


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
    return tuple(RepositoryProbe((value,)) for value in range(-24, 25) if value not in {0, -5, 5})


def run_external_transfer(external_callable: Callable[[int], object], *, source_id: str, source_version: str) -> dict[str, object]:
    if not callable(external_callable): raise TypeError('external_callable must be callable')
    if not source_id or not source_version: raise ValueError('source_id and source_version must be non-empty')
    source = _candidate('r263:external:source', _files(pos_expr='x + x', neg_expr='x + x'))
    wrong = _candidate('r263:external:wrong', _files(pos_expr='x - 1', neg_expr='x + x'), edits=1)
    target = _candidate('r263:external:target-evaluation-only', _files(pos_expr='x * x', neg_expr='x * x'), edits=2)
    target_digest = repository_content_digest(target)
    initial_digests = {repository_content_digest(source), repository_content_digest(wrong)}
    one_step = expand_repository_candidates((source,), (_macro(),), max_generated_candidates=16, max_sites_per_macro=16)
    one_step_digests = {repository_content_digest(row.candidate) for row in one_step}
    diagnostic = (RepositoryProbe((5,)),)
    refinement = (RepositoryProbe((-5,)),)
    verification = _verification_inputs()

    r261_oracle, r261_counter = _counted_oracle(external_callable)
    r261 = solve_repository_patch_with_version_space_expansion(
        (source, wrong), (), diagnostic, r261_oracle,
        verification_inputs=refinement + verification,
        expansion_seeds=(source,), expansion_macros=(_macro(),),
        max_selection_oracle_calls=1, max_expansion_rounds=1,
        max_generated_candidates_per_round=16, max_sites_per_macro=16,
    )
    r263_oracle, r263_counter = _counted_oracle(external_callable)
    r263 = solve_repository_patch_with_compositional_expansion(
        (source, wrong), (), diagnostic, r263_oracle,
        refinement_inputs=refinement, verification_inputs=verification,
        expansion_seeds=(source,), expansion_macros=(_macro(),),
        max_selection_oracle_calls=1, max_refinement_oracle_calls=1,
        max_expansion_rounds=2, max_composition_depth=2,
        max_generated_candidates_per_round=16, max_sites_per_macro=16,
    )
    accepted_digest = repository_content_digest(r263.candidate) if r263.candidate is not None else None
    exact = bool(r263.status == 'accept' and r263.exact and accepted_digest == target_digest)
    verification_exact = len(verification) if exact and r263.verification_failures == 0 else 0
    total_calls = int(r261_counter['count']) + int(r263_counter['count'])
    return {
        'schema_version': 1,
        'milestone': 'R2.63',
        'capability': 'bounded-compositional-repository-version-space-expansion',
        'claim_boundary': 'Pinned callable-I/O evidence that two independently necessary trusted Add->Mult repository edits can be composed via a public refinement counterexample while the accepted R2.61 baseline stops after a partial repair. The exact target repository is used only for content-addressed evaluation and is never supplied to either solver. This does not establish source inspection, arbitrary code generation, patch-language invention, effectful experimentation, broad repository autonomy, or AGI.',
        'source_id': source_id,
        'source_version': source_version,
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
        'diagnostic_args': list(diagnostic[0].args),
        'refinement_args': list(refinement[0].args),
        'verification_cases': len(verification),
        'verification_exact': verification_exact,
        'r261_baseline': {
            'status': r261.status, 'reason': r261.reason,
            'expansion_rounds': r261.expansion_round_count,
            'oracle_calls': int(r261_counter['count']),
            'selection_oracle_calls': r261.selection_oracle_calls,
            'verification_oracle_calls': r261.verification_oracle_calls,
        },
        'r263': {
            'status': r263.status, 'reason': r263.reason, 'exact': exact,
            'composition_depth': r263.max_composition_depth_reached,
            'expansion_rounds': r263.expansion_round_count,
            'generated_candidates': r263.generated_candidates,
            'admitted_generated_candidates': r263.admitted_generated_candidates,
            'selection_oracle_calls': r263.selection_oracle_calls,
            'refinement_oracle_calls': r263.refinement_oracle_calls,
            'verification_oracle_calls': r263.verification_oracle_calls,
            'oracle_calls': int(r263_counter['count']),
            'public_observation_count': r263.observed_test_count,
            'false_terminal_accepts': r263.false_terminal_accepts,
            'verification_failures': r263.verification_failures,
        },
        'total_external_oracle_calls': total_calls,
        'target_digest': target_digest,
        'accepted_digest': accepted_digest,
        'passed': bool(
            target_digest not in initial_digests and target_digest not in one_step_digests
            and r261.status == 'abstain' and r261.reason == 'independent_verification_failed'
            and exact and r263.expansion_round_count == 2 and r263.max_composition_depth_reached == 2
            and r263.false_terminal_accepts == 0 and r263.verification_failures == 0
            and verification_exact == len(verification)
        ),
        'trainable_parameter_count': 0,
    }


__all__ = ['run_external_transfer']
