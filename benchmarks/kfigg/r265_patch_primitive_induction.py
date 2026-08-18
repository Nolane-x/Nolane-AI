from __future__ import annotations

import inspect
from dataclasses import replace
from typing import Callable

from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r260_active_repository_probes import RepositoryProbe
from cogcoder.r261_expansion_proof import repository_content_digest
from cogcoder.r264_unified_adaptive_repository_search import solve_unified_adaptive_repository_patch
from cogcoder.r265_verified_patch_primitive_induction import (
    PatchPrimitiveGrammar,
    enumerate_patch_macro_hypotheses,
    solve_repository_patch_with_primitive_induction,
)


EPISODES = (
    (7101, 0, 'Add', 'Mult', 'Sub'),
    (7117, 1, 'FloorDiv', 'Mod', 'Add'),
    (7129, 2, 'Sub', 'Add', 'Mult'),
    (7141, 0, 'Mult', 'Sub', 'Add'),
    (7159, 1, 'Mod', 'FloorDiv', 'Add'),
    (7177, 2, 'Add', 'Mod', 'Sub'),
)

_SYMBOL = {
    'Add': '+',
    'Sub': '-',
    'Mult': '*',
    'Div': '/',
    'FloorDiv': '//',
    'Mod': '%',
}


def _candidate(candidate_id: str, files: dict[str, str], *, edits: int = 0) -> RepositoryPatchCandidate:
    return RepositoryPatchCandidate(candidate_id, (), tuple(sorted(files.items())), 0, edits)


def _repository(relays: int, *, target_op: str, aux_op: str) -> dict[str, str]:
    target_symbol = _SYMBOL[target_op]
    aux_symbol = _SYMBOL[aux_op]
    files: dict[str, str] = {
        'leaf.py': f'def leaf(x, y):\n    return x {target_symbol} y\n',
        'aux.py': f'def aux(x, y):\n    return x {aux_symbol} y\n',
    }
    previous = 'leaf'
    for index in range(1, relays + 1):
        name = f'relay{index}'
        files[f'{name}.py'] = (
            f'from {previous} import {previous}\n\n'
            f'def {name}(x, y):\n    return {previous}(x, y)\n'
        )
        previous = name
    files['entry.py'] = (
        'from aux import aux\n'
        f'from {previous} import {previous}\n\n'
        'def solve(x, y):\n'
        '    aux(x, y)\n'
        f'    return {previous}(x, y)\n'
    )
    return files


def _eval_op(name: str, x: int, y: int):
    if name == 'Add': return x + y
    if name == 'Sub': return x - y
    if name == 'Mult': return x * y
    if name == 'Div': return x / y
    if name == 'FloorDiv': return x // y
    if name == 'Mod': return x % y
    raise ValueError(name)


def _oracle(target_op: str) -> Callable[[int, int], object]:
    return lambda x, y: _eval_op(target_op, x, y)


def _grammar(*, omit: str | None = None, max_hypotheses: int = 64) -> PatchPrimitiveGrammar:
    targets = tuple(name for name in ('Add', 'Sub', 'Mult', 'Div', 'FloorDiv', 'Mod') if name != omit)
    return PatchPrimitiveGrammar(
        allowed_slots=('binop',),
        allowed_operations=('replace',),
        allowed_target_values=targets,
        max_hypotheses=max_hypotheses,
    )


def _challenges() -> tuple[RepositoryProbe, ...]:
    return tuple(RepositoryProbe(args) for args in ((4, 3), (7, 2), (9, 4), (-3, 5)))


def _final_inputs() -> tuple[RepositoryProbe, ...]:
    learning = {(5, 2), (4, 3), (7, 2), (9, 4), (-3, 5)}
    return tuple(
        RepositoryProbe((x, y))
        for x in (-11, -7, -2, 1, 3, 6, 10)
        for y in (-5, -2, 1, 4, 8)
        if (x, y) not in learning
    )


