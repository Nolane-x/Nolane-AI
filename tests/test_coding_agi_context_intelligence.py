from dataclasses import replace

import pytest

from cogcoder.organization.context_intelligence import ContextBudget, ContextDeltaKind
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind, MemoryScope
from nolane.core.canonical_digest import canonical_digest


def test_context_capsule_exposes_semantic_delta_and_bounded_overload_metrics():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-CONTEXT-1', title='Compile bounded context', plan_node_id='P-CONTEXT-1')
    runtime.tasks.lease('T-CONTEXT-1', 'memory.context-compiler.01')
    for index in range(30):
        runtime.memory.write(
            MemoryScope.REGION, f'context candidate {index} ' + ('z' * 90),
            owner_agent_id='memory.chief', region='memory-context-knowledge', tags=('context',),
            evidence_ids=(f'EV-M-{index}',), confidence=0.6,
        )
    result = runtime.memory_context.compile_context(
        'memory.context-compiler.01', task_id='T-CONTEXT-1',
        budget=ContextBudget(max_memories=4, max_events=4, max_estimated_units=500),
    )
    assert result.capsule.semantic_delta_digest == result.delta.digest
    assert result.capsule.context_compilation_receipt_id == result.receipt.receipt_id
    assert result.capsule.context_budget_units == result.receipt.selected_units
    assert result.capsule.context_overload_ratio == result.receipt.overload_ratio
    assert len(result.capsule.memories) <= 4
    assert result.receipt.memory_candidate_count >= len(result.capsule.memories)
    assert result.receipt.dropped_object_ids


def test_plan_change_and_central_intervention_become_typed_semantic_delta_items():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-CONTEXT-2', title='Track delta', plan_node_id='P-CONTEXT-2')
    runtime.tasks.lease('T-CONTEXT-2', 'coding.backend.01')
    runtime.checkpoint_agent('coding.backend.01')
    checkpoint_id = runtime.memory_context.capture_continuity('coding.backend.01').checkpoint_id

    gap = runtime.report_plan_gap(
        source_agent_id='coding.backend.01', task_id='T-CONTEXT-2',
        reason='need compatibility task', suggested_nodes=('P-COMPAT',), evidence_ids=('EV-GAP',),
    )
    runtime.tasks.apply_plan_amendment('planning.chief', gap.event_id, added_nodes=('P-COMPAT',))
    runtime.central_intervene(
        target_agent_id='coding.backend.01', directive='preserve backward compatibility', evidence_ids=('EV-CENTRAL',),
    )
    result = runtime.memory_context.compile_context(
        'coding.backend.01', continuity_checkpoint_id=checkpoint_id,
        budget=ContextBudget(max_memories=16, max_events=16, max_estimated_units=4096),
    )
    kinds = {item.kind for item in result.delta.items}
    assert ContextDeltaKind.PLAN_CHANGED in kinds
    assert ContextDeltaKind.CENTRAL_INTERVENTION in kinds
    assert result.receipt.stale_context_warnings


def test_context_receipt_uses_exact_full_capsule_authority_snapshot(monkeypatch):
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task(
        'T-CONTEXT-ATOMIC', title='Compile one atomic authority snapshot', plan_node_id='P-CONTEXT-ATOMIC',
    )
    runtime.tasks.lease('T-CONTEXT-ATOMIC', 'coding.backend.01')

    compiler = runtime.memory_context.context_intelligence
    base_context = compiler._base_context
    assert base_context is not None
    original_compile = base_context.compile

    def compile_then_advance_plan(*args, **kwargs):
        capsule = original_compile(*args, **kwargs)
        gap = runtime.report_plan_gap(
            source_agent_id='coding.backend.01',
            task_id='T-CONTEXT-ATOMIC',
            reason='advance planning after capsule authority snapshot',
            suggested_nodes=('P-CONTEXT-AFTER-SNAPSHOT',),
            evidence_ids=('EV-CONTEXT-ATOMIC',),
        )
        runtime.tasks.apply_plan_amendment(
            'planning.chief', gap.event_id, added_nodes=('P-CONTEXT-AFTER-SNAPSHOT',),
        )
        return capsule

    monkeypatch.setattr(base_context, 'compile', compile_then_advance_plan)
    result = runtime.memory_context.compile_context(
        'coding.backend.01',
        task_id='T-CONTEXT-ATOMIC',
        budget=ContextBudget(max_memories=8, max_events=8, max_estimated_units=2048),
    )

    capsule_frontier = tuple((str(name), str(value)) for name, value in result.capsule.authoritative_artifacts)
    authority_names = {name for name, _ in capsule_frontier}
    assert {'master-plan', 'requirements', 'architecture-graph', 'integration-state', 'coding-state'} <= authority_names
    assert result.capsule.plan_version == int(dict(result.capsule.authoritative_artifacts)['master-plan'])
    assert result.receipt.authoritative_frontier == capsule_frontier

    verified = runtime.memory_context.verify_context_capsule(result.capsule)
    assert verified is not None
    assert verified.receipt.authoritative_frontier == capsule_frontier



def test_context_verifier_rejects_redigested_receipt_missing_nonlegacy_authority():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task(
        'T-CONTEXT-SCOPED-TAMPER', title='Reject incomplete scoped provenance', plan_node_id='P-CONTEXT-SCOPED-TAMPER',
    )
    runtime.tasks.lease('T-CONTEXT-SCOPED-TAMPER', 'coding.backend.01')
    result = runtime.memory_context.compile_context(
        'coding.backend.01',
        task_id='T-CONTEXT-SCOPED-TAMPER',
        budget=ContextBudget(max_memories=8, max_events=8, max_estimated_units=2048),
    )

    assert 'integration-state' in {name for name, _ in result.receipt.authoritative_frontier}
    tampered_frontier = tuple(
        (name, value) for name, value in result.receipt.authoritative_frontier
        if name != 'integration-state'
    )
    tampered = replace(result.receipt, authoritative_frontier=tampered_frontier)
    tampered = replace(tampered, digest=canonical_digest(tampered.payload()))
    runtime.memory_context.context_intelligence._receipts[tampered.receipt_id] = tampered

    with pytest.raises(ValueError, match='authority provenance'):
        runtime.memory_context.verify_context_capsule(result.capsule)


def test_context_verifier_rejects_redigested_receipt_with_conflicting_capsule_frontier():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task(
        'T-CONTEXT-TAMPER', title='Reject split-brain provenance', plan_node_id='P-CONTEXT-TAMPER',
    )
    runtime.tasks.lease('T-CONTEXT-TAMPER', 'coding.backend.01')
    result = runtime.memory_context.compile_context(
        'coding.backend.01',
        task_id='T-CONTEXT-TAMPER',
        budget=ContextBudget(max_memories=8, max_events=8, max_estimated_units=2048),
    )

    tampered_frontier = tuple(
        (name, str(int(value) + 1) if name == 'master-plan' else value)
        for name, value in result.receipt.authoritative_frontier
    )
    tampered = replace(result.receipt, authoritative_frontier=tampered_frontier)
    tampered = replace(tampered, digest=canonical_digest(tampered.payload()))
    runtime.memory_context.context_intelligence._receipts[tampered.receipt_id] = tampered

    with pytest.raises(ValueError, match='authority provenance'):
        runtime.memory_context.verify_context_capsule(result.capsule)
