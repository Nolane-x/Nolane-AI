from __future__ import annotations

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.external_core.execution_neural import OrganizationExecutionControlPlane
from nolane.external_core.execution_types import ExecutionCounters
from nolane.neural.inference_bridge import CognitiveStateEncoder


TASK_ID = "T-NEURAL-R24-LIVE-COGNITIVE-STATE"
AGENT_ID = "coding.backend.01"


def _native_execution():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task(
        TASK_ID,
        title="Activate R2.4 cognitive state at inference boundary",
        plan_node_id="P-NEURAL-R24-LIVE-COGNITIVE-STATE",
    )
    runtime.tasks.lease(TASK_ID, AGENT_ID)
    native = OrganizationExecutionControlPlane(
        registry=runtime.registry,
        tasks=runtime.tasks,
        context=runtime.memory_context,
        artifacts=runtime.artifacts,
        external_cores=runtime.external_cores,
        coding=runtime.coding,
    )
    return runtime, native


def test_native_execution_builds_cognitive_state_from_exact_verified_context_provenance():
    runtime, native = _native_execution()

    capsule, cognitive_state = native._compile_context_for_inference(
        AGENT_ID,
        task_id=TASK_ID,
    )
    verified = runtime.memory_context.verify_context_capsule(capsule)

    assert verified is not None
    assert cognitive_state is not None
    assert cognitive_state.payload["agent_id"] == capsule.agent_id
    assert cognitive_state.payload["task_id"] == capsule.task_id
    assert (
        cognitive_state.payload["context_compilation_receipt_id"]
        == verified.receipt.receipt_id
    )
    assert (
        cognitive_state.payload["context_compilation_receipt_digest"]
        == verified.receipt.digest
    )
    assert cognitive_state.payload["semantic_delta_id"] == verified.delta.delta_id
    assert cognitive_state.payload["semantic_delta_digest"] == verified.delta.digest

    provenance = {
        (row.receipt_id, row.digest, row.authority)
        for row in cognitive_state.provenance
    }
    assert (
        verified.receipt.receipt_id,
        verified.receipt.digest,
        "observation",
    ) in provenance
    assert (
        verified.delta.delta_id,
        verified.delta.digest,
        "observation",
    ) in provenance


def test_live_encoder_binds_cognitive_state_digest_to_verified_context_digest():
    runtime, native = _native_execution()
    capsule, cognitive_state = native._compile_context_for_inference(
        AGENT_ID,
        task_id=TASK_ID,
    )
    identity = runtime.registry.get(AGENT_ID)
    kwargs = dict(
        identity=identity,
        capsule=capsule,
        task_id=TASK_ID,
        action_schema=("repository.read",),
        counters=ExecutionCounters(),
        step_index=0,
        checkpoint_digest="checkpoint-test",
    )

    plain_request = CognitiveStateEncoder(
        version=native.encoder.version
    ).build_request(**kwargs)
    live_request = native.encoder.build_request(**kwargs)

    assert cognitive_state is not None
    assert live_request.context_digest == cognitive_state.bind_context_digest(
        plain_request.context_digest
    )
    assert live_request.context_digest != plain_request.context_digest


def test_native_execution_legacy_context_never_fabricates_cognitive_provenance():
    runtime, native = _native_execution()
    native.context = runtime.context

    capsule, cognitive_state = native._compile_context_for_inference(
        AGENT_ID,
        task_id=TASK_ID,
    )

    assert cognitive_state is None
    assert capsule.context_compilation_receipt_id is None
    assert capsule.semantic_delta_digest is None