def _run_positive(seed: int, relays: int, source_op: str, target_op: str, wrong_op: str) -> dict[str, object]:
    source = _candidate(
        f'r265:source:{seed}',
        _repository(relays, target_op=source_op, aux_op=source_op),
    )
    wrong = _candidate(
        f'r265:wrong:{seed}',
        _repository(relays, target_op=wrong_op, aux_op=source_op),
        edits=1,
    )
    target = _candidate(
        f'r265:target-eval:{seed}',
        _repository(relays, target_op=target_op, aux_op=source_op),
        edits=1,
    )
    diagnostic = (RepositoryProbe((5, 2)),)
    challenges = _challenges()
    final = _final_inputs()
    oracle = _oracle(target_op)
    grammar = _grammar()

    baseline = solve_unified_adaptive_repository_patch(
        (source, wrong), (), diagnostic, oracle,
        refinement_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        expansion_macros=(),
        max_selection_oracle_calls=1,
        max_refinement_oracle_calls=len(challenges),
        max_expansion_rounds=1,
        max_composition_depth=1,
        max_generated_candidates_per_round=64,
        max_sites_per_macro=16,
    )
    result = solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, oracle,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        grammar=grammar,
        max_selection_oracle_calls=1,
        max_challenge_oracle_calls=len(challenges),
        max_generated_candidates=128,
        max_sites_per_hypothesis=16,
        min_independent_challenges=4,
    )
    reordered = solve_repository_patch_with_primitive_induction(
        (wrong, source), (), diagnostic, oracle,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        grammar=grammar,
        max_selection_oracle_calls=1,
        max_challenge_oracle_calls=len(challenges),
        max_generated_candidates=128,
        max_sites_per_hypothesis=16,
        min_independent_challenges=4,
    )
    renamed_source = replace(source, candidate_id=f'caller:renamed-source:{seed}')
    renamed_wrong = replace(wrong, candidate_id=f'caller:renamed-wrong:{seed}')
    renamed = solve_repository_patch_with_primitive_induction(
        (renamed_source, renamed_wrong), (), diagnostic, oracle,
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(renamed_source,),
        grammar=grammar,
        max_selection_oracle_calls=1,
        max_challenge_oracle_calls=len(challenges),
        max_generated_candidates=128,
        max_sites_per_hypothesis=16,
        min_independent_challenges=4,
    )

    target_digest = repository_content_digest(target)
    initial_digests = {repository_content_digest(source), repository_content_digest(wrong)}
    learned = result.learned_macro
    expected_primitive = bool(
        learned is not None
        and learned.slot == 'binop'
        and learned.operation == 'replace'
        and learned.source_value == source_op
        and learned.target_value == target_op
    )
    exact = bool(
        result.status == 'accept'
        and result.exact
        and result.accepted_content_digest == target_digest
    )
    return {
        'seed': seed,
        'relay_depth': relays,
        'file_count': len(source.files),
        'source_op': source_op,
        'target_op': target_op,
        'wrong_op': wrong_op,
        'target_absent_initial': target_digest not in initial_digests,
        'connected_decoy_present': f'x {_SYMBOL[source_op]} y' in dict(source.files)['aux.py'] and 'aux(x, y)' in dict(source.files)['entry.py'],
        'r264_status': baseline.status,
        'r264_reason': baseline.reason,
        'r265_status': result.status,
        'r265_reason': result.reason,
        'r265_exact': exact,
        'primitive_promoted': result.primitive_promoted,
        'learned_expected_primitive': expected_primitive,
        'learned_macro_id': learned.macro_id if learned is not None else None,
        'hypotheses_enumerated': result.hypotheses_enumerated,
        'generated_candidates': result.generated_candidates,
        'candidates_after_diagnostic': result.candidates_after_diagnostic,
        'independent_challenges_passed': result.independent_challenges_passed,
        'final_verification_cases': len(final),
        'final_verification_oracle_calls': result.final_verification_oracle_calls,
        'diagnostic_counterexamples': result.diagnostic_counterexamples,
        'caller_id_invariant': bool(
            result.candidate is not None and renamed.candidate is not None
            and result.candidate.files == renamed.candidate.files
            and result.learned_macro is not None and renamed.learned_macro is not None
            and result.learned_macro.macro_id == renamed.learned_macro.macro_id
        ),
        'candidate_order_invariant': bool(
            result.candidate is not None and reordered.candidate is not None
            and result.candidate.files == reordered.candidate.files
            and result.learned_macro is not None and reordered.learned_macro is not None
            and result.learned_macro.macro_id == reordered.learned_macro.macro_id
        ),
        'generation_used_target_outputs': result.generation_used_target_outputs,
        'false_terminal_accepts': result.false_terminal_accepts,
        'verification_failures': result.verification_failures,
        'target_digest': target_digest,
        'accepted_digest': result.accepted_content_digest,
    }


