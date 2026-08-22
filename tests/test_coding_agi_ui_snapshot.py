from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.snapshot import OrganizationSnapshot
from cogcoder.organization.ui import UIQualityEvidence, UIQualityKind
from cogcoder.organization.ui_design import UXAcceptanceCriterion, UXTransition
from cogcoder.organization.ui_observations import Viewport
from cogcoder.organization.ui_profiles import UIDomain, UIWorkRequest


def test_ui_state_and_cross_region_grant_round_trip_exactly_through_organization_snapshot():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-UI-SNAP', title='Snapshot UI state', plan_node_id='P-UI-SNAP')
    runtime.tasks.lease('T-UI-SNAP', 'frontend.component.01')
    runtime.ui.request_work(UIWorkRequest(
        work_id='W-UI-SNAP', task_id='T-UI-SNAP', requested_domains=(UIDomain.COMPONENT,),
        scope_hints=('component',), priority=50, requester_agent_id='frontend.chief', evidence_refs=('EV-UI-SNAP',),
    ))
    runtime.coding.grant_external_coder(
        agent_id='frontend.component.01', task_id='T-UI-SNAP', actor_agent_id='coding.chief',
        reason='snapshot grant', evidence_refs=('EV-GRANT-SNAP',),
    )
    browser = runtime.artifacts.put(kind='browser-runtime', producer_agent_id='frontend.browser-runtime.01', content='runtime')
    dom = runtime.artifacts.put(kind='dom-snapshot', producer_agent_id='frontend.browser-runtime.01', content='<button>Save</button>')
    shot = runtime.artifacts.put(kind='screenshot', producer_agent_id='frontend.browser-runtime.01', content='pixels')
    obs = runtime.ui.record_observation(
        task_id='T-UI-SNAP', work_id='W-UI-SNAP', patch_id=None,
        producer_agent_id='frontend.browser-runtime.01', viewport=Viewport(1024, 768, 1.0),
        browser_runtime_artifact_id=browser.artifact_id, dom_artifact_id=dom.artifact_id,
        screenshot_artifact_id=shot.artifact_id, evidence_refs=('EV-OBS-SNAP',),
    )
    runtime.ui.record_quality_evidence(UIQualityEvidence(
        evidence_id='EV-QUALITY-SNAP', verifier_agent_id='verification.integration-e2e.01',
        kind=UIQualityKind.VISUAL_DIFF, passed=True, observation_ids=(obs.observation_id,),
        evidence_refs=('EV-QUALITY-RAW',),
    ))
    proposal = runtime.ui.design.propose(
        source_agent_id='ux.flow.01', flow_id='FLOW-SNAP', task_id='T-UI-SNAP', goal='Save predictably',
        states=('editing', 'saved'), transitions=(UXTransition('editing', 'saved', 'save'),),
        design_token_refs=('action.save',), responsive_expectations=('mobile full-width save',),
        accessibility_expectations=('save has accessible name',),
        acceptance_criteria=(UXAcceptanceCriterion('AC-SNAP', 'Save reaches saved state', 'interaction', ('e2e',)),),
        evidence_refs=('EV-DESIGN-SNAP',),
    )
    runtime.ui.design.accept(proposal.proposal_id, actor_agent_id='ux.chief')

    first = OrganizationSnapshot.capture(runtime)
    restored = OrganizationSnapshot.from_json(first.to_json()).restore()
    second = OrganizationSnapshot.capture(restored)
    assert second.to_json() == first.to_json()
    assert restored.ui.to_state() == runtime.ui.to_state()
    assert restored.coding.to_state() == runtime.coding.to_state()
