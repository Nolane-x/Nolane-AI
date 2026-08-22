from cogcoder.organization.architecture import ArchitectureComponent, ComponentKind
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.types import EventKind


def test_coder_feedback_emits_plan_gap_without_mutating_plan_authority():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-FEEDBACK', title='Implement migration', plan_node_id='P-FEEDBACK')
    runtime.tasks.lease('T-FEEDBACK', 'coding.backend.01')
    before = runtime.planning.to_state()

    event = runtime.coding.report_plan_gap(
        source_agent_id='coding.backend.01',
        task_id='T-FEEDBACK',
        reason='rollback task missing',
        suggested_nodes=('P-ROLLBACK',),
        evidence_refs=('EV-GAP-1',),
    )

    assert event.kind is EventKind.PLAN_GAP_DETECTED
    assert event.target_agent_id == 'planning.chief'
    assert runtime.planning.to_state() == before


def test_coder_feedback_emits_architecture_concern_without_mutating_architecture():
    runtime = OrganizationRuntime.first_generation()
    runtime.architecture.apply_revision(
        actor_agent_id='architecture.chief',
        reason='seed service boundary',
        evidence_refs=('EV-ARCH-SEED',),
        upsert_components=(ArchitectureComponent(
            'COMP-AUTH', 'Auth Service', ComponentKind.SERVICE,
            'core-coding', 'internal',
        ),),
    )
    before = runtime.architecture.to_state()

    event = runtime.coding.report_architecture_concern(
        source_agent_id='coding.api-interface.01',
        component_refs=('COMP-AUTH',),
        observation='public token contract would become incompatible',
        alternatives=('add versioned endpoint', 'preserve compatibility adapter'),
        evidence_refs=('EV-ARCH-CONCERN',),
        severity=80,
    )

    assert event.kind is EventKind.ARCHITECTURE_CONCERN
    assert event.target_agent_id == 'architecture.chief'
    assert runtime.architecture.to_state() == before
