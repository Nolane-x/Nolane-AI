from __future__ import annotations

import pytest

from cogcoder.organization.execution import (
    OrganizationExecutionControlPlane as CompatibilityOrganizationExecutionControlPlane,
)
from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    OrganizationExecutionControlPlane,
)
from nolane.external_core.execution_neural import (
    OrganizationExecutionControlPlane as NeuralCompatibilityExecutionControlPlane,
)
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionBudget,
    ExecutionCounters,
)


TASK_ID = "T-NEURAL-R24-PERSISTED-COGNITION"
AGENT_ID = "coding.backend.01"
ACTION_SCHEMA = ("repository.read",)


def _authority_with_persisted_decision():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task(
        TASK_ID,
        title="Persist cognitive identity with execution decision",
        plan_node_id="P-NEURAL-R24-PERSISTED-COGNITION",
    )
    runtime.tasks.lease(TASK_ID, AGENT_ID)

    authority = OrganizationExecutionControlPlane(
        registry=runtime.registry,
        tasks=runtime.tasks,
        context=runtime.memory_context,
        artifacts=runtime.artifacts,
        external_cores=runtime.external_cores,
        coding=runtime.coding,
    )
    capsule, cognitive_state = authority._compile_context_for_inference(
        AGENT_ID,
        task_id=TASK_ID,
    )
    assert cognitive_state is not None
    request = authority.encoder.build_request(
        identity=runtime.registry.get(AGENT_ID),
        capsule=capsule,
        task_id=TASK_ID,
        action_schema=ACTION_SCHEMA,
        counters=ExecutionCounters(),
        step_index=0,
        checkpoint_digest="checkpoint-persisted-cognition",
    )
    decision = AgentDecisionReceipt.create(
        backend_id="persisted-cognition-backend",
        request=request,
        action=ExecutionAction.wait(reason="persist cognition"),
    )
    session = ExecutionSession(
        session_id="execution-00000001",
        agent_id=AGENT_ID,
        task_id=TASK_ID,
        action_schema=ACTION_SCHEMA,
        budget=ExecutionBudget(
            max_steps=4,
            max_tool_calls=4,
            max_external_core_calls=4,
            max_compute_units=16,
        ),
        counters=ExecutionCounters(
            steps=1,
            compute_units=decision.compute_units,
        ),
        step_index=1,
        state=ExecutionState.RUNNING,
        backend_id=decision.backend_id,
        checkpoint_digest=decision.checkpoint_digest,
        workspace_base_revision="persisted-cognition-test",
        decision_receipt_ids=(decision.receipt_id,),
    )
    persisted = OrganizationExecutionControlPlane(
        registry=runtime.registry,
        tasks=runtime.tasks,
        context=runtime.memory_context,
        artifacts=runtime.artifacts,
        external_cores=runtime.external_cores,
        coding=runtime.coding,
        sessions=(session,),
        decisions=(decision,),
        session_counter=1,
    )
    return runtime, persisted, cognitive_state, request


def _restore(runtime, state):
    return OrganizationExecutionControlPlane.from_state(
        registry=runtime.registry,
        tasks=runtime.tasks,
        context=runtime.memory_context,
        artifacts=runtime.artifacts,
        external_cores=runtime.external_cores,
        coding=runtime.coding,
        state=state,
    )


def _downgrade_decision_to_v1(state, receipt_id):
    decision_index = next(
        index
        for index, row in enumerate(state["decisions"])
        if row["receipt_id"] == receipt_id
    )
    forged = dict(state["decisions"][decision_index])
    original_receipt_id = forged["receipt_id"]
    forged.pop("request_provenance_version", None)
    forged.pop("request", None)
    payload = {
        key: value
        for key, value in forged.items()
        if key not in {"receipt_id", "digest"}
    }
    forged_digest = canonical_digest(payload)
    forged["digest"] = forged_digest
    forged["receipt_id"] = "decision-" + forged_digest[:24]
    state["decisions"][decision_index] = forged
    for session in state["sessions"]:
        session["decision_receipt_ids"] = [
            forged["receipt_id"] if row == original_receipt_id else row
            for row in session["decision_receipt_ids"]
        ]
    return forged


def _downgrade_first_decision_to_v1(state):
    return _downgrade_decision_to_v1(state, state["decisions"][0]["receipt_id"])


