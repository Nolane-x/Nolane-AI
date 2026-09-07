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
    return runtime, persisted, cognitive_state


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


def test_persisted_execution_decision_cognitive_identity_survives_restore():
    runtime, persisted, cognitive_state = _authority_with_persisted_decision()

    restored = _restore(runtime, persisted.to_state())
    decision = restored.get_decision(restored.get_session("execution-00000001").decision_receipt_ids[0])

    assert decision.cognitive_state_digest == cognitive_state.digest
    assert restored.resolve_cognitive_state(decision.cognitive_state_digest) == cognitive_state


def test_restore_rejects_self_consistent_decision_with_orphan_cognitive_digest():
    runtime, persisted, _ = _authority_with_persisted_decision()
    state = persisted.to_state()
    forged = dict(state["decisions"][0])
    forged["cognitive_state_digest"] = "f" * 64
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

    with pytest.raises(ValueError, match="persisted execution decision.*cognitive state"):
        _restore(runtime, state)


def test_public_execution_compatibility_surfaces_inherit_cognition_aware_authority():
    assert CompatibilityOrganizationExecutionControlPlane.__bases__ == (
        OrganizationExecutionControlPlane,
    )
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
