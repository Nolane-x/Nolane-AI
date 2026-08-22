import pytest

from cogcoder.organization.artifacts import ArtifactStore
from cogcoder.organization.ui_observations import UIObservationLedger, Viewport


def _artifact(store: ArtifactStore, kind: str, producer: str, content: str):
    return store.put(kind=kind, producer_agent_id=producer, content=content, evidence_refs=(f'EV-{kind}',))


def _required_artifacts(store: ArtifactStore, producer: str):
    return (
        _artifact(store, 'browser-runtime', producer, 'runtime-state'),
        _artifact(store, 'dom-snapshot', producer, '<main>ready</main>'),
        _artifact(store, 'screenshot', producer, 'screenshot-bytes-digest-proxy'),
    )


def test_render_observation_requires_browser_dom_and_screenshot_artifacts():
    store = ArtifactStore()
    runtime, dom, screenshot = _required_artifacts(store, 'frontend.browser-runtime.01')
    ledger = UIObservationLedger(store)
    row = ledger.record(
        task_id='T-UI', work_id='W-UI', producer_agent_id='frontend.browser-runtime.01',
        viewport=Viewport(390, 844, 3.0), browser_runtime_artifact_id=runtime.artifact_id,
        dom_artifact_id=dom.artifact_id, screenshot_artifact_id=screenshot.artifact_id,
        evidence_refs=('EV-OBS',),
    )
    assert row.viewport.width == 390
    assert row.browser_runtime_artifact_id == runtime.artifact_id
    assert row.dom_artifact_id == dom.artifact_id
    assert row.screenshot_artifact_id == screenshot.artifact_id
    assert row.digest

    with pytest.raises((KeyError, ValueError)):
        ledger.record(
            task_id='T-MISSING', work_id='W-MISSING', producer_agent_id='frontend.browser-runtime.01',
            viewport=Viewport(1280, 720, 1.0), browser_runtime_artifact_id=runtime.artifact_id,
            dom_artifact_id=dom.artifact_id, screenshot_artifact_id='artifact-does-not-exist',
            evidence_refs=('EV-MISSING',),
        )


def test_render_observation_rejects_artifact_kind_mismatch():
    store = ArtifactStore()
    runtime, dom, _ = _required_artifacts(store, 'frontend.browser-runtime.01')
    wrong = _artifact(store, 'interaction-trace', 'frontend.browser-runtime.01', 'trace')
    ledger = UIObservationLedger(store)
    with pytest.raises(ValueError):
        ledger.record(
            task_id='T-UI', work_id='W-UI', producer_agent_id='frontend.browser-runtime.01',
            viewport=Viewport(1440, 900, 1.0), browser_runtime_artifact_id=runtime.artifact_id,
            dom_artifact_id=dom.artifact_id, screenshot_artifact_id=wrong.artifact_id,
            evidence_refs=('EV-KIND',),
        )


def test_optional_cssom_accessibility_and_interaction_artifacts_are_kind_checked_and_restore_exactly():
    store = ArtifactStore()
    runtime, dom, screenshot = _required_artifacts(store, 'frontend.browser-runtime.01')
    cssom = _artifact(store, 'cssom-snapshot', 'frontend.browser-runtime.01', 'display:grid')
    a11y = _artifact(store, 'accessibility-tree', 'ux.visual-accessibility.01', 'button: Submit')
    interaction = _artifact(store, 'interaction-trace', 'frontend.browser-runtime.01', 'click->submitted')
    ledger = UIObservationLedger(store)
    row = ledger.record(
        task_id='T-UI', work_id='W-UI', producer_agent_id='frontend.browser-runtime.01',
        viewport=Viewport(1280, 800, 1.0), browser_runtime_artifact_id=runtime.artifact_id,
        dom_artifact_id=dom.artifact_id, screenshot_artifact_id=screenshot.artifact_id,
        cssom_artifact_id=cssom.artifact_id, accessibility_tree_artifact_id=a11y.artifact_id,
        interaction_trace_artifact_id=interaction.artifact_id, evidence_refs=('EV-FULL',),
    )
    restored = UIObservationLedger.from_state(artifacts=store, state=ledger.to_state())
    assert restored.get(row.observation_id) == row
    assert restored.to_state() == ledger.to_state()
