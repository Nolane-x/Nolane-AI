from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .r27_codeworld_controller import ACTION_KINDS
from .r27_codeworld_runtime import ActionProposal, CodingLoopState, legal_action_kinds
from .r28_epistemic_debugger import ActiveDebugger, EpistemicProbe, HypothesisLedger
from .r28_repo_world import RepoWorldGraph


@dataclass(frozen=True, slots=True)
class EpistemicActionDecision:
    kind: str
    target_nodes: frozenset[str]
    utility: float
    information_gain: float
    controller_score: float


def choose_epistemic_action(
    state: CodingLoopState,
    proposals: Sequence[ActionProposal],
    graph: RepoWorldGraph,
    ledger: HypothesisLedger,
    probes: Sequence[EpistemicProbe],
    *,
    debugger: ActiveDebugger | None = None,
) -> EpistemicActionDecision:
    """Choose a legal coding action using R2.7 scores plus repository evidence.

    R2.7 legality remains authoritative. R2.8 only re-ranks legal actions using
    public evidence, expected information gain, graph coverage, cost and risk.
    """
    if not proposals:
        raise ValueError('at least one R2.7 proposal is required')
    if not probes:
        raise ValueError('at least one epistemic probe is required')
    debugger = debugger or ActiveDebugger()
    proposal_by_kind = {proposal.kind: proposal for proposal in proposals}

    if (
        state.patch_applied
        and state.regression_detected
        and state.regression_risk >= 0.8
        and state.budget_remaining <= 1
        and 'revert' in proposal_by_kind
    ):
        return EpistemicActionDecision(
            kind='revert',
            target_nodes=frozenset(),
            utility=float('inf'),
            information_gain=0.0,
            controller_score=float(proposal_by_kind['revert'].score),
        )

    legal = legal_action_kinds(state)
    candidates: list[tuple[EpistemicProbe, float, float, float]] = []
    for probe in probes:
        if probe.kind not in legal:
            continue
        proposal = proposal_by_kind.get(probe.kind)
        if proposal is None:
            continue
        combined = EpistemicProbe(
            kind=probe.kind,
            target_nodes=probe.target_nodes,
            likelihood_positive=probe.likelihood_positive,
            base_score=float(proposal.score) + float(probe.base_score),
            cost=probe.cost,
            risk=probe.risk,
        )
        information_gain = debugger.expected_information_gain(ledger, combined)
        utility = debugger.utility(graph, ledger, combined)
        candidates.append((combined, utility, information_gain, float(proposal.score)))

    if not candidates:
        raise RuntimeError('no legal R2.8 probe corresponds to an R2.7 controller proposal')

    candidates.sort(
        key=lambda item: (
            -item[1],
            ACTION_KINDS.index(item[0].kind),
            tuple(sorted(item[0].target_nodes)),
        )
    )
    probe, utility, information_gain, controller_score = candidates[0]
    return EpistemicActionDecision(
        kind=probe.kind,
        target_nodes=probe.target_nodes,
        utility=utility,
        information_gain=information_gain,
        controller_score=controller_score,
    )
