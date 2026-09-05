from __future__ import annotations

import copy
import importlib

import pytest


def _live():
    return importlib.import_module("nolane.external_core.live_fabric")


def _snapshot():
    live = _live()
    return live.LiveExternalCoreSnapshot.create(
        registry_digest="registry-v1-current",
        authority_graph_digest="authority-current",
        artifact_graph_digest="artifact-current",
        handoff_frontier_digest=live.handoff_frontier_digest(({"handoff_id": "h2"}, {"handoff_id": "h1"})),
        work_trace_frontier_digest=live.work_trace_frontier_digest(({"trace_id": "t1"},)),
        source_state_frontier_digest=live.source_state_frontier_digest({"a": "state-a", "b": "state-b"}),
        component_versions={"verification": "1.0.0", "planning": "2.0.0"},
    )


def _current_kwargs(snapshot):
    return {
        "current_registry_digest": snapshot.registry_digest,
        "current_authority_graph_digest": snapshot.authority_graph_digest,
        "current_artifact_graph_digest": snapshot.artifact_graph_digest,
        "current_handoff_frontier_digest": snapshot.handoff_frontier_digest,
        "current_work_trace_frontier_digest": snapshot.work_trace_frontier_digest,
        "current_source_state_frontier_digest": snapshot.source_state_frontier_digest,
        "current_component_versions": dict(snapshot.component_versions),
    }


def test_live_frontier_digests_are_order_independent_and_domain_separated():
    live = _live()
    handoffs_a = live.handoff_frontier_digest(({"handoff_id": "b"}, {"handoff_id": "a"}))
    handoffs_b = live.handoff_frontier_digest(({"handoff_id": "a"}, {"handoff_id": "b"}))
    assert handoffs_a == handoffs_b
    assert handoffs_a.startswith("handoff-frontier-v1-")
    traces = live.work_trace_frontier_digest(({"handoff_id": "a"}, {"handoff_id": "b"}))
    assert traces.startswith("work-trace-frontier-v1-")
    assert traces != handoffs_a

    source_a = live.source_state_frontier_digest({"b": "2", "a": "1"})
    source_b = live.source_state_frontier_digest({"a": "1", "b": "2"})
    assert source_a == source_b
    assert source_a.startswith("source-state-frontier-v1-")


def test_frontier_digest_rejects_noncanonical_nan_and_ambiguous_duplicates():
    live = _live()
    with pytest.raises(ValueError):
        live.handoff_frontier_digest(({"value": float("nan")},))
    with pytest.raises(ValueError, match="duplicate"):
        live.handoff_frontier_digest(({"handoff_id": "same"}, {"handoff_id": "same"}))
    with pytest.raises(ValueError):
        live.source_state_frontier_digest({"source": ""})


def test_live_snapshot_is_content_addressed_and_exact_restorable():
    live = _live()
    snapshot = _snapshot()
    assert snapshot.snapshot_id.startswith("live-fabric-v1-")
    assert live.LiveExternalCoreSnapshot.from_state(snapshot.to_state()) == snapshot

    tampered = copy.deepcopy(snapshot.to_state())
    tampered["component_versions"][0][1] = "9.9.9"
    with pytest.raises(ValueError):
        live.LiveExternalCoreSnapshot.from_state(tampered)


def test_live_snapshot_rejects_bool_version_shape_and_duplicate_components():
    live = _live()
    with pytest.raises(ValueError):
        live.LiveExternalCoreSnapshot.create(
            registry_digest="r",
            authority_graph_digest="g",
            artifact_graph_digest="a",
            handoff_frontier_digest="h",
            work_trace_frontier_digest="t",
            source_state_frontier_digest="s",
            component_versions={"x": True},
        )

    state = _snapshot().to_state()
    state["component_versions"].append(list(state["component_versions"][0]))
    with pytest.raises(ValueError):
        live.LiveExternalCoreSnapshot.from_state(state)


def test_restore_assessment_exact_current_state_is_current():
    live = _live()
    snapshot = _snapshot()
    result = live.assess_live_restore(snapshot, **_current_kwargs(snapshot))
    assert result.disposition is live.LiveRestoreDisposition.CURRENT
    assert result.reasons == ()
    assert result.authoritative is True


def test_restore_assessment_registry_or_version_drift_requires_revalidation():
    live = _live()
    snapshot = _snapshot()
    kwargs = _current_kwargs(snapshot)
    kwargs["current_registry_digest"] = "registry-v1-new"
    result = live.assess_live_restore(snapshot, **kwargs)
    assert result.disposition is live.LiveRestoreDisposition.REQUIRES_REVALIDATION
    assert "registry-drift" in result.reasons
    assert result.authoritative is False

    kwargs = _current_kwargs(snapshot)
    kwargs["current_component_versions"] = {"verification": "1.0.1", "planning": "2.0.0"}
    result = live.assess_live_restore(snapshot, **kwargs)
    assert result.disposition is live.LiveRestoreDisposition.REQUIRES_REVALIDATION
    assert any(reason.startswith("version-drift:verification") for reason in result.reasons)


def test_restore_assessment_frontier_substitution_requires_revalidation():
    live = _live()
    snapshot = _snapshot()
    kwargs = _current_kwargs(snapshot)
    kwargs["current_handoff_frontier_digest"] = "handoff-frontier-v1-substituted"
    kwargs["current_work_trace_frontier_digest"] = "work-trace-frontier-v1-substituted"
    kwargs["current_source_state_frontier_digest"] = "source-state-frontier-v1-substituted"
    result = live.assess_live_restore(snapshot, **kwargs)
    assert result.disposition is live.LiveRestoreDisposition.REQUIRES_REVALIDATION
    assert {"handoff-frontier-drift", "work-trace-frontier-drift", "source-state-frontier-drift"} <= set(result.reasons)


def test_restore_assessment_missing_current_proof_is_unknown_not_current():
    live = _live()
    snapshot = _snapshot()
    kwargs = _current_kwargs(snapshot)
    kwargs["current_source_state_frontier_digest"] = None
    result = live.assess_live_restore(snapshot, **kwargs)
    assert result.disposition is live.LiveRestoreDisposition.UNKNOWN
    assert result.authoritative is False
    assert "missing-current-source-state-frontier" in result.reasons


def test_tampered_serialized_snapshot_is_quarantined_without_restoring_authority():
    live = _live()
    snapshot = _snapshot()
    tampered = snapshot.to_state()
    tampered["registry_digest"] = "forged-registry"
    result = live.assess_live_restore_state(tampered, **_current_kwargs(snapshot))
    assert result.disposition is live.LiveRestoreDisposition.QUARANTINED
    assert result.authoritative is False
    assert "invalid-snapshot" in result.reasons


def test_live_restore_layer_has_no_execution_or_authorization_surface():
    live = _live()
    snapshot = _snapshot()
    for subject in (snapshot, live):
        for forbidden in ("invoke", "execute", "authorize", "promote", "deploy", "repair"):
            assert not hasattr(subject, forbidden)
