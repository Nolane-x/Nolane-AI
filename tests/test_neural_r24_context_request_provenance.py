from __future__ import annotations

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution import (
    ExecutionSession,
    ExecutionState,
    OrganizationExecutionControlPlane,
)
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionBudget,
    ExecutionCounters,
)


TASK_ID = "T-NEURAL-R24-CONTEXT-REQUEST-PROVENANCE"
AGENT_ID = "coding.backend.01"
ACTION_SCHEMA = ("repository.read",)


def _persisted_authority():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task(
        TASK_ID,
        title="Bind inference request to canonical context receipt",
        plan_node_id="P-NEURAL-R24-CONTEXT-REQUEST-PROVENANCE",
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
    verified = runtime.memory_context.verify_context_capsule(capsule)
    assert verified is not None
    request = authority.encoder.build_request(
        identity=runtime.registry.get(AGENT_ID),
        capsule=capsule,
        task_id=TASK_ID,
        action_schema=ACTION_SCHEMA,
        counters=ExecutionCounters(),
        step_index=0,
        checkpoint_digest="checkpoint-context-request-provenance",
    )
    decision = AgentDecisionReceipt.create(
        backend_id="context-request-provenance-backend",
        request=request,
        action=ExecutionAction.wait(reason="persist canonical context request provenance"),
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
        counters=ExecutionCounters(steps=1, compute_units=decision.compute_units),
        step_index=1,
        state=ExecutionState.RUNNING,
        backend_id=decision.backend_id,
        checkpoint_digest=decision.checkpoint_digest,
        workspace_base_revision="context-request-provenance-test",
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
    return runtime, persisted, verified, cognitive_state, request, decision


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


def _recanonicalize_decision_after_request_change(state):
    forged = dict(state["decisions"][0])
    original_receipt_id = forged["receipt_id"]
    forged_request = dict(forged["request"])
    forged_request["context_digest"] = "a" * 64
    forged["request"] = forged_request
    forged["context_digest"] = forged_request["context_digest"]
    forged["request_digest"] = canonical_digest(forged_request)
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
    if "request_provenance_decision_ids" in state:
        state["request_provenance_decision_ids"] = [
            forged["receipt_id"] if row == original_receipt_id else row
            for row in state["request_provenance_decision_ids"]
        ]
    if "context_provenance_decision_ids" in state:
        state["context_provenance_decision_ids"] = [
            forged["receipt_id"] if row == original_receipt_id else row
            for row in state["context_provenance_decision_ids"]
        ]
    return forged


def test_modern_request_binds_exact_canonical_context_receipt_and_capsule_digest():
    _, _, verified, cognitive_state, request, _ = _persisted_authority()

    assert getattr(request, "context_provenance_version", 1) == 2
    assert request.context_compilation_receipt_id == verified.receipt.receipt_id
    assert request.context_compilation_receipt_digest == verified.receipt.digest
    assert request.context_capsule_digest == verified.receipt.capsule_digest
    assert request.context_digest == cognitive_state.bind_context_digest(
        verified.receipt.capsule_digest
    )


def test_restore_rejects_self_consistent_forged_context_digest_detached_from_receipt():
    runtime, persisted, _, _, _, _ = _persisted_authority()
    state = persisted.to_state()
    _recanonicalize_decision_after_request_change(state)

    with pytest.raises(ValueError, match="context.*provenance|context.*receipt"):
        _restore(runtime, state)