def _mixed_v1_v2_authority():
    runtime, persisted, _, request = _authority_with_persisted_decision()
    historical_state = persisted.to_state()
    historical_state.pop("request_provenance_version", None)
    historical_state.pop("request_provenance_decision_ids", None)
    historical_state.pop("context_provenance_version", None)
    historical_state.pop("context_provenance_decision_ids", None)
    legacy_state = _downgrade_first_decision_to_v1(historical_state)
    legacy_decision = AgentDecisionReceipt.from_state(legacy_state)
    legacy_session = ExecutionSession.from_state(historical_state["sessions"][0])

    modern_decision = AgentDecisionReceipt.create(
        backend_id="persisted-cognition-backend-modern",
        request=request,
        action=ExecutionAction.wait(reason="persist modern cognition"),
    )
    modern_session = ExecutionSession(
        session_id="execution-00000002",
        agent_id=AGENT_ID,
        task_id=TASK_ID,
        action_schema=ACTION_SCHEMA,
        budget=ExecutionBudget(
            max_steps=4,
            max_tool_calls=4,
            max_external_core_calls=4,
            max_compute_units=16,
        ),
        counters=ExecutionCounters(
            steps=1,
            compute_units=modern_decision.compute_units,
        ),
        step_index=1,
        state=ExecutionState.RUNNING,
        backend_id=modern_decision.backend_id,
        checkpoint_digest=modern_decision.checkpoint_digest,
        workspace_base_revision="persisted-cognition-modern",
        decision_receipt_ids=(modern_decision.receipt_id,),
    )
    mixed = OrganizationExecutionControlPlane(
        registry=runtime.registry,
        tasks=runtime.tasks,
        context=runtime.memory_context,
        artifacts=runtime.artifacts,
        external_cores=runtime.external_cores,
        coding=runtime.coding,
        sessions=(legacy_session, modern_session),
        decisions=(legacy_decision, modern_decision),
        session_counter=2,
    )
    return runtime, mixed, modern_decision


def test_persisted_execution_decision_cognitive_identity_survives_restore():
    runtime, persisted, cognitive_state, _ = _authority_with_persisted_decision()

    restored = _restore(runtime, persisted.to_state())
    decision = restored.get_decision(restored.get_session("execution-00000001").decision_receipt_ids[0])

    assert decision.cognitive_state_digest == cognitive_state.digest
    assert restored.resolve_cognitive_state(decision.cognitive_state_digest) == cognitive_state


def test_modern_decision_persists_canonical_inference_request_provenance():
    runtime, persisted, _, request = _authority_with_persisted_decision()
    decision = persisted.get_decision(
        persisted.get_session("execution-00000001").decision_receipt_ids[0]
    )

    execution_state = persisted.to_state()
    assert execution_state["request_provenance_version"] == 2
    assert execution_state["request_provenance_decision_ids"] == [decision.receipt_id]
    state = decision.to_state()
    assert state["request_provenance_version"] == 2
    assert state["request"] == request.to_state()
    assert decision.request == request
    assert persisted.get_inference_request(decision.receipt_id) == request

    restored = _restore(runtime, execution_state)
    restored_decision = restored.get_decision(decision.receipt_id)
    assert restored_decision.request == request
    assert restored.get_inference_request(decision.receipt_id) == request


def test_mixed_historical_and_modern_state_anchors_modern_request_provenance():
    runtime, mixed, modern_decision = _mixed_v1_v2_authority()

    state = mixed.to_state()

    assert state["request_provenance_version"] == 2
    assert state["request_provenance_decision_ids"] == [modern_decision.receipt_id]
    restored = _restore(runtime, state)
    assert restored.get_inference_request(modern_decision.receipt_id) == modern_decision.request


def test_mixed_state_rejects_self_consistent_downgrade_of_anchored_modern_decision():
    runtime, mixed, modern_decision = _mixed_v1_v2_authority()
    state = mixed.to_state()
    _downgrade_decision_to_v1(state, modern_decision.receipt_id)

    with pytest.raises(ValueError, match="request provenance.*binding|request provenance.*downgrade"):
        _restore(runtime, state)


def test_restore_rejects_request_provenance_downgrade_without_request_payload():
    runtime, persisted, _, _ = _authority_with_persisted_decision()
    state = persisted.to_state()
    state["decisions"][0]["request_provenance_version"] = 2
    state["decisions"][0].pop("request")

    with pytest.raises(ValueError, match="inference request"):
        _restore(runtime, state)


