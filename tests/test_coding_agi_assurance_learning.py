from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import SkillScope


def test_assurance_learning_remains_personal_candidate_until_normal_promotion():
    runtime = OrganizationRuntime.first_generation()
    skill = runtime.assurance.propose_personal_skill(
        agent_id='security.adversarial.01',
        name='cross-boundary malformed-state probe',
        body='vary authorization state transitions while preserving a heldout tenant-boundary oracle',
        object_refs=('SUBJECT-SECURITY',), evidence_refs=('EV-ADVERSARIAL-SKILL',),
    )
    assert skill.owner_agent_id == 'security.adversarial.01'
    assert skill.scope is SkillScope.CANDIDATE
