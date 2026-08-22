from cogcoder.organization.architecture import ArchitectureComponent, ComponentKind
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind, SkillScope


def test_ui_agents_emit_plan_gap_without_mutating_planning_authority():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-UI-FEEDBACK', title='Implement onboarding', plan_node_id='P-UI-FEEDBACK')
    runtime.tasks.lease('T-UI-FEEDBACK', 'frontend.component.01')
    before = runtime.planning.to_state()
    event = runtime.ui.report_plan_gap(
        source_agent_id='frontend.component.01', task_id='T-UI-FEEDBACK',
        reason='empty-state design task missing', suggested_nodes=('P-EMPTY-STATE',),
        evidence_refs=('EV-UI-GAP',),
    )
    assert event.kind is EventKind.PLAN_GAP_DETECTED
    assert event.target_agent_id == 'planning.chief'
    assert runtime.planning.to_state() == before


def test_ui_agents_emit_architecture_concern_without_mutating_architecture_authority():
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id='architecture.chief', reason='seed frontend shell', evidence_refs=('EV-ARCH-SEED',),
        upsert_components=(ArchitectureComponent('COMP-UI-SHELL', 'UI Shell', ComponentKind.UI, 'frontend-ui', 'client'),),
    )
    before = runtime.architecture.to_state()
    event = runtime.ui.report_architecture_concern(
        source_agent_id='frontend.browser-runtime.01', component_refs=('COMP-UI-SHELL',),
        observation='global listener leaks across route boundary',
        alternatives=('scope listener to route root', 'introduce lifecycle adapter'),
        evidence_refs=('EV-UI-ARCH',), severity=75,
    )
    assert event.kind is EventKind.ARCHITECTURE_CONCERN
    assert event.target_agent_id == 'architecture.chief'
    assert runtime.architecture.to_state() == before


def test_ui_ux_learning_episode_stays_personal_candidate_until_normal_promotion():
    runtime = OrganizationRuntime.first_generation()
    skill = runtime.ui.propose_personal_skill(
        agent_id='ux.visual-accessibility.01',
        name='focus-visible remediation',
        body='preserve visible focus while avoiding layout shift across responsive states',
        object_refs=('FLOW-A11Y',), evidence_refs=('EV-SKILL-UI',),
    )
    assert skill.owner_agent_id == 'ux.visual-accessibility.01'
    assert skill.scope is SkillScope.CANDIDATE
