import pytest

from cogcoder.organization.coding import PatchVerificationEvidence
from cogcoder.organization.coding_profiles import CodingDomain, CodingWorkRequest
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.ui import UIQualityEvidence, UIQualityKind
from cogcoder.organization.ui_observations import Viewport
from cogcoder.organization.ui_profiles import UIDomain, UIWorkRequest


def _coding_request(runtime, task_id='T-UI', work_id='W-UI'):
    task = runtime.tasks.get(task_id)
    return CodingWorkRequest(
        work_id=work_id, task_id=task_id, plan_node_id=task.plan_node_id,
        requirement_refs=(), architecture_version=runtime.architecture.graph.version,
        plan_version=runtime.planning.graph.version, requested_domains=(CodingDomain.CROSS_SYSTEM,),
        scope_hints=('frontend',), acceptance_refs=('UI-AC',), priority=80,
        requester_agent_id='frontend.chief', evidence_refs=('EV-CODING-WORK',),
    )


def _render(runtime, *, patch_id: str, width: int, height: int, suffix: str):
    producer = 'frontend.browser-runtime.01'
    browser = runtime.artifacts.put(kind='browser-runtime', producer_agent_id=producer, content=f'browser-{suffix}', evidence_refs=(f'EV-BROWSER-{suffix}',))
    dom = runtime.artifacts.put(kind='dom-snapshot', producer_agent_id=producer, content=f'<main>{suffix}</main>', evidence_refs=(f'EV-DOM-{suffix}',))
    screenshot = runtime.artifacts.put(kind='screenshot', producer_agent_id=producer, content=f'pixels-{suffix}', evidence_refs=(f'EV-SHOT-{suffix}',))
    a11y = runtime.artifacts.put(kind='accessibility-tree', producer_agent_id='ux.visual-accessibility.01', content=f'button submit {suffix}', evidence_refs=(f'EV-A11Y-TREE-{suffix}',))
    interaction = runtime.artifacts.put(kind='interaction-trace', producer_agent_id=producer, content=f'click submit {suffix}', evidence_refs=(f'EV-INTERACTION-{suffix}',))
    return runtime.ui.record_observation(
        task_id='T-UI', work_id='W-UI', patch_id=patch_id, producer_agent_id=producer,
        viewport=Viewport(width, height, 1.0), browser_runtime_artifact_id=browser.artifact_id,
        dom_artifact_id=dom.artifact_id, screenshot_artifact_id=screenshot.artifact_id,
        accessibility_tree_artifact_id=a11y.artifact_id,
        interaction_trace_artifact_id=interaction.artifact_id,
        evidence_refs=(f'EV-OBS-{suffix}',),
    )


def _prepared_runtime():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task('T-UI', title='Implement responsive editor', plan_node_id='P-UI')
    runtime.tasks.lease('T-UI', 'frontend.logic.01')
    ui_assignment = runtime.ui.request_work(UIWorkRequest(
        work_id='W-UI', task_id='T-UI', requested_domains=(UIDomain.FRONTEND_LOGIC,),
        scope_hints=('state', 'responsive'), priority=80, requester_agent_id='frontend.chief',
        evidence_refs=('EV-UI-WORK',),
    ))
    assert ui_assignment.selected_agent_id == 'frontend.logic.01'
    grant = runtime.coding.grant_external_coder(
        agent_id='frontend.logic.01', task_id='T-UI', actor_agent_id='coding.chief',
        reason='UI implementation', evidence_refs=('EV-GRANT',),
    )
    runtime.coding.request_external_work(_coding_request(runtime), assignee_agent_id='frontend.logic.01', grant_id=grant.grant_id)
    runtime.coding.claim_sources(agent_id='frontend.logic.01', task_id='T-UI', file_paths=('src/ui/editor.py',))
    patch = runtime.coding.submit_patch(
        producer_agent_id='frontend.logic.01', task_id='T-UI', work_id='W-UI',
        touched_files=('src/ui/editor.py',), patch_artifact_id='artifact-ui-editor-patch',
        compile_evidence_refs=('EV-COMPILE',), test_evidence_refs=('EV-TEST',),
    )
    coding_ready = runtime.coding.assess_readiness(
        patch.patch_id, PatchVerificationEvidence('EV-CODE-VERIFY', 'verification.unit-property.01', True),
    )
    assert coding_ready.ready is True
    return runtime, patch, coding_ready


def _quality(kind, evidence_id, observation_ids, *, passed=True, false_accepts=0, regressions=0, verifier='verification.integration-e2e.01'):
    return UIQualityEvidence(
        evidence_id=evidence_id, verifier_agent_id=verifier, kind=kind, passed=passed,
        false_accepts=false_accepts, regressions=regressions,
        observation_ids=tuple(observation_ids), evidence_refs=(evidence_id + '-RAW',),
    )


