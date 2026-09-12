from dataclasses import replace

import pytest

from cogcoder.organization.context_intelligence import ContextBudget, ContextDeltaKind
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind, MemoryScope
from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.evidence import EvidenceRecord
from nolane.memory.skills import SkillScope


def _promoted_personal_skill(runtime: OrganizationRuntime, owner_agent_id: str):
    owner = runtime.registry.get(owner_agent_id)
    skill = runtime.evolution.propose(
        owner_agent_id=owner.agent_id,
        region=owner.region,
        name='context-receipt-skill-frontier',
        body='context provenance must bind the exact applicable skill set',
    )
    evidence = EvidenceRecord(
        'context-skill-frontier-independent-verification',
        'memory.context-compiler.01',
        True,
        false_accepts=0,
        regressions=0,
    )
    authority = runtime.learning_substrate.learning_authority
    lease = authority.issue(
        subject_kind='skill',
        subject_id=skill.skill_id,
        operation_class='skill.verify',
        producer_agent_id=skill.owner_agent_id,
        evidence=evidence,
        subject_digest=runtime.evolution.verification_subject_digest(skill.skill_id),
    )
    runtime.evolution.verify(skill.skill_id, evidence, authority_lease_id=lease.lease_id)
    runtime.learning_substrate.record_skill_validation(
        skill.skill_id,
        regression_evidence_ids=('context-skill-regression-a', 'context-skill-regression-b'),
        causal_ablation_evidence_ids=('context-skill-causal-ablation',),
        regression_evidence_families={
            'context-skill-regression-a': 'context-skill-family-a',
            'context-skill-regression-b': 'context-skill-family-b',
        },
        causal_ablation_evidence_families={
            'context-skill-causal-ablation': 'context-skill-causal-family',
        },
    )
    return runtime.individual_evolution.promote_skill(skill.skill_id, SkillScope.PERSONAL)


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
    assert type(result.receipt).from_state(result.receipt.to_state()) == result.receipt

    verified = runtime.memory_context.verify_context_capsule(result.capsule)
    assert verified is not None
    assert verified.receipt.authoritative_frontier == capsule_frontier


def test_context_receipt_binds_exact_applicable_skill_frontier_and_round_trips():
    runtime = OrganizationRuntime.first_generation()
    skill = _promoted_personal_skill(runtime, 'memory.chief')
    result = runtime.memory_context.compile_context(
        'memory.chief',
        budget=ContextBudget(max_memories=8, max_events=8, max_estimated_units=2048),
    )

    assert result.capsule.applicable_skill_ids == (skill.skill_id,)
    expected = canonical_digest({'skill_ids': list(result.capsule.applicable_skill_ids)})
    assert dict(result.capsule.authoritative_artifacts)['skill-frontier'] == expected
    assert dict(result.receipt.authoritative_frontier)['skill-frontier'] == expected
    assert type(result.receipt).from_state(result.receipt.to_state()) == result.receipt


def test_context_compilation_reads_applicable_skill_frontier_once(monkeypatch):
    runtime = OrganizationRuntime.first_generation()
    skill = _promoted_personal_skill(runtime, 'memory.chief')
    original = runtime.evolution.skills_for
    calls = 0

    def counted_skills_for(agent_id: str, *, region: str):
        nonlocal calls
        calls += 1
        return original(agent_id, region=region)

    monkeypatch.setattr(runtime.evolution, 'skills_for', counted_skills_for)
    result = runtime.memory_context.compile_context(
        'memory.chief',
        budget=ContextBudget(max_memories=8, max_events=8, max_estimated_units=2048),
    )

    assert calls == 1
    assert result.capsule.applicable_skill_ids == (skill.skill_id,)
    expected = canonical_digest({'skill_ids': [skill.skill_id]})
    assert dict(result.capsule.authoritative_artifacts)['skill-frontier'] == expected
    assert dict(result.receipt.authoritative_frontier)['skill-frontier'] == expected


def test_fallback_context_preserves_exact_skill_frontier_provenance(monkeypatch):
    runtime = OrganizationRuntime.first_generation()
    skill = _promoted_personal_skill(runtime, 'memory.chief')
    compiler = runtime.memory_context.context_intelligence
    monkeypatch.setattr(compiler, '_base_context', None)

    result = runtime.memory_context.compile_context(
        'memory.chief',
        budget=ContextBudget(max_memories=8, max_events=8, max_estimated_units=2048),
    )

    assert result.capsule.applicable_skill_ids == (skill.skill_id,)
    expected = canonical_digest({'skill_ids': [skill.skill_id]})
    assert dict(result.capsule.authoritative_artifacts)['skill-frontier'] == expected
    assert dict(result.receipt.authoritative_frontier)['skill-frontier'] == expected


def test_skill_frontier_ignores_evidence_changes_when_applicability_is_unchanged():
    runtime = OrganizationRuntime.first_generation()
    skill = _promoted_personal_skill(runtime, 'memory.chief')
    before = dict(runtime.context.authoritative_artifacts('memory.chief'))['skill-frontier']

    evidence = EvidenceRecord(
        'context-skill-frontier-second-verification',
        'memory.knowledge-graph.01',
        True,
        false_accepts=0,
        regressions=0,
    )
    authority = runtime.learning_substrate.learning_authority
    lease = authority.issue(
        subject_kind='skill',
        subject_id=skill.skill_id,
        operation_class='skill.verify',
        producer_agent_id=skill.owner_agent_id,
        evidence=evidence,
        subject_digest=runtime.evolution.verification_subject_digest(skill.skill_id),
    )
    runtime.evolution.verify(skill.skill_id, evidence, authority_lease_id=lease.lease_id)

    after = dict(runtime.context.authoritative_artifacts('memory.chief'))['skill-frontier']
    assert before == after
    assert tuple(
        row.skill_id
        for row in runtime.evolution.skills_for('memory.chief', region='memory-context-knowledge')
    ) == (skill.skill_id,)


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
