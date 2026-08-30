from dataclasses import dataclass

import pytest

from nolane.external_core.software_engineering_impact import (
    EngineeringDependencyGraphLedger,
    EngineeringImpactAnalyzer,
    EngineeringTestCoverageLedger,
    EngineeringTestExecutionLedger,
    EngineeringTestSelectionEngine,
)


@dataclass(frozen=True)
class _Patch:
    patch_id: str = 'patch-execution-1'
    producer_agent_id: str = 'coding.backend.01'
    task_id: str = 'task-execution-1'
    touched_files: tuple[str, ...] = ()
    touched_symbols: tuple[str, ...] = ('A.run',)

    def to_state(self):
        return {
            'patch_id': self.patch_id,
            'producer_agent_id': self.producer_agent_id,
            'task_id': self.task_id,
            'touched_files': list(self.touched_files),
            'touched_symbols': list(self.touched_symbols),
        }


def _selection():
    graph = EngineeringDependencyGraphLedger().register(
        source_revision='git:execution-a',
        nodes=('symbol:A.run', 'symbol:B.call'),
        dependency_edges=(('symbol:A.run', 'symbol:B.call'),),
        component_membership={
            'symbol:A.run': 'component:a',
            'symbol:B.call': 'component:b',
        },
        provenance_refs=('static:execution-a',),
    )
    impact = EngineeringImpactAnalyzer().analyze(patch=_Patch(), graph=graph)
    coverage = EngineeringTestCoverageLedger().register(
        source_revision='git:execution-a',
        graph_id=graph.graph_id,
        graph_digest=graph.digest,
        test_to_nodes={
            'tests/test_a.py::test_run': ('symbol:A.run',),
            'tests/test_b.py::test_call': ('symbol:B.call',),
        },
        provenance_refs=('coverage:execution-a',),
    )
    return EngineeringTestSelectionEngine().select(impact=impact, coverage=coverage)


def test_execution_receipt_proves_every_selected_test_ran_and_passed():
    selection = _selection()
    receipt = EngineeringTestExecutionLedger().record(
        selection=selection,
        source_revision='git:execution-a',
        environment_digest='env:py313',
        executed_tests=selection.selected_tests,
        failed_tests=(),
        evidence_refs=('pytest:junit:123',),
    )
    assert receipt.passed
    assert receipt.missing_tests == ()
    assert receipt.failed_tests == ()
    assert receipt.selection_id == selection.selection_id


def test_execution_receipt_is_not_green_when_selected_test_was_not_executed():
    selection = _selection()
    receipt = EngineeringTestExecutionLedger().record(
        selection=selection,
        source_revision='git:execution-a',
        environment_digest='env:py313',
        executed_tests=(selection.selected_tests[0],),
        failed_tests=(),
        evidence_refs=('pytest:junit:partial',),
    )
    assert not receipt.passed
    assert receipt.missing_tests == (selection.selected_tests[1],)


def test_execution_receipt_is_not_green_when_selected_test_failed():
    selection = _selection()
    receipt = EngineeringTestExecutionLedger().record(
        selection=selection,
        source_revision='git:execution-a',
        environment_digest='env:py313',
        executed_tests=selection.selected_tests,
        failed_tests=(selection.selected_tests[0],),
        evidence_refs=('pytest:junit:failed',),
    )
    assert not receipt.passed
    assert receipt.failed_tests == (selection.selected_tests[0],)


def test_execution_rejects_failed_test_that_was_not_executed():
    selection = _selection()
    with pytest.raises(ValueError, match='failed test.*executed'):
        EngineeringTestExecutionLedger().record(
            selection=selection,
            source_revision='git:execution-a',
            environment_digest='env:py313',
            executed_tests=selection.selected_tests,
            failed_tests=('tests/unknown.py::test_unknown',),
            evidence_refs=('pytest:junit:invalid',),
        )


def test_execution_requires_same_source_revision_as_selection():
    selection = _selection()
    with pytest.raises(ValueError, match='source revision'):
        EngineeringTestExecutionLedger().record(
            selection=selection,
            source_revision='git:other',
            environment_digest='env:py313',
            executed_tests=selection.selected_tests,
            failed_tests=(),
            evidence_refs=('pytest:junit:stale',),
        )
