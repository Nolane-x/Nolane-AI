from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import SkillScope


def test_operational_learning_remains_personal_candidate_until_normal_promotion():
    runtime = OrganizationRuntime.first_generation()
    skill = runtime.operations.propose_personal_skill(
        agent_id='reliability.recovery.01',
        name='restart idempotency checkpoint probe',
        body='inject restart after checkpoint commit and verify deduplication under a heldout replay workload',
        object_refs=('OPS-INCIDENT-1',), evidence_refs=('EV-OPS-SKILL',),
    )
    assert skill.owner_agent_id == 'reliability.recovery.01'
    assert skill.scope is SkillScope.CANDIDATE
