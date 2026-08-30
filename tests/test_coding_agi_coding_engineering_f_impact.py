from dataclasses import dataclass

import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.software_engineering_impact import (
    EngineeringDependencyGraphLedger,
    EngineeringImpactAnalyzer,
    EngineeringTestCoverageLedger,
    EngineeringTestSelectionEngine,
)


@dataclass(frozen=True)
class _Patch:
    patch_id: str = 'patch-impact-1'
    producer_agent_id: str = 'coding.backend.01'
    task_id: str = 'task-impact-1'
    touched_files: tuple[str, ...] = ('pkg/a.py',)
    touched_symbols: tuple[str, ...] = ('pkg.a:A.run',)

    def to_state(self):
        return {
            'patch_id': self.patch_id,
            'producer_agent_id': self.producer_agent_id,
            'task_id': self.task_id,
            'touched_files': list(self.touched_files),
            'touched_symbols': list(self.touched_symbols),
        }


def _graph():
    ledger = EngineeringDependencyGraphLedger()
    return ledger.register(
        source_revision='git:impact-a',
        nodes=(
            'file:pkg/a.py',
            'symbol:pkg.a:A.run',
            'symbol:pkg.b:B.call',
            'symbol:pkg.c:C.use',
        ),
        dependency_edges=(
            ('symbol:pkg.a:A.run', 'symbol:pkg.b:B.call'),
            ('symbol:pkg.b:B.call', 'symbol:pkg.c:C.use'),
        ),
        component_membership={
            'symbol:pkg.a:A.run': 'component:a',
            'symbol:pkg.b:B.call': 'component:b',
            'symbol:pkg.c:C.use': 'component:c',
        },
        provenance_refs=('static-analysis:graph-1',),
    )


def test_impact_is_transitive_and_derived_not_caller_declared():
    graph = _graph()
    receipt = EngineeringImpactAnalyzer().analyze(patch=_Patch(), graph=graph)
    assert receipt.impacted_nodes == (
        'symbol:pkg.a:A.run',
        'symbol:pkg.b:B.call',
        'symbol:pkg.c:C.use',
    )
    assert receipt.impacted_component_refs == ('component:a', 'component:b', 'component:c')
    assert receipt.graph_digest == graph.digest
    assert receipt.patch_digest == canonical_digest(_Patch().to_state())


def test_impact_rejects_patch_scope_missing_from_graph():
    graph = _graph()
    patch = _Patch(touched_symbols=('pkg.unknown:X.run',))
    with pytest.raises(ValueError, match='not represented'):
        EngineeringImpactAnalyzer().analyze(patch=patch, graph=graph)


def test_graph_rejects_cycles():
    ledger = EngineeringDependencyGraphLedger()
    with pytest.raises(ValueError, match='cycle'):
        ledger.register(
            source_revision='git:cycle',
            nodes=('symbol:a', 'symbol:b'),
            dependency_edges=(('symbol:a', 'symbol:b'), ('symbol:b', 'symbol:a')),
            component_membership={},
            provenance_refs=('static-analysis:cycle',),
        )


def test_differential_test_selection_must_cover_every_impacted_node():
    graph = _graph()
    impact = EngineeringImpactAnalyzer().analyze(patch=_Patch(), graph=graph)
    coverage = EngineeringTestCoverageLedger().register(
        source_revision='git:impact-a',
        graph_id=graph.graph_id,
        graph_digest=graph.digest,
        test_to_nodes={
            'tests/test_a.py::test_run': ('symbol:pkg.a:A.run',),
            'tests/test_b.py::test_call': ('symbol:pkg.b:B.call',),
            'tests/test_c.py::test_use': ('symbol:pkg.c:C.use',),
        },
        provenance_refs=('coverage:run-1',),
    )
    proof = EngineeringTestSelectionEngine().select(impact=impact, coverage=coverage)
    assert proof.complete
    assert proof.uncovered_nodes == ()
    assert proof.selected_tests == (
        'tests/test_a.py::test_run',
        'tests/test_b.py::test_call',
        'tests/test_c.py::test_use',
    )


def test_selection_fails_closed_when_impact_has_no_coverage():
    graph = _graph()
    impact = EngineeringImpactAnalyzer().analyze(patch=_Patch(), graph=graph)
    coverage = EngineeringTestCoverageLedger().register(
        source_revision='git:impact-a',
        graph_id=graph.graph_id,
        graph_digest=graph.digest,
        test_to_nodes={'tests/test_a.py::test_run': ('symbol:pkg.a:A.run',)},
        provenance_refs=('coverage:partial',),
    )
    proof = EngineeringTestSelectionEngine().select(impact=impact, coverage=coverage)
    assert not proof.complete
    assert proof.uncovered_nodes == ('symbol:pkg.b:B.call', 'symbol:pkg.c:C.use')


def test_selection_rejects_stale_coverage_source_revision():
    graph = _graph()
    impact = EngineeringImpactAnalyzer().analyze(patch=_Patch(), graph=graph)
    coverage = EngineeringTestCoverageLedger().register(
        source_revision='git:other',
        graph_id=graph.graph_id,
        graph_digest=graph.digest,
        test_to_nodes={'tests/test_a.py::test_run': ('symbol:pkg.a:A.run',)},
        provenance_refs=('coverage:stale',),
    )
    with pytest.raises(ValueError, match='source revision'):
        EngineeringTestSelectionEngine().select(impact=impact, coverage=coverage)
