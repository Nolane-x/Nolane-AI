from cogcoder.organization.coding import PatchVerificationEvidence
from cogcoder.organization.coding_profiles import CodingDomain, CodingWorkRequest
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.ui import UIQualityEvidence, UIQualityKind
from cogcoder.organization.ui_design import UXAcceptanceCriterion, UXTransition
from cogcoder.organization.ui_observations import Viewport
from cogcoder.organization.ui_profiles import UIDomain, UIWorkRequest


def _quality(kind, eid, obs):
    return UIQualityEvidence(
        evidence_id=eid, verifier_agent_id='verification.integration-e2e.01', kind=kind,
        passed=True, observation_ids=obs, evidence_refs=(eid + '-RAW',),
    )


def test_frontend_chief_personally_implements_browser_grounded_ui_flow():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-FRONTEND-CHIEF', title='Repair account settings flow', plan_node_id='P-FRONTEND-CHIEF')
    runtime.tasks.lease('T-FRONTEND-CHIEF', 'frontend.chief')
    ui_assignment = runtime.ui.request_work(UIWorkRequest(
        work_id='W-FRONTEND-CHIEF', task_id='T-FRONTEND-CHIEF',
        requested_domains=(UIDomain.FRONTEND_CROSS_SYSTEM,), scope_hints=('cross-frontend', 'integration'),
        priority=95, requester_agent_id='frontend.chief', evidence_refs=('EV-UI-CHIEF',),
    ))
    assert ui_assignment.selected_agent_id == 'frontend.chief'
    grant = runtime.coding.grant_external_coder(
        agent_id='frontend.chief', task_id='T-FRONTEND-CHIEF', actor_agent_id='coding.chief',
        reason='Frontend Chief direct implementation', evidence_refs=('EV-GRANT-CHIEF',),
    )
    task = runtime.tasks.get('T-FRONTEND-CHIEF')
    coding_request = CodingWorkRequest(
        work_id='W-FRONTEND-CHIEF', task_id=task.task_id, plan_node_id=task.plan_node_id,
        requirement_refs=(), architecture_version=runtime.architecture.graph.version,
        plan_version=runtime.planning.graph.version, requested_domains=(CodingDomain.CROSS_SYSTEM,),
        scope_hints=('frontend',), acceptance_refs=('UI-AC-CHIEF',), priority=95,
        requester_agent_id='frontend.chief', evidence_refs=('EV-CODE-CHIEF',),
    )
    runtime.coding.request_external_work(coding_request, assignee_agent_id='frontend.chief', grant_id=grant.grant_id)
    runtime.coding.claim_sources(agent_id='frontend.chief', task_id=task.task_id, file_paths=('src/ui/account_settings.py',))
    patch = runtime.coding.submit_patch(
        producer_agent_id='frontend.chief', task_id=task.task_id, work_id='W-FRONTEND-CHIEF',
        touched_files=('src/ui/account_settings.py',), patch_artifact_id='artifact-frontend-chief-patch',
        compile_evidence_refs=('EV-COMPILE-CHIEF',), test_evidence_refs=('EV-TEST-CHIEF',),
    )
    coding_ready = runtime.coding.assess_readiness(
        patch.patch_id, PatchVerificationEvidence('EV-CODE-VERIFY-CHIEF', 'verification.unit-property.01', True),
    )
    observations = []
    for width, height, suffix in ((390, 844, 'mobile'), (1440, 900, 'desktop')):
        browser = runtime.artifacts.put(kind='browser-runtime', producer_agent_id='frontend.chief', content='runtime-' + suffix)
        dom = runtime.artifacts.put(kind='dom-snapshot', producer_agent_id='frontend.chief', content='<main>' + suffix + '</main>')
        shot = runtime.artifacts.put(kind='screenshot', producer_agent_id='frontend.chief', content='pixels-' + suffix)
        a11y = runtime.artifacts.put(kind='accessibility-tree', producer_agent_id='ux.visual-accessibility.01', content='settings form ' + suffix)
        observations.append(runtime.ui.record_observation(
            task_id=task.task_id, work_id='W-FRONTEND-CHIEF', patch_id=patch.patch_id,
            producer_agent_id='frontend.chief', viewport=Viewport(width, height, 1.0),
            browser_runtime_artifact_id=browser.artifact_id, dom_artifact_id=dom.artifact_id,
            screenshot_artifact_id=shot.artifact_id, accessibility_tree_artifact_id=a11y.artifact_id,
            evidence_refs=('EV-OBS-' + suffix,),
        ))
    obs_ids = tuple(x.observation_id for x in observations)
    quality = tuple(runtime.ui.record_quality_evidence(_quality(kind, eid, obs_ids)) for kind, eid in (
        (UIQualityKind.VISUAL_DIFF, 'EV-VISUAL-CHIEF'),
        (UIQualityKind.RESPONSIVE, 'EV-RESP-CHIEF'),
        (UIQualityKind.ACCESSIBILITY, 'EV-A11Y-CHIEF'),
    ))
    ui_ready = runtime.ui.assess_readiness(
        patch_id=patch.patch_id, coding_readiness_receipt_id=coding_ready.receipt_id,
        observation_ids=obs_ids, quality_evidence_ids=tuple(x.evidence_id for x in quality),
    )
    assert ui_ready.ready is True
    completion = runtime.chief_direct_work('frontend.chief', task.task_id, output_artifact_ids=(patch.patch_artifact_id,))
    assert completion['chief_agent_id'] == 'frontend.chief'
    assert runtime.tasks.get(task.task_id).completed_by == 'frontend.chief'


def test_ux_chief_personally_redesigns_and_accepts_bounded_flow_with_testable_criteria():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-UX-CHIEF', title='Redesign save flow', plan_node_id='P-UX-CHIEF')
    runtime.tasks.lease('T-UX-CHIEF', 'ux.chief')
    proposal = runtime.ui.design.propose(
        source_agent_id='ux.chief', flow_id='FLOW-SAVE', task_id='T-UX-CHIEF',
        goal='Make saving state explicit and keyboard accessible',
        states=('editing', 'saving', 'saved', 'error'),
        transitions=(UXTransition('editing', 'saving', 'save'), UXTransition('saving', 'saved', 'success'), UXTransition('saving', 'error', 'failure')),
        design_token_refs=('status.success', 'status.error'),
        responsive_expectations=('mobile status below actions', 'desktop status inline'),
        accessibility_expectations=('saving state announced', 'focus remains stable'),
        acceptance_criteria=(UXAcceptanceCriterion(
            'UX-SAVE-AC', 'Keyboard save announces progress and a final saved or error state',
            'accessibility-interaction', ('keyboard-e2e', 'live-region-tree'),
        ),), evidence_refs=('EV-UX-CHIEF',),
    )
    accepted = runtime.ui.design.accept(proposal.proposal_id, actor_agent_id='ux.chief')
    artifact = runtime.artifacts.put(
        kind='ux-flow-spec', producer_agent_id='ux.chief', content=accepted.digest,
        evidence_refs=('EV-UX-CHIEF',), metadata={'flow_id': accepted.flow_id, 'revision': accepted.revision},
    )
    completion = runtime.chief_direct_work('ux.chief', 'T-UX-CHIEF', output_artifact_ids=(artifact.artifact_id,))
    assert completion['chief_agent_id'] == 'ux.chief'
    assert accepted.acceptance_criteria[0].evidence_expectations
