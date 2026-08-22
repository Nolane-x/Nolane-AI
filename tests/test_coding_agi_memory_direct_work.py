import pytest

from cogcoder.organization.context_intelligence import ContextBudget
from cogcoder.organization.memory_lifecycle import MemoryRelationKind
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import MemoryScope, MemoryStatus


def test_memory_chief_personally_repairs_contradicted_context_and_completes_task():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-MEM-CHIEF', title='Repair poisoned resume context', plan_node_id='P-MEM-CHIEF')
    runtime.tasks.lease('T-MEM-CHIEF', 'memory.chief')

    old = runtime.memory.write(
        MemoryScope.PERSONAL, 'service contract uses v1', owner_agent_id='coding.backend.01',
        tags=('service-contract',), evidence_ids=('EV-OLD',), confidence=1.0,
    )
    corrected = runtime.memory.write(
        MemoryScope.PERSONAL, 'service contract uses v2', owner_agent_id='coding.backend.01',
        tags=('service-contract',), evidence_ids=('EV-NEW',), confidence=0.9,
    )
    runtime.memory_context.relations.add(
        actor_agent_id='memory.chief', source_memory_id=corrected.memory_id,
        target_memory_id=old.memory_id, kind=MemoryRelationKind.CONTRADICTS,
        evidence_refs=('EV-NEW',),
    )
    repair = runtime.memory_context.repair_contradiction(
        chief_agent_id='memory.chief', rejected_memory_ids=(old.memory_id,),
        corrected_memory_id=corrected.memory_id, reason='new verified contract supersedes stale belief',
        evidence_refs=('EV-NEW',), affected_agent_id='coding.backend.01',
        budget=ContextBudget(max_memories=16, max_events=16, max_estimated_units=4096),
    )
    assert runtime.memory.get(old.memory_id).status is MemoryStatus.CONTRADICTED
    assert repair.corrected_memory_id == corrected.memory_id
    assert old.memory_id not in repair.selected_memory_ids
    assert corrected.memory_id in repair.selected_memory_ids

    artifact = runtime.artifacts.put(
        kind='memory-context-repair', producer_agent_id='memory.chief', content=repair.digest,
        evidence_refs=('EV-NEW',),
    )
    completed = runtime.chief_direct_work(
        'memory.chief', 'T-MEM-CHIEF', output_artifact_ids=(artifact.artifact_id,),
    )
    assert completed['chief_agent_id'] == 'memory.chief'


def test_only_memory_chief_can_execute_governed_cross_memory_repair():
    runtime = OrganizationRuntime.first_generation()
    old = runtime.memory.write(MemoryScope.GLOBAL, 'old', owner_agent_id='memory.chief')
    corrected = runtime.memory.write(MemoryScope.GLOBAL, 'new', owner_agent_id='memory.chief', evidence_ids=('EV-NEW',))
    with pytest.raises(PermissionError):
        runtime.memory_context.repair_contradiction(
            chief_agent_id='memory.lifecycle.01', rejected_memory_ids=(old.memory_id,),
            corrected_memory_id=corrected.memory_id, reason='specialist tries chief override',
            evidence_refs=('EV-NEW',), affected_agent_id='coding.backend.01',
            budget=ContextBudget(max_memories=8, max_events=8, max_estimated_units=2048),
        )
