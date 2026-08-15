import math

from cogcoder.r28_epistemic_debugger import (
    ActiveDebugger,
    DebugHypothesis,
    EpistemicProbe,
    Evidence,
    HypothesisLedger,
)
from cogcoder.r28_repo_world import RepoNode, RepoWorldGraph


def _ledger() -> HypothesisLedger:
    return HypothesisLedger(
        [
            DebugHypothesis('h_core', frozenset({'core'}), 0.5),
            DebugHypothesis('h_api', frozenset({'api'}), 0.5),
        ]
    )


def test_public_evidence_updates_and_renormalizes_hypotheses() -> None:
    ledger = _ledger()
    ledger.update(
        Evidence(
            source='targeted-test',
            observed_positive=True,
            likelihood_positive={'h_core': 0.9, 'h_api': 0.1},
        )
    )
    assert math.isclose(ledger.probability('h_core'), 0.9, rel_tol=1e-9)
    assert math.isclose(ledger.probability('h_api'), 0.1, rel_tol=1e-9)
    assert math.isclose(sum(ledger.probabilities().values()), 1.0, rel_tol=1e-9)


def test_discriminative_probe_has_more_information_gain_than_uninformative_probe() -> None:
    ledger = _ledger()
    debugger = ActiveDebugger()
    discriminative = EpistemicProbe(
        kind='reproduce_failure',
        target_nodes=frozenset({'core', 'api'}),
        likelihood_positive={'h_core': 0.9, 'h_api': 0.1},
    )
    uninformative = EpistemicProbe(
        kind='search_code',
        target_nodes=frozenset({'core', 'api'}),
        likelihood_positive={'h_core': 0.5, 'h_api': 0.5},
    )
    assert debugger.expected_information_gain(ledger, discriminative) > 0.5
    assert math.isclose(debugger.expected_information_gain(ledger, uninformative), 0.0, abs_tol=1e-12)


def test_high_impact_edit_is_penalized_by_repository_world_risk() -> None:
    debugger = ActiveDebugger()
    graph = RepoWorldGraph()
    for node_id in ('core', 'service', 'api', 'test_api'):
        graph.add_node(RepoNode(node_id, 'symbol'))
    from cogcoder.r28_repo_world import RepoEdge
    graph.add_edge(RepoEdge('service', 'core', 'depends_on'))
    graph.add_edge(RepoEdge('api', 'service', 'depends_on'))
    graph.add_edge(RepoEdge('test_api', 'api', 'tests'))
    ledger = HypothesisLedger([DebugHypothesis('h', frozenset({'core'}), 1.0)])
    edit = EpistemicProbe(
        kind='edit_small',
        target_nodes=frozenset({'core'}),
        likelihood_positive={'h': 1.0},
        base_score=1.0,
    )
    read = EpistemicProbe(
        kind='read_context',
        target_nodes=frozenset({'core'}),
        likelihood_positive={'h': 1.0},
        base_score=1.0,
    )
    assert debugger.utility(graph, ledger, read) > debugger.utility(graph, ledger, edit)