def test_source_and_part_v_readiness_without_rendered_state_is_not_ui_ready():
    runtime, patch, coding_ready = _prepared_runtime()
    receipt = runtime.ui.assess_readiness(
        patch_id=patch.patch_id, coding_readiness_receipt_id=coding_ready.receipt_id,
        observation_ids=(), quality_evidence_ids=(),
    )
    assert receipt.ready is False
    assert 'missing_render_observation' in receipt.reasons


def test_visual_only_or_single_viewport_responsive_evidence_cannot_satisfy_all_ui_gates():
    runtime, patch, coding_ready = _prepared_runtime()
    mobile = _render(runtime, patch_id=patch.patch_id, width=390, height=844, suffix='mobile')
    visual = runtime.ui.record_quality_evidence(_quality(UIQualityKind.VISUAL_DIFF, 'EV-VISUAL', (mobile.observation_id,)))
    responsive = runtime.ui.record_quality_evidence(_quality(UIQualityKind.RESPONSIVE, 'EV-RESP', (mobile.observation_id,)))
    receipt = runtime.ui.assess_readiness(
        patch_id=patch.patch_id, coding_readiness_receipt_id=coding_ready.receipt_id,
        observation_ids=(mobile.observation_id,), quality_evidence_ids=(visual.evidence_id, responsive.evidence_id),
    )
    assert receipt.ready is False
    assert 'missing_accessibility_evidence' in receipt.reasons
    assert 'responsive_viewport_coverage_insufficient' in receipt.reasons


def test_ui_quality_requires_independent_verification_authority():
    runtime, patch, _ = _prepared_runtime()
    mobile = _render(runtime, patch_id=patch.patch_id, width=390, height=844, suffix='mobile')
    with pytest.raises(PermissionError):
        runtime.ui.record_quality_evidence(_quality(
            UIQualityKind.ACCESSIBILITY, 'EV-SELF', (mobile.observation_id,), verifier='frontend.logic.01',
        ))


def test_full_browser_visual_responsive_accessibility_and_interaction_evidence_is_ui_ready():
    runtime, patch, coding_ready = _prepared_runtime()
    mobile = _render(runtime, patch_id=patch.patch_id, width=390, height=844, suffix='mobile')
    desktop = _render(runtime, patch_id=patch.patch_id, width=1440, height=900, suffix='desktop')
    observation_ids = (mobile.observation_id, desktop.observation_id)
    evidence = (
        runtime.ui.record_quality_evidence(_quality(UIQualityKind.VISUAL_DIFF, 'EV-VISUAL', observation_ids)),
        runtime.ui.record_quality_evidence(_quality(UIQualityKind.RESPONSIVE, 'EV-RESP', observation_ids)),
        runtime.ui.record_quality_evidence(_quality(UIQualityKind.ACCESSIBILITY, 'EV-A11Y', observation_ids)),
        runtime.ui.record_quality_evidence(_quality(UIQualityKind.INTERACTION_E2E, 'EV-E2E', observation_ids)),
    )
    receipt = runtime.ui.assess_readiness(
        patch_id=patch.patch_id, coding_readiness_receipt_id=coding_ready.receipt_id,
        observation_ids=observation_ids, quality_evidence_ids=tuple(x.evidence_id for x in evidence),
        require_interaction=True,
    )
    assert receipt.ready is True
    assert receipt.reasons == ()
    assert receipt.digest


def test_failed_or_regressing_quality_evidence_blocks_ui_readiness():
    runtime, patch, coding_ready = _prepared_runtime()
    mobile = _render(runtime, patch_id=patch.patch_id, width=390, height=844, suffix='mobile')
    desktop = _render(runtime, patch_id=patch.patch_id, width=1440, height=900, suffix='desktop')
    obs = (mobile.observation_id, desktop.observation_id)
    evidence = (
        runtime.ui.record_quality_evidence(_quality(UIQualityKind.VISUAL_DIFF, 'EV-VISUAL', obs, regressions=1)),
        runtime.ui.record_quality_evidence(_quality(UIQualityKind.RESPONSIVE, 'EV-RESP', obs)),
        runtime.ui.record_quality_evidence(_quality(UIQualityKind.ACCESSIBILITY, 'EV-A11Y', obs)),
    )
    receipt = runtime.ui.assess_readiness(
        patch_id=patch.patch_id, coding_readiness_receipt_id=coding_ready.receipt_id,
        observation_ids=obs, quality_evidence_ids=tuple(x.evidence_id for x in evidence),
    )
    assert receipt.ready is False
    assert 'quality_regressions' in receipt.reasons
