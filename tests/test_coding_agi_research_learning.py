from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import SkillScope


def test_verified_research_lesson_stays_personal_candidate_until_governed_promotion():
    runtime = OrganizationRuntime.first_generation()
    skill = runtime.research.propose_personal_skill(
        agent_id='research.repo-archaeology.01',
        name='history-first convention recovery',
        body='inspect commit history and contract tests before inferring repository conventions',
        object_refs=('repo:constructor-history',),
        evidence_refs=('EV-RESEARCH-LESSON',),
    )
    assert skill.owner_agent_id == 'research.repo-archaeology.01'
    assert skill.scope is SkillScope.CANDIDATE
