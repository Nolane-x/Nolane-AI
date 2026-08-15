from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

from cogcoder.r27_codeworld_runtime import ActionProposal, CodingLoopState
from cogcoder.r28_codeworld_runtime import choose_epistemic_action
from cogcoder.r28_epistemic_debugger import DebugHypothesis, EpistemicProbe, HypothesisLedger
from cogcoder.r28_repo_world import RepoEdge, RepoNode, RepoWorldGraph


@dataclass(frozen=True, slots=True)
class RoutingCase:
    name: str
    state: CodingLoopState
    nodes: tuple[RepoNode, ...]
    edges: tuple[RepoEdge, ...]
    hypotheses: tuple[DebugHypothesis, ...]
    proposals: tuple[ActionProposal, ...]
    probes: tuple[EpistemicProbe, ...]
    expected_kind: str

    def graph(self) -> RepoWorldGraph:
        graph = RepoWorldGraph()
        for node in self.nodes:
            graph.add_node(node)
        for edge in self.edges:
            graph.add_edge(edge)
        return graph

    def ledger(self) -> HypothesisLedger:
        return HypothesisLedger(self.hypotheses)


def _ambiguity_case(name: str, core_prior: float, expected_kind: str) -> RoutingCase:
    api_prior = 1.0 - core_prior
    nodes = (
        RepoNode('core', 'symbol', 'src/core'),
        RepoNode('api', 'symbol', 'src/api'),
    )
    hypotheses = (
        DebugHypothesis('h_core', frozenset({'core'}), core_prior),
        DebugHypothesis('h_api', frozenset({'api'}), api_prior),
    )
    proposals = (
        ActionProposal('reproduce_failure', 0.20),
        ActionProposal('read_context', 0.20),
        ActionProposal('search_code', 0.20),
    )
    probes = (
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
    )
    return RoutingCase(
        name=name,
        state=CodingLoopState(repo_mapped=True, budget_remaining=8),
        nodes=nodes,
        edges=(),
        hypotheses=hypotheses,
        proposals=proposals,
        probes=probes,
        expected_kind=expected_kind,
    )


def _topology_case(name: str, central: bool, expected_kind: str) -> RoutingCase:
    nodes = (
        RepoNode('target', 'symbol', 'src/target'),
        RepoNode('consumer', 'symbol', 'src/consumer'),
        RepoNode('api', 'symbol', 'src/api'),
        RepoNode('test_api', 'test', 'tests/test_api'),
    )
    edges = (
        (
            RepoEdge('consumer', 'target', 'depends_on'),
            RepoEdge('api', 'consumer', 'depends_on'),
            RepoEdge('test_api', 'api', 'tests'),
        )
        if central
        else ()
    )
    hypotheses = (DebugHypothesis('h_target', frozenset({'target'}), 1.0),)
    proposals = (
        ActionProposal('edit_small', 0.80),
        ActionProposal('read_context', 0.50),
    )
    probes = (
        EpistemicProbe(
            kind='edit_small',
            target_nodes=frozenset({'target'}),
            likelihood_positive={'h_target': 1.0},
        ),
        EpistemicProbe(
            kind='read_context',
            target_nodes=frozenset({'target'}),
            likelihood_positive={'h_target': 1.0},
        ),
    )
    return RoutingCase(
        name=name,
        state=CodingLoopState(
            repo_mapped=True,
            failure_reproduced=True,
            target_located=True,
            budget_remaining=6,
        ),
        nodes=nodes,
        edges=edges,
        hypotheses=hypotheses,
        proposals=proposals,
        probes=probes,
        expected_kind=expected_kind,
    )


def build_cases() -> tuple[RoutingCase, ...]:
    """Phase-A counterexamples deliberately break a fixed stage->action policy."""
    return (
        _ambiguity_case('diffuse-needs-reproduction', 0.50, 'reproduce_failure'),
        _ambiguity_case('concentrated-needs-context', 0.95, 'read_context'),
        _topology_case('isolated-target-allows-edit', False, 'edit_small'),
        _topology_case('central-target-needs-more-context', True, 'read_context'),
    )


def renamed_case(case: RoutingCase) -> RoutingCase:
    node_map = {node.node_id: f'n{index}' for index, node in enumerate(case.nodes)}
    hypothesis_map = {
        hypothesis.hypothesis_id: f'h{index}' for index, hypothesis in enumerate(case.hypotheses)
    }
    nodes = tuple(
        RepoNode(node_map[node.node_id], node.kind, path=f'renamed/{index}')
        for index, node in enumerate(case.nodes)
    )
    edges = tuple(
        RepoEdge(node_map[edge.source], node_map[edge.target], edge.kind, edge.weight)
        for edge in case.edges
    )
    hypotheses = tuple(
        DebugHypothesis(
            hypothesis_map[hypothesis.hypothesis_id],
            frozenset(node_map[node_id] for node_id in hypothesis.target_nodes),
            hypothesis.prior_probability,
        )
        for hypothesis in case.hypotheses
    )
    probes = tuple(
        EpistemicProbe(
            kind=probe.kind,
            target_nodes=frozenset(node_map[node_id] for node_id in probe.target_nodes),
            likelihood_positive={
                hypothesis_map[hypothesis_id]: likelihood
                for hypothesis_id, likelihood in probe.likelihood_positive.items()
            },
            base_score=probe.base_score,
            cost=probe.cost,
            risk=probe.risk,
        )
        for probe in case.probes
    )
    return replace(
        case,
        name=f'{case.name}-renamed',
        nodes=nodes,
        edges=edges,
        hypotheses=hypotheses,
        probes=probes,
    )


def _decision_kind(case: RoutingCase) -> str:
    return choose_epistemic_action(
        case.state,
        case.proposals,
        case.graph(),
        case.ledger(),
        case.probes,
    ).kind


def evaluate_cases(cases: Sequence[RoutingCase]) -> dict[str, object]:
    if not cases:
        raise ValueError('at least one R2.8 routing case is required')
    exact = 0
    invariant = 0
    rows: list[dict[str, object]] = []
    for case in cases:
        decision = _decision_kind(case)
        renamed = renamed_case(case)
        renamed_decision = _decision_kind(renamed)
        exact += int(decision == case.expected_kind)
        invariant += int(renamed_decision == decision == case.expected_kind)
        rows.append(
            {
                'case': case.name,
                'expected': case.expected_kind,
                'decision': decision,
                'renamed_decision': renamed_decision,
            }
        )
    count = len(cases)
    return {
        'cases': count,
        'exact_action_accuracy': exact / count,
        'rename_invariance': invariant / count,
        'rows': rows,
    }
