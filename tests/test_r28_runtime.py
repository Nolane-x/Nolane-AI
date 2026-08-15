from cogcoder.r27_codeworld_runtime import ActionProposal, CodingLoopState
from cogcoder.r28_codeworld_runtime import choose_epistemic_action
from cogcoder.r28_epistemic_debugger import DebugHypothesis, EpistemicProbe, HypothesisLedger
from cogcoder.r28_repo_world import RepoNode, RepoWorldGraph


def _graph() -> RepoWorldGraph:
    graph = RepoWorldGraph()
    graph.add_node(RepoNode('core', 'symbol', 'src/core'))
    graph.add_node(RepoNode('api', 'symbol', 'src/api'))
    return graph


def _proposals() -> list[ActionProposal]:
    return [
        ActionProposal('reproduce_failure', 0.20),
        ActionProposal('read_context', 0.20),
        ActionProposal('search_code', 0.20),
        ActionProposal('finish', 9.0),
    ]


def _probes() -> list[EpistemicProbe]:
    return [
        EpistemicProbe(
            kind='reproduce_failure',
            target_nodes=frozenset({'core', 'api'}),
            likelihood_positive={'h_core': 0.95, 'h_api': 0.05},
            cost=0.90,
        ),
        EpistemicProbe(
            kind='read_context',
            target_nodes=frozenset({'core'}),
            likelihood_positive={'h_core': 0.65, 'h_api': 0.35},
            cost=0.05,
        ),
        EpistemicProbe(
            kind='search_code',
            target_nodes=frozenset({'core', 'api'}),
            likelihood_positive={'h_core': 0.50, 'h_api': 0.50},
            cost=0.10,
        ),
        EpistemicProbe(
            kind='finish',
            target_nodes=frozenset(),
            likelihood_positive={'h_core': 0.50, 'h_api': 0.50},
        ),
    ]


def test_same_loop_state_and_neural_scores_choose_different_actions_from_evidence() -> None:
    state = CodingLoopState(repo_mapped=True, budget_remaining=8)
    diffuse = HypothesisLedger(
        [
            DebugHypothesis('h_core', frozenset({'core'}), 0.5),
            DebugHypothesis('h_api', frozenset({'api'}), 0.5),
        ]
    )
    concentrated = HypothesisLedger(
        [
            DebugHypothesis('h_core', frozenset({'core'}), 0.95),
            DebugHypothesis('h_api', frozenset({'api'}), 0.05),
        ]
    )

    diffuse_decision = choose_epistemic_action(state, _proposals(), _graph(), diffuse, _probes())
    concentrated_decision = choose_epistemic_action(state, _proposals(), _graph(), concentrated, _probes())

    assert diffuse_decision.kind == 'reproduce_failure'
    assert concentrated_decision.kind == 'read_context'


def test_r27_safety_legality_still_blocks_high_scoring_finish() -> None:
    state = CodingLoopState(repo_mapped=True)
    ledger = HypothesisLedger(
        [
            DebugHypothesis('h_core', frozenset({'core'}), 0.5),
            DebugHypothesis('h_api', frozenset({'api'}), 0.5),
        ]
    )
    decision = choose_epistemic_action(state, _proposals(), _graph(), ledger, _probes())
    assert decision.kind != 'finish'
