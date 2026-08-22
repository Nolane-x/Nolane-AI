from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import SkillScope


def test_memory_context_personal_lesson_remains_candidate_until_governed_promotion():
    runtime = OrganizationRuntime.first_generation()
    skill = runtime.memory_context.propose_personal_skill(
        agent_id='memory.context-compiler.01',
        name='prefer checkpoint delta over history replay',
        body='When a valid continuity checkpoint exists, reconstruct from post-checkpoint semantic changes before considering older history.',
        object_refs=('context-receipt-1',),
        evidence_refs=('EV-CONTEXT-LESSON',),
    )
    assert skill.owner_agent_id == 'memory.context-compiler.01'
    assert skill.scope is SkillScope.CANDIDATE
