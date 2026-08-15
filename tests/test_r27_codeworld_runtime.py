from cogcoder.r27_codeworld_runtime import (
    ActionProposal,
    CodingLoopState,
    choose_safe_action,
    legal_action_kinds,
)


def test_finish_is_illegal_until_full_verification_passes():
    state = CodingLoopState(
        repo_mapped=True,
        failure_reproduced=True,
        target_located=True,
        patch_applied=True,
        targeted_tests_pass=True,
        full_tests_pass=False,
        diff_reviewed=True,
        regression_risk=0.2,
        budget_remaining=4,
    )
    assert "finish" not in legal_action_kinds(state)
    assert "run_full_tests" in legal_action_kinds(state)


def test_safe_policy_blocks_finish_and_selects_best_legal_action():
    state = CodingLoopState(
        repo_mapped=True,
        failure_reproduced=True,
        target_located=True,
        patch_applied=True,
        targeted_tests_pass=True,
        full_tests_pass=False,
        diff_reviewed=True,
        regression_risk=0.1,
        budget_remaining=3,
    )
    proposals = [
        ActionProposal("finish", 10.0),
        ActionProposal("run_full_tests", 7.0),
        ActionProposal("inspect_diff", 6.0),
    ]
    chosen = choose_safe_action(state, proposals)
    assert chosen.kind == "run_full_tests"


def test_revert_is_forced_after_regression_when_budget_is_tight():
    state = CodingLoopState(
        repo_mapped=True,
        failure_reproduced=True,
        target_located=True,
        patch_applied=True,
        targeted_tests_pass=False,
        full_tests_pass=False,
        diff_reviewed=False,
        regression_detected=True,
        regression_risk=0.95,
        budget_remaining=1,
    )
    proposals = [
        ActionProposal("edit_small", 8.0),
        ActionProposal("revert", 2.0),
    ]
    assert choose_safe_action(state, proposals).kind == "revert"
