import copy

from cogcoder.r247_executable_patch_cegis import PatchTest
from cogcoder.r252_repository_query import RepositoryPatchCandidate
from cogcoder.r259_active_repository_probes import (
    RepositoryProbe,
    enumerate_probe_inputs,
    solve_repository_patch_with_active_probes,
)


def _candidate(candidate_id: str, expression: str) -> RepositoryPatchCandidate:
    source = f'def root(x, y):\n    return {expression}\n'
    return RepositoryPatchCandidate(candidate_id, (), (('main.py', source),), 0, 0)


def test_probe_ids_are_content_addressed_and_enumeration_is_order_independent():
    a = enumerate_probe_inputs(2, (-1, 0, 1))
    b = enumerate_probe_inputs(2, (1, -1, 0))
    assert {row.probe_id for row in a} == {row.probe_id for row in b}
    assert len(a) == 9
    assert RepositoryProbe((1, -1)).probe_id == RepositoryProbe((1, -1)).probe_id


def test_active_probe_chooses_maximally_discriminating_input_and_recovers_target():
    candidates = (
        _candidate('add', 'x + y'),
        _candidate('sub', 'x - y'),
        _candidate('mul', 'x * y'),
    )
    calls = {'count': 0}

    def oracle(x, y):
        calls['count'] += 1
        return x + y

    receipt = solve_repository_patch_with_active_probes(
        candidates,
        (PatchTest('initial-zero', (0, 0), 0),),
        enumerate_probe_inputs(2, (-1, 0, 1, 2)),
        oracle,
        verification_inputs=enumerate_probe_inputs(2, (-2, -1, 0, 1, 2)),
        max_selection_oracle_calls=2,
    )

    assert receipt.status == 'accept'
    assert receipt.exact is True
    assert receipt.candidate is not None and receipt.candidate.candidate_id == 'add'
    assert receipt.initial_survivors == 3
    assert receipt.selection_oracle_calls == 1
    assert receipt.rounds[0].partition_count == 3
    assert receipt.rounds[0].largest_partition == 1
    assert receipt.final_survivors == 1
    assert receipt.verification_oracle_calls == 25
    assert receipt.oracle_calls_total == calls['count'] == 26
    assert receipt.false_terminal_accepts == 0


def test_candidate_order_and_candidate_ids_do_not_change_selected_probe_or_behavior():
    left = (
        _candidate('a', 'x + y'),
        _candidate('b', 'x - y'),
        _candidate('c', 'x * y'),
    )
    renamed = (
        _candidate('zzz', 'x * y'),
        _candidate('qqq', 'x + y'),
        _candidate('mmm', 'x - y'),
    )

    def run(rows):
        return solve_repository_patch_with_active_probes(
            rows,
            (PatchTest('z', (0, 0), 0),),
            enumerate_probe_inputs(2, (-1, 0, 1, 2)),
            lambda x, y: x + y,
            verification_inputs=enumerate_probe_inputs(2, (-1, 0, 1)),
            max_selection_oracle_calls=2,
        )

    a = run(left); b = run(renamed)
    assert a.status == b.status == 'accept'
    assert a.rounds[0].probe.args == b.rounds[0].probe.args
    assert a.rounds[0].partition_signature == b.rounds[0].partition_signature
    assert a.selection_oracle_calls == b.selection_oracle_calls == 1


def test_indistinguishable_survivors_abstain_without_wasting_oracle_calls():
    candidates = (
        _candidate('one', 'x + y'),
        _candidate('two', 'y + x'),
    )
    calls = {'count': 0}

    def oracle(x, y):
        calls['count'] += 1
        return x + y

    receipt = solve_repository_patch_with_active_probes(
        candidates,
        (PatchTest('z', (0, 0), 0),),
        enumerate_probe_inputs(2, (-1, 0, 1)),
        oracle,
        verification_inputs=enumerate_probe_inputs(2, (-1, 0, 1)),
        max_selection_oracle_calls=3,
    )

    assert receipt.status == 'abstain'
    assert receipt.reason == 'no_informative_probe'
    assert receipt.selection_oracle_calls == 0
    assert receipt.verification_oracle_calls == 0
    assert calls['count'] == 0
    assert receipt.final_survivors == 2


def test_oracle_budget_exhaustion_abstains_before_terminal_accept():
    candidates = (
        _candidate('a', 'x + y'),
        _candidate('b', 'x - y'),
        _candidate('c', 'x * y'),
    )
    receipt = solve_repository_patch_with_active_probes(
        candidates,
        (PatchTest('z', (0, 0), 0),),
        enumerate_probe_inputs(2, (-1, 0, 1, 2)),
        lambda x, y: x + y,
        verification_inputs=enumerate_probe_inputs(2, (-1, 0, 1)),
        max_selection_oracle_calls=0,
    )
    assert receipt.status == 'abstain'
    assert receipt.reason == 'selection_oracle_budget_exhausted'
    assert receipt.false_terminal_accepts == 0
