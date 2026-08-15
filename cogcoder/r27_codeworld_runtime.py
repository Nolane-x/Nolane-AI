from __future__ import annotations

from dataclasses import dataclass

from .r27_codeworld_controller import ACTION_KINDS


@dataclass(frozen=True)
class CodingLoopState:
    repo_mapped: bool = False
    failure_reproduced: bool = False
    target_located: bool = False
    patch_applied: bool = False
    targeted_tests_pass: bool = False
    full_tests_pass: bool = False
    diff_reviewed: bool = False
    regression_detected: bool = False
    regression_risk: float = 0.0
    budget_remaining: int = 12


@dataclass(frozen=True)
class ActionProposal:
    kind: str
    score: float

    def __post_init__(self) -> None:
        if self.kind not in ACTION_KINDS:
            raise ValueError(f"unknown action kind: {self.kind}")


def legal_action_kinds(state: CodingLoopState) -> set[str]:
    legal: set[str] = {"inspect_tree", "query_docs"}
    if state.repo_mapped:
        legal.update({"search_code", "read_context", "reproduce_failure"})
    if state.target_located:
        legal.update({"edit_small", "edit_multi"})
    if state.patch_applied:
        legal.update({"run_targeted_tests", "inspect_diff", "revert"})
    if state.patch_applied and state.targeted_tests_pass:
        legal.add("run_full_tests")
    if (
        state.patch_applied
        and state.targeted_tests_pass
        and state.full_tests_pass
        and state.diff_reviewed
        and not state.regression_detected
    ):
        legal.add("finish")
    return legal


def choose_safe_action(
    state: CodingLoopState, proposals: list[ActionProposal] | tuple[ActionProposal, ...]
) -> ActionProposal:
    if not proposals:
        raise ValueError("at least one proposal is required")

    by_kind = {proposal.kind: proposal for proposal in proposals}
    if (
        state.patch_applied
        and state.regression_detected
        and state.regression_risk >= 0.8
        and state.budget_remaining <= 1
        and "revert" in by_kind
    ):
        return by_kind["revert"]

    legal = legal_action_kinds(state)
    candidates = [proposal for proposal in proposals if proposal.kind in legal]
    if not candidates:
        raise RuntimeError("controller proposed no legal coding action")
    return max(candidates, key=lambda proposal: (proposal.score, -ACTION_KINDS.index(proposal.kind)))
