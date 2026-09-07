from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from cogcoder.organization.runtime import OrganizationRuntime
from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution import (
    OrganizationExecutionControlPlane as GenericOrganizationExecutionControlPlane,
)
from nolane.external_core.execution_neural import (
    OrganizationExecutionControlPlane as NeuralOrganizationExecutionControlPlane,
)
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionCounters,
)
from nolane.neural.inference_bridge import CognitiveStateEncoder


TASK_ID = "T-NEURAL-R24-LIVE-COGNITIVE-STATE"
AGENT_ID = "coding.backend.01"


def _native_execution(control_plane_cls=NeuralOrganizationExecutionControlPlane):
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task(
        TASK_ID,
        title="Activate R2.4 cognitive state at inference boundary",
        plan_node_id="P-NEURAL-R24-LIVE-COGNITIVE-STATE",
    )
    runtime.tasks.lease(TASK_ID, AGENT_ID)
    native = control_plane_cls(
        registry=runtime.registry,
        tasks=runtime.tasks,
        context=runtime.memory_context,
        artifacts=runtime.artifacts,
        external_cores=runtime.external_cores,
        coding=runtime.coding,
    )
    return runtime, native


def _assert_verified_cognitive_state(runtime, native):
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
    return capsule, cognitive_state


def _request_kwargs(runtime, native, capsule):
    return dict(
        identity=runtime.registry.get(AGENT_ID),
        capsule=capsule,
        task_id=TASK_ID,
        action_schema=("repository.read",),
        counters=ExecutionCounters(),
        step_index=0,
        checkpoint_digest="checkpoint-test",
    )


def test_native_execution_builds_cognitive_state_from_exact_verified_context_provenance():
    runtime, native = _native_execution()

    _assert_verified_cognitive_state(runtime, native)


def test_generic_native_execution_owns_cognitive_state_activation_gate():
    runtime, native = _native_execution(GenericOrganizationExecutionControlPlane)

    _assert_verified_cognitive_state(runtime, native)


def test_neural_execution_specialization_inherits_generic_cognition_gate():
    assert (
        NeuralOrganizationExecutionControlPlane._compile_context_for_inference
        is GenericOrganizationExecutionControlPlane._compile_context_for_inference
    )


def test_live_encoder_binds_cognitive_state_digest_to_verified_context_digest():
    runtime, native = _native_execution(GenericOrganizationExecutionControlPlane)
    capsule, cognitive_state = _assert_verified_cognitive_state(runtime, native)
    kwargs = _request_kwargs(runtime, native, capsule)

    plain_request = CognitiveStateEncoder(
        version=native.encoder.version
    ).build_request(**kwargs)
    live_request = native.encoder.build_request(**kwargs)

    assert live_request.context_digest == cognitive_state.bind_context_digest(
        plain_request.context_digest
    )
    assert live_request.context_digest != plain_request.context_digest


def test_modern_request_and_decision_expose_exact_cognitive_state_digest():
    runtime, native = _native_execution(GenericOrganizationExecutionControlPlane)
    capsule, cognitive_state = _assert_verified_cognitive_state(runtime, native)
    request = native.encoder.build_request(**_request_kwargs(runtime, native, capsule))

    assert request.cognitive_state_digest == cognitive_state.digest
    assert request.payload()["cognitive_state_digest"] == cognitive_state.digest

    decision = AgentDecisionReceipt.create(
        backend_id="audit-backend",
        request=request,
        action=ExecutionAction.wait(reason="audit cognition provenance"),
    )
    assert decision.cognitive_state_digest == cognitive_state.digest
    assert decision.to_state()["cognitive_state_digest"] == cognitive_state.digest
    assert AgentDecisionReceipt.from_state(decision.to_state()) == decision


def test_legacy_request_and_decision_do_not_fabricate_cognitive_identity_or_change_shape():
    runtime, native = _native_execution(GenericOrganizationExecutionControlPlane)
    native.context = runtime.context
    capsule, cognitive_state = native._compile_context_for_inference(
        AGENT_ID,
        task_id=TASK_ID,
    )
    request = CognitiveStateEncoder(version=native.encoder.version).build_request(
        **_request_kwargs(runtime, native, capsule)
    )

    assert cognitive_state is None
    assert request.cognitive_state_digest is None
    assert "cognitive_state_digest" not in request.payload()

    decision = AgentDecisionReceipt.create(
        backend_id="legacy-backend",
        request=request,
        action=ExecutionAction.wait(reason="legacy audit"),
    )
    assert decision.cognitive_state_digest is None
    assert "cognitive_state_digest" not in decision.to_state()
    assert AgentDecisionReceipt.from_state(decision.to_state()) == decision


