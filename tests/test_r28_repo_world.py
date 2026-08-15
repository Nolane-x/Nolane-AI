from cogcoder.r28_repo_world import RepoEdge, RepoNode, RepoWorldGraph


def _world() -> RepoWorldGraph:
    graph = RepoWorldGraph()
    for node in (
        RepoNode('core', 'symbol', 'src/core.py'),
        RepoNode('service', 'symbol', 'src/service.py'),
        RepoNode('api', 'symbol', 'src/api.py'),
        RepoNode('test_api', 'test', 'tests/test_api.py'),
        RepoNode('docs', 'file', 'docs/readme.md'),
    ):
        graph.add_node(node)
    graph.add_edge(RepoEdge('service', 'core', 'depends_on'))
    graph.add_edge(RepoEdge('api', 'service', 'depends_on'))
    graph.add_edge(RepoEdge('test_api', 'api', 'tests'))
    return graph


def test_impact_closure_follows_reverse_dependencies_and_tests() -> None:
    graph = _world()
    impacted = graph.impact_closure({'core'})
    assert impacted == {'core', 'service', 'api', 'test_api'}
    assert 'docs' not in impacted


def test_edit_risk_is_normalized_by_repository_graph_size() -> None:
    graph = _world()
    assert graph.edit_risk({'core'}) == 4 / 5
    assert graph.edit_risk({'docs'}) == 1 / 5