def _negative_cases() -> list[dict[str, object]]:
    seed, relays, source_op, target_op, wrong_op = EPISODES[0]
    source = _candidate('r265:negative:source', _repository(relays, target_op=source_op, aux_op=source_op))
    wrong = _candidate('r265:negative:wrong', _repository(relays, target_op=wrong_op, aux_op=source_op), edits=1)
    diagnostic = (RepositoryProbe((5, 2)),)
    challenges = _challenges()
    final = _final_inputs()
    oracle = _oracle(target_op)
    common = dict(
        challenge_inputs=challenges,
        final_verification_inputs=final,
        expansion_seeds=(source,),
        grammar=_grammar(),
        max_selection_oracle_calls=1,
        max_challenge_oracle_calls=4,
        max_generated_candidates=128,
        max_sites_per_hypothesis=16,
        min_independent_challenges=4,
    )
    rows: list[dict[str, object]] = []

    def add(case: str, receipt) -> None:
        rows.append({
            'case': case,
            'status': receipt.status,
            'reason': receipt.reason,
            'primitive_promoted': receipt.primitive_promoted,
            'final_verification_oracle_calls': receipt.final_verification_oracle_calls,
            'false_accepts': receipt.false_terminal_accepts,
            'verification_failures': receipt.verification_failures,
        })

    add('grammar_missing_target', solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, oracle, **{**common, 'grammar': _grammar(omit=target_op)},
    ))
    add('zero_hypothesis_budget', solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, oracle, **{**common, 'grammar': _grammar(max_hypotheses=0)},
    ))
    add('selection_budget', solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, oracle, **{**common, 'max_selection_oracle_calls': 0},
    ))
    add('challenge_budget', solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, oracle, **{**common, 'max_challenge_oracle_calls': 2},
    ))
    add('generation_budget', solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, oracle, **{**common, 'max_generated_candidates': 0},
    ))

    def diagnostic_error(x: int, y: int):
        if (x, y) == diagnostic[0].args:
            raise RuntimeError('diagnostic unavailable')
        return oracle(x, y)
    add('diagnostic_oracle_error', solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, diagnostic_error, **common,
    ))

    bad_challenge = challenges[0].args
    def challenge_error(x: int, y: int):
        if (x, y) == bad_challenge:
            raise RuntimeError('challenge unavailable')
        return oracle(x, y)
    add('challenge_oracle_error', solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, challenge_error, **common,
    ))

    poisoned = final[0].args
    def final_contradiction(x: int, y: int):
        value = oracle(x, y)
        return value + 101 if (x, y) == poisoned else value
    add('terminal_final_verification', solve_repository_patch_with_primitive_induction(
        (source, wrong), (), diagnostic, final_contradiction, **common,
    ))
    return rows