def test_restore_rejects_self_consistent_decision_request_provenance_downgrade():
    runtime, persisted, _, _ = _authority_with_persisted_decision()
    state = persisted.to_state()
    _downgrade_first_decision_to_v1(state)

    with pytest.raises(ValueError, match="request provenance.*binding|request provenance.*downgrade"):
        _restore(runtime, state)


def test_historical_execution_state_without_request_provenance_marker_restores_v1_decision():
    runtime, persisted, _, _ = _authority_with_persisted_decision()
    state = persisted.to_state()
    state.pop("request_provenance_version", None)
    state.pop("request_provenance_decision_ids", None)
    state.pop("context_provenance_version", None)
    state.pop("context_provenance_decision_ids", None)
    forged = _downgrade_first_decision_to_v1(state)

    restored = _restore(runtime, state)
    decision = restored.get_decision(forged["receipt_id"])

    assert decision.request_provenance_version == 1
    assert decision.request is None
    with pytest.raises(KeyError, match="no persisted inference request"):
        restored.get_inference_request(decision.receipt_id)


def test_restore_rejects_self_consistent_request_rebound_to_different_task():
    runtime, persisted, _, _ = _authority_with_persisted_decision()
    state = persisted.to_state()
    forged = dict(state["decisions"][0])
    original_receipt_id = forged["receipt_id"]
    forged["request"] = dict(forged["request"])
    forged["request"]["task_id"] = TASK_ID + "-rebound"
    forged["request_digest"] = canonical_digest(forged["request"])
    payload = {
        key: value
        for key, value in forged.items()
        if key not in {"receipt_id", "digest"}
    }
    forged_digest = canonical_digest(payload)
    forged["digest"] = forged_digest
    forged["receipt_id"] = "decision-" + forged_digest[:24]
    state["decisions"][0] = forged
    state["sessions"][0]["decision_receipt_ids"] = [forged["receipt_id"]]
    state["request_provenance_decision_ids"] = [
        forged["receipt_id"] if row == original_receipt_id else row
        for row in state["request_provenance_decision_ids"]
    ]

    with pytest.raises(ValueError, match="inference request.*task.*session"):
        _restore(runtime, state)


def test_restore_rejects_self_consistent_decision_with_orphan_cognitive_digest():
    runtime, persisted, _, _ = _authority_with_persisted_decision()
    state = persisted.to_state()
    forged = dict(state["decisions"][0])
    original_receipt_id = forged["receipt_id"]
    forged["cognitive_state_digest"] = "f" * 64
    if "request" in forged:
        forged["request"] = dict(forged["request"])
        forged["request"]["cognitive_state_digest"] = "f" * 64
        forged["request_digest"] = canonical_digest(forged["request"])
    payload = {
        key: value
        for key, value in forged.items()
        if key not in {"receipt_id", "digest"}
    }
    forged_digest = canonical_digest(payload)
    forged["digest"] = forged_digest
    forged["receipt_id"] = "decision-" + forged_digest[:24]
    state["decisions"][0] = forged
    state["sessions"][0]["decision_receipt_ids"] = [forged["receipt_id"]]
    state["request_provenance_decision_ids"] = [
        forged["receipt_id"] if row == original_receipt_id else row
        for row in state["request_provenance_decision_ids"]
    ]

    with pytest.raises(ValueError, match="persisted execution decision.*cognitive state"):
        _restore(runtime, state)


def test_public_execution_compatibility_surfaces_are_cognition_aware():
    assert CompatibilityOrganizationExecutionControlPlane is OrganizationExecutionControlPlane
    assert NeuralCompatibilityExecutionControlPlane.__bases__ == (
        OrganizationExecutionControlPlane,
    )
    assert hasattr(CompatibilityOrganizationExecutionControlPlane, "resolve_cognitive_state")
    assert hasattr(NeuralCompatibilityExecutionControlPlane, "resolve_cognitive_state")


def test_public_runtime_composes_only_cognition_aware_execution_authority():
    runtime = OrganizationRuntime.first_generation()

    assert isinstance(runtime.execution, OrganizationExecutionControlPlane)
    assert runtime.execution.context is runtime.memory_context
    assert callable(runtime.execution.resolve_cognitive_state)

    restored = OrganizationRuntime.from_state(runtime.to_state())

    assert isinstance(restored.execution, OrganizationExecutionControlPlane)
    assert restored.execution.context is restored.memory_context
    assert callable(restored.execution.resolve_cognitive_state)