def test_execution_attestation_rejects_self_consistent_decision_with_wrong_cognitive_digest():
    runtime, native = _native_execution(GenericOrganizationExecutionControlPlane)
    capsule, cognitive_state = _assert_verified_cognitive_state(runtime, native)
    request = native.encoder.build_request(**_request_kwargs(runtime, native, capsule))
    decision = AgentDecisionReceipt.create(
        backend_id="audit-backend",
        request=request,
        action=ExecutionAction.wait(reason="audit cognition provenance"),
    )

    forged_state = decision.to_state()
    forged_state["cognitive_state_digest"] = "f" * 64
    forged_request = dict(forged_state["request"])
    forged_request["cognitive_state_digest"] = "f" * 64
    forged_state["request"] = forged_request
    forged_state["request_digest"] = canonical_digest(forged_request)
    forged_payload = {
        key: value
        for key, value in forged_state.items()
        if key not in {"receipt_id", "digest"}
    }
    forged_digest = canonical_digest(forged_payload)
    forged_state["digest"] = forged_digest
    forged_state["receipt_id"] = "decision-" + forged_digest[:24]
    forged = AgentDecisionReceipt.from_state(forged_state)

    with pytest.raises(ValueError, match="request_digest|cognitive_state_digest"):
        native._attest_decision_receipt(
            forged,
            request=request,
            backend=SimpleNamespace(backend_id="audit-backend"),
        )


def test_decision_cognitive_digest_resolves_from_persisted_context_after_restore():
    runtime, native = _native_execution(GenericOrganizationExecutionControlPlane)
    capsule, cognitive_state = _assert_verified_cognitive_state(runtime, native)
    request = native.encoder.build_request(**_request_kwargs(runtime, native, capsule))
    decision = AgentDecisionReceipt.create(
        backend_id="audit-backend",
        request=request,
        action=ExecutionAction.wait(reason="resolve persisted cognition"),
    )

    assert decision.cognitive_state_digest is not None
    assert native.resolve_cognitive_state(decision.cognitive_state_digest) == cognitive_state

    restored = OrganizationRuntime.from_state(runtime.to_state())
    assert (
        restored.execution.resolve_cognitive_state(decision.cognitive_state_digest)
        == cognitive_state
    )


def test_cognitive_state_resolver_fails_closed_for_unknown_digest():
    _, native = _native_execution(GenericOrganizationExecutionControlPlane)

    with pytest.raises(KeyError, match="unknown cognitive state digest"):
        native.resolve_cognitive_state("f" * 64)


def test_native_execution_legacy_context_never_fabricates_cognitive_provenance():
    runtime, native = _native_execution(GenericOrganizationExecutionControlPlane)
    native.context = runtime.context

    capsule, cognitive_state = native._compile_context_for_inference(
        AGENT_ID,
        task_id=TASK_ID,
    )

    assert cognitive_state is None
    assert capsule.context_compilation_receipt_id is None
    assert capsule.semantic_delta_digest is None


def test_neural_ci_tracks_and_compiles_private_execution_base_and_execution_types():
    workflow = Path(".github/workflows/neural-r24-runtime-activation.yml").read_text(
        encoding="utf-8"
    )

    assert workflow.count("'nolane/external_core/_execution_base.py'") == 2
    assert "            nolane/external_core/_execution_base.py \\\n" in workflow
    assert workflow.count("'nolane/external_core/execution_types.py'") == 2
    assert "            nolane/external_core/execution_types.py \\\n" in workflow


def test_neural_ci_covers_postmerge_runtime_state_closure():
    workflow = Path(".github/workflows/neural-r24-runtime-activation.yml").read_text(
        encoding="utf-8"
    )

    assert "      - main\n" in workflow
    assert workflow.count("'cogcoder/organization/runtime_core.py'") == 2
    assert "            cogcoder/organization/runtime_core.py \\\n" in workflow
    assert workflow.count("'nolane/metadata/runtime_state_map.py'") == 2
    assert "            nolane/metadata/runtime_state_map.py \\\n" in workflow
    assert workflow.count("'tests/test_refoundation_runtime_state_map.py'") == 2
    assert workflow.count("'tests/test_refoundation_wave2_zero_loss_runtime_digest.py'") == 2
    assert "            tests/test_refoundation_runtime_state_map.py \\\n" in workflow
    assert "            tests/test_refoundation_wave2_zero_loss_runtime_digest.py \\\n" in workflow