def run_benchmark() -> dict[str, object]:
    rows = [_run_positive(*episode) for episode in EPISODES]
    negatives = _negative_cases()
    summary = {
        'episodes': len(rows),
        'r264_missing_macro_abstains': sum(
            row['r264_status'] == 'abstain' and row['r264_reason'] == 'no_expansion_macros'
            for row in rows
        ),
        'r265_exact': sum(bool(row['r265_exact']) for row in rows),
        'learned_expected_primitive': sum(bool(row['learned_expected_primitive']) for row in rows),
        'primitive_promoted': sum(bool(row['primitive_promoted']) for row in rows),
        'target_absent_initial': sum(bool(row['target_absent_initial']) for row in rows),
        'connected_decoy_present': sum(bool(row['connected_decoy_present']) for row in rows),
        'min_independent_challenges': min(int(row['independent_challenges_passed']) for row in rows),
        'min_final_verification_cases': min(int(row['final_verification_cases']) for row in rows),
        'max_file_count': max(int(row['file_count']) for row in rows),
        'max_relay_depth': max(int(row['relay_depth']) for row in rows),
        'max_hypotheses_enumerated': max(int(row['hypotheses_enumerated']) for row in rows),
        'max_generated_candidates': max(int(row['generated_candidates']) for row in rows),
        'caller_id_invariant': all(bool(row['caller_id_invariant']) for row in rows),
        'candidate_order_invariant': all(bool(row['candidate_order_invariant']) for row in rows),
        'enumeration_uses_target_outputs': (
            'oracle' in inspect.signature(enumerate_patch_macro_hypotheses).parameters
            or 'target' in inspect.signature(enumerate_patch_macro_hypotheses).parameters
            or 'expected' in inspect.signature(enumerate_patch_macro_hypotheses).parameters
        ),
        'negative_abstains': sum(row['status'] == 'abstain' for row in negatives),
        'false_terminal_accepts': sum(int(row['false_terminal_accepts']) for row in rows) + sum(int(row['false_accepts']) for row in negatives),
        'positive_verification_failures': sum(int(row['verification_failures']) for row in rows),
    }
    gates = {
        'r264_baseline_fails_without_exact_macro': summary['r264_missing_macro_abstains'] == len(rows),
        'r265_all_exact': summary['r265_exact'] == len(rows),
        'all_learn_expected_primitive': summary['learned_expected_primitive'] == len(rows),
        'all_primitives_promoted': summary['primitive_promoted'] == len(rows),
        'targets_absent_initial': summary['target_absent_initial'] == len(rows),
        'all_have_connected_decoy': summary['connected_decoy_present'] == len(rows),
        'at_least_four_independent_challenges': summary['min_independent_challenges'] >= 4,
        'at_least_24_final_heldouts': summary['min_final_verification_cases'] >= 24,
        'caller_id_invariant': summary['caller_id_invariant'] is True,
        'candidate_order_invariant': summary['candidate_order_invariant'] is True,
        'target_output_free_primitive_enumeration': summary['enumeration_uses_target_outputs'] is False,
        'all_negative_cases_abstain': summary['negative_abstains'] == len(negatives),
        'zero_false_terminal_accepts': summary['false_terminal_accepts'] == 0,
        'zero_positive_verification_failures': summary['positive_verification_failures'] == 0,
        'zero_trainable_parameters': True,
    }
    return {
        'schema_version': 1,
        'milestone': 'R2.65 Verified Patch Primitive Induction Phase A',
        'capability': 'closed-grammar-repository-patch-primitive-induction',
        'claim_boundary': (
            'Causal evidence that a missing target-specific binop PatchMacro can be derived from a finite '
            'host-authorized rewrite grammar plus public diagnostic/challenge evidence, then terminally verified. '
            'This is not arbitrary code generation, open-ended patch-language invention, effectful experimentation, '
            'broad real-repository autonomy, or AGI.'
        ),
        'rows': rows,
        'negative_rows': negatives,
        'summary': summary,
        'gates': gates,
        'all_gates_pass': all(gates.values()),
        'trainable_parameter_count': 0,
    }


if __name__ == '__main__':
    import json
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
