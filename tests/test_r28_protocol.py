from dataclasses import fields

from benchmarks.codeworld.r28_epistemic_cases import build_cases, evaluate_cases, renamed_case
from cogcoder.r27_codeworld_runtime import CodingLoopState


def _state_signature(state: CodingLoopState) -> tuple[object, ...]:
    return tuple(getattr(state, field.name) for field in fields(CodingLoopState))


def test_protocol_contains_same_state_counterexamples_with_different_correct_actions() -> None:
    cases = build_cases()
    assert len(cases) >= 4
    by_state: dict[tuple[object, ...], set[str]] = {}
    for case in cases:
        by_state.setdefault(_state_signature(case.state), set()).add(case.expected_kind)
    assert any(len(actions) >= 2 for actions in by_state.values())


def test_routing_cases_pass_exact_action_and_node_renaming_invariance() -> None:
    result = evaluate_cases(build_cases())
    assert result['exact_action_accuracy'] == 1.0
    assert result['rename_invariance'] == 1.0
    for case in build_cases():
        renamed = renamed_case(case)
        assert renamed.expected_kind == case.expected_kind


def test_r28_protocol_does_not_consume_language_or_task_ids() -> None:
    import inspect
    import cogcoder.r28_codeworld_runtime as runtime
    import cogcoder.r28_epistemic_debugger as debugger

    source = inspect.getsource(runtime) + inspect.getsource(debugger)
    assert 'language_id' not in source
    assert 'task_type_id' not in source


def test_phase_a_lock_freezes_zero_parameter_growth_and_external_claim_boundary() -> None:
    import json
    from pathlib import Path

    lock = json.loads(Path('research/R2_8_PRE_DEV_LOCK.json').read_text(encoding='utf-8'))
    assert lock['parent_effective_parameters'] == 79_401_400
    assert lock['new_r28_neural_parameters'] == 0
    assert lock['candidate_effective_parameters'] == 79_401_400
    assert lock['acceptance']['minimum_exact_action_accuracy'] == 1.0
    assert lock['acceptance']['minimum_rename_invariance'] == 1.0
    assert lock['acceptance']['external_coding_claim_allowed'] is False
