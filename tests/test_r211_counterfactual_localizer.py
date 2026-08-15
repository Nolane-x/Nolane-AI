import torch

from cogcoder.r28_repo_world import RepoEdge, RepoNode, RepoWorldGraph
from cogcoder.r210_copy_edit_features import FailureProbe
from cogcoder.r210_copy_edit_model import CopyEditProposalNet
from cogcoder.r211_counterfactual_localizer import (
    SymbolSlice,
    CounterfactualLocalizer,
)


def _graph():
    g = RepoWorldGraph()
    for node, kind in [('test','test'),('service','symbol'),('a','symbol'),('b','symbol'),('off','symbol')]:
        g.add_node(RepoNode(node, kind))
    g.add_edge(RepoEdge('test','service','tests'))
    g.add_edge(RepoEdge('service','a','calls'))
    g.add_edge(RepoEdge('service','b','calls'))
    return g


def test_localizer_excludes_unreachable_symbols_and_uses_no_path_or_id_features():
    torch.manual_seed(210)
    model = CopyEditProposalNet()
    localizer = CounterfactualLocalizer(model)
    symbols = (
        SymbolSlice('a','random-one.js','function f(x,y) {\n  return x + y;\n}\n'),
        SymbolSlice('b','random-two.js','function g(x,y) {\n  return x - y;\n}\n'),
        SymbolSlice('off','issue-name.js','function h(x,y) {\n  return x - y;\n}\n'),
    )
    probes = (FailureProbe((3,2),1,5), FailureProbe((-1,4),-5,3))
    ranked = localizer.rank(symbols, graph=_graph(), failing_test_node='test', language='javascript', probes=probes)
    assert {item.node_id for item in ranked} == {'a','b'}
    assert all(item.path not in repr(item.features) for item in ranked)


def test_node_id_and_filename_permutation_preserves_content_ranking():
    torch.manual_seed(210)
    model = CopyEditProposalNet()
    localizer = CounterfactualLocalizer(model)
    probes = (FailureProbe((3,2),1,5), FailureProbe((-1,4),-5,3))
    symbols = (
        SymbolSlice('a','x.js','function f(x,y) {\n  return x + y;\n}\n'),
        SymbolSlice('b','y.js','function g(x,y) {\n  return x - y;\n}\n'),
    )
    first = localizer.rank(symbols, graph=_graph(), failing_test_node='test', language='javascript', probes=probes)

    g2 = RepoWorldGraph()
    for node, kind in [('T','test'),('S','symbol'),('Q','symbol'),('P','symbol')]:
        g2.add_node(RepoNode(node, kind))
    g2.add_edge(RepoEdge('T','S','tests'))
    g2.add_edge(RepoEdge('S','Q','calls'))
    g2.add_edge(RepoEdge('S','P','calls'))
    renamed = (
        SymbolSlice('Q','zzz.js','function f(alpha,beta) {\n  return alpha + beta;\n}\n'),
        SymbolSlice('P','aaa.js','function g(alpha,beta) {\n  return alpha - beta;\n}\n'),
    )
    second = localizer.rank(renamed, graph=g2, failing_test_node='T', language='javascript', probes=probes)
    assert [item.canonical_fingerprint for item in first] == [item.canonical_fingerprint for item in second]


def test_per_symbol_runtime_observations_are_routed_by_node_but_not_encoded_as_identity():
    torch.manual_seed(210)
    model = CopyEditProposalNet()
    localizer = CounterfactualLocalizer(model)
    symbols = (
        SymbolSlice('a','a.js','function f(x,y) {\n  return x + y;\n}\n'),
        SymbolSlice('b','b.js','function g(x,y) {\n  return x - y;\n}\n'),
    )
    global_probes = (FailureProbe((3,2),1,5), FailureProbe((-1,4),-5,3))
    per_node = {
        'a': (FailureProbe((3,2),5,5), FailureProbe((-1,4),3,3)),
        'b': global_probes,
    }
    ranked = localizer.rank(symbols, graph=_graph(), failing_test_node='test', language='javascript', probes=global_probes, probes_by_node=per_node)
    assert {item.node_id for item in ranked} == {'a','b'}


def test_spectrum_evidence_ranks_symbol_covered_only_by_failing_tests_above_peer():
    from cogcoder.r211_counterfactual_localizer import TestCoverageObservation
    torch.manual_seed(210)
    model = CopyEditProposalNet()
    localizer = CounterfactualLocalizer(model, edit_gain_weight=0.0, behavior_weight=0.0)
    symbols = (
        SymbolSlice('a','a.js','function f(x,y) {\n  return x + y;\n}\n'),
        SymbolSlice('b','b.js','function g(x,y) {\n  return x + y;\n}\n'),
    )
    probes = (FailureProbe((3,2),1,5), FailureProbe((-1,4),-5,3))
    coverage = (
        TestCoverageObservation('f1', frozenset({'a','b'}), False),
        TestCoverageObservation('f2', frozenset({'a'}), False),
        TestCoverageObservation('p1', frozenset({'b'}), True),
    )
    ranked = localizer.rank(symbols, graph=_graph(), failing_test_node='test', language='javascript', probes=probes, coverage=coverage)
    assert ranked[0].node_id == 'a'


def test_differential_peer_behavior_breaks_identical_spectrum_tie():
    from cogcoder.r211_counterfactual_localizer import TestCoverageObservation
    torch.manual_seed(210)
    model = CopyEditProposalNet()
    localizer = CounterfactualLocalizer(model, edit_gain_weight=0.0)
    symbols = (
        SymbolSlice('a','a.js','function f(x,y) {\n  return x - y;\n}\n'),
        SymbolSlice('b','b.js','function g(x,y) {\n  return x + y;\n}\n'),
        SymbolSlice('c','c.js','function h(x,y) {\n  return x + y;\n}\n'),
    )
    probes = (FailureProbe((3,2),1,5), FailureProbe((-1,4),-5,3))
    per_node = {
        'a': probes,
        'b': (FailureProbe((3,2),5,5), FailureProbe((-1,4),3,3)),
        'c': (FailureProbe((3,2),5,5), FailureProbe((-1,4),3,3)),
    }
    coverage = (
        TestCoverageObservation('f1', frozenset({'a','b'}), False),
        TestCoverageObservation('f2', frozenset({'a','b'}), False),
    )
    ranked = localizer.rank(symbols, graph=_graph(), failing_test_node='test', language='javascript', probes=probes, probes_by_node=per_node, coverage=coverage)
    assert ranked[0].node_id == 'a'
