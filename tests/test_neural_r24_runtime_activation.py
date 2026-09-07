from __future__ import annotations

from dataclasses import replace

import pytest

from cogcoder.organization.context_intelligence import ContextBudget
from cogcoder.organization.execution import OrganizationExecutionControlPlane
from cogcoder.organization.runtime import OrganizationRuntime
from cogcoder.organization.runtime_core import OrganizationRuntime as NativeOrganizationRuntime
from cogcoder.organization.types import EventKind
from nolane.external_core.execution import (
    OrganizationExecutionControlPlane as NativeOrganizationExecutionControlPlane,
)


TASK_ID = "T-NEURAL-R24-RUNTIME-ACTIVATION"
AGENT_ID = "coding.backend.01"


def _compiled_context():
    runtime = OrganizationRuntime.first_generation()
    runtime.tasks.add_task(
        TASK_ID,
        title="Activate Neural R2.4 runtime cognition",
        plan_node_id="P-NEURAL-R24-RUNTIME-ACTIVATION",
    )
    runtime.tasks.lease(TASK_ID, AGENT_ID)
    result = runtime.memory_context.compile_context(
        AGENT_ID,
        task_id=TASK_ID,
        budget=ContextBudget(
            max_memories=8,
            max_events=8,
            max_estimated_units=2048,
        ),
    )
    return runtime, result


def _emit_post_checkpoint_evidence(runtime, *, evidence_id: str):
    identity = runtime.registry.get(AGENT_ID)
    return runtime.ledger.append(
        EventKind.TEST_PASSED,
        source_agent_id=AGENT_ID,
        target_agent_id=AGENT_ID,
        region=identity.region,
        payload={"task_id": identity.current_task},
        evidence_refs=(evidence_id,),
    )


def test_modern_context_provenance_verifier_resolves_canonical_receipt_and_delta():
    runtime, result = _compiled_context()

    verified = runtime.memory_context.verify_context_capsule(result.capsule)

    assert verified is not None
    assert verified.receipt == result.receipt
    assert verified.delta == result.delta
    assert (
        runtime.memory_context.context_intelligence.receipt(result.receipt.receipt_id)
        == result.receipt
    )
    assert (
        runtime.memory_context.context_intelligence.semantic_delta(result.delta.digest)
        == result.delta
    )


def test_context_provenance_verifier_preserves_legacy_capsules_without_fabricating_evidence():
    runtime, _ = _compiled_context()
    legacy = runtime.context.compile(AGENT_ID, task_id=TASK_ID)

    assert legacy.semantic_delta_digest is None
    assert legacy.context_compilation_receipt_id is None
    assert runtime.memory_context.verify_context_capsule(legacy) is None


def test_context_provenance_verifier_fails_closed_on_partial_or_tampered_provenance():
    runtime, result = _compiled_context()
    legacy = runtime.context.compile(AGENT_ID, task_id=TASK_ID)

    with pytest.raises(ValueError):
        runtime.memory_context.verify_context_capsule(
            replace(
                legacy,
                context_compilation_receipt_id="context-compilation-99999999",
            )
        )

    with pytest.raises(ValueError):
        runtime.memory_context.verify_context_capsule(
            replace(
                result.capsule,
                context_budget_units=result.capsule.context_budget_units + 1,
            )
        )

    with pytest.raises(ValueError):
        runtime.memory_context.verify_context_capsule(
            replace(result.capsule, semantic_delta_digest="f" * 64)
        )


def test_context_provenance_verifier_rejects_receipt_or_delta_identity_mismatch():
    runtime, result = _compiled_context()

    with pytest.raises(ValueError):
        runtime.memory_context.verify_context_capsule(
            replace(result.capsule, agent_id="coding.backend.02")
        )

    with pytest.raises(ValueError):
        runtime.memory_context.verify_context_capsule(
            replace(result.capsule, task_id="T-OTHER")
        )


def test_execution_composition_uses_memory_context_for_live_and_restored_runtime():
    runtime = OrganizationRuntime.first_generation()

    assert runtime.execution.context is runtime.memory_context
    assert runtime.execution.context is not runtime.context

    restored = OrganizationRuntime.from_state(runtime.to_state())

    assert restored.execution.context is restored.memory_context
    assert restored.execution.context is not restored.context


def test_execution_composition_does_not_mutate_shared_memory_context_with_legacy_compile_surface():
    runtime = OrganizationRuntime.first_generation()

    assert "compile" not in runtime.memory_context.__dict__

    restored = OrganizationRuntime.from_state(runtime.to_state())

    assert "compile" not in restored.memory_context.__dict__


def test_execution_compiles_and_verifies_modern_context_before_inference_boundary():
    runtime, _ = _compiled_context()
    events: list[str] = []

    class RecordingModernContext:
        def compile_context(self, agent_id: str, *, task_id: str | None = None):
            events.append("compile")
            return runtime.memory_context.compile_context(agent_id, task_id=task_id)

        def verify_context_capsule(self, capsule):
            events.append("verify")
            return runtime.memory_context.verify_context_capsule(capsule)

    runtime.execution.context = RecordingModernContext()

    capsule = runtime.execution._compile_context_capsule(AGENT_ID, task_id=TASK_ID)

    assert events == ["compile", "verify"]
    assert capsule.context_compilation_receipt_id is not None
    assert capsule.semantic_delta_digest is not None
    assert runtime.memory_context.verify_context_capsule(capsule) is not None


def test_native_execution_authority_compiles_and_verifies_modern_context_without_compatibility_patch():
    runtime, _ = _compiled_context()
    native = NativeOrganizationExecutionControlPlane(
        registry=runtime.registry,
        tasks=runtime.tasks,
        context=runtime.memory_context,
        artifacts=runtime.artifacts,
        external_cores=runtime.external_cores,
        coding=runtime.coding,
    )

    capsule = native._compile_context_capsule(AGENT_ID, task_id=TASK_ID)

    assert capsule.context_compilation_receipt_id is not None
    assert capsule.semantic_delta_digest is not None
    assert runtime.memory_context.verify_context_capsule(capsule) is not None
    assert "compile" not in runtime.memory_context.__dict__


def test_execution_modern_context_verification_fails_closed():
    runtime, _ = _compiled_context()

    class RejectingModernContext:
        def compile_context(self, agent_id: str, *, task_id: str | None = None):
            return runtime.memory_context.compile_context(agent_id, task_id=task_id)

        def verify_context_capsule(self, capsule):
            raise ValueError("rejected modern context provenance")

    runtime.execution.context = RejectingModernContext()

    with pytest.raises(ValueError, match="rejected modern context provenance"):
        runtime.execution._compile_context_capsule(AGENT_ID, task_id=TASK_ID)


def test_execution_preserves_legacy_context_compiler_fallback():
    runtime, _ = _compiled_context()
    runtime.execution.context = runtime.context

    capsule = runtime.execution._compile_context_capsule(AGENT_ID, task_id=TASK_ID)

    assert capsule.context_compilation_receipt_id is None
    assert capsule.semantic_delta_digest is None


def test_execution_bridge_prefers_verified_modern_compiler_when_both_surfaces_exist():
    runtime, _ = _compiled_context()
    events: list[str] = []

    class AmbiguousContext:
        def compile_context(self, agent_id: str, *, task_id: str | None = None):
            events.append("modern-compile")
            return runtime.memory_context.compile_context(agent_id, task_id=task_id)

        def verify_context_capsule(self, capsule):
            events.append("verify")
            return runtime.memory_context.verify_context_capsule(capsule)

        def compile(self, agent_id: str, *, task_id: str | None = None):
            events.append("legacy-compile")
            return runtime.context.compile(agent_id, task_id=task_id)

    ambiguous = AmbiguousContext()
    execution = OrganizationExecutionControlPlane(
        registry=runtime.registry,
        tasks=runtime.tasks,
        context=ambiguous,
        artifacts=runtime.artifacts,
        external_cores=runtime.external_cores,
        coding=runtime.coding,
    )

    capsule = execution._compile_context_capsule(AGENT_ID, task_id=TASK_ID)

    assert events == ["modern-compile", "verify"]
    assert capsule.context_compilation_receipt_id is not None
    assert capsule.semantic_delta_digest is not None


def test_checkpoint_then_wake_replays_from_persisted_continuity_with_verified_provenance():
    runtime = OrganizationRuntime.first_generation()
    scheduler_checkpoint = runtime.checkpoint_agent(AGENT_ID)
    assert scheduler_checkpoint is not None
    post_checkpoint = _emit_post_checkpoint_evidence(runtime, evidence_id="EV-WAKE-CONTINUITY")

    capsule = runtime.wake_agent(AGENT_ID, reason="resume verified neural context")
    verified = runtime.memory_context.verify_context_capsule(capsule)

    assert verified is not None
    assert verified.receipt.continuity_checkpoint_id is not None
    continuity = runtime.memory_context.context_intelligence.checkpoint(
        verified.receipt.continuity_checkpoint_id
    )
    assert continuity.scheduler_checkpoint_event_id == scheduler_checkpoint
    assert verified.delta.checkpoint_id == continuity.checkpoint_id
    assert capsule.since_event_id == scheduler_checkpoint
    assert verified.receipt.replayed_full_history is False
    assert post_checkpoint.event_id in tuple(event.event_id for event in capsule.event_delta)


def test_checkpoint_wake_continuity_survives_runtime_restore():
    runtime = OrganizationRuntime.first_generation()
    scheduler_checkpoint = runtime.checkpoint_agent(AGENT_ID)
    assert scheduler_checkpoint is not None

    restored = OrganizationRuntime.from_state(runtime.to_state())
    post_checkpoint = _emit_post_checkpoint_evidence(restored, evidence_id="EV-WAKE-RESTORE")

    capsule = restored.wake_agent(AGENT_ID, reason="resume after runtime restore")
    verified = restored.memory_context.verify_context_capsule(capsule)

    assert verified is not None
    assert verified.receipt.continuity_checkpoint_id is not None
    continuity = restored.memory_context.context_intelligence.checkpoint(
        verified.receipt.continuity_checkpoint_id
    )
    assert continuity.scheduler_checkpoint_event_id == scheduler_checkpoint
    assert capsule.since_event_id == scheduler_checkpoint
    assert verified.receipt.replayed_full_history is False
    assert post_checkpoint.event_id in tuple(event.event_id for event in capsule.event_delta)


def test_pre_activation_checkpoint_without_continuity_index_falls_back_to_verified_full_replay():
    runtime = OrganizationRuntime.first_generation()
    assert runtime.checkpoint_agent(AGENT_ID) is not None
    state = runtime.to_state()
    state.pop("wake_continuity", None)

    restored = OrganizationRuntime.from_state(state)
    _emit_post_checkpoint_evidence(restored, evidence_id="EV-WAKE-LEGACY-STATE")

    capsule = restored.wake_agent(AGENT_ID, reason="resume legacy checkpoint safely")
    verified = restored.memory_context.verify_context_capsule(capsule)

    assert verified is not None
    assert verified.receipt.continuity_checkpoint_id is None
    assert verified.delta.checkpoint_id is None
    assert capsule.since_event_id is None
    assert verified.receipt.replayed_full_history is True


def test_native_runtime_core_owns_checkpoint_and_wake_provenance_gate():
    assert OrganizationRuntime.checkpoint_agent is NativeOrganizationRuntime.checkpoint_agent
    assert OrganizationRuntime.wake_agent is NativeOrganizationRuntime.wake_agent


def test_native_runtime_core_checkpoint_wake_emits_verified_continuity():
    runtime = NativeOrganizationRuntime.first_generation()
    scheduler_checkpoint = runtime.checkpoint_agent(AGENT_ID)
    assert scheduler_checkpoint is not None
    post_checkpoint = _emit_post_checkpoint_evidence(runtime, evidence_id="EV-NATIVE-WAKE")

    capsule = runtime.wake_agent(AGENT_ID, reason="native core resume")
    verified = runtime.memory_context.verify_context_capsule(capsule)

    assert verified is not None
    assert verified.receipt.continuity_checkpoint_id is not None
    continuity = runtime.memory_context.context_intelligence.checkpoint(
        verified.receipt.continuity_checkpoint_id
    )
    assert continuity.scheduler_checkpoint_event_id == scheduler_checkpoint
    assert capsule.since_event_id == scheduler_checkpoint
    assert verified.receipt.replayed_full_history is False
    assert post_checkpoint.event_id in tuple(event.event_id for event in capsule.event_delta)


def test_native_runtime_core_wake_continuity_survives_restore():
    runtime = NativeOrganizationRuntime.first_generation()
    scheduler_checkpoint = runtime.checkpoint_agent(AGENT_ID)
    assert scheduler_checkpoint is not None

    restored = NativeOrganizationRuntime.from_state(runtime.to_state())
    post_checkpoint = _emit_post_checkpoint_evidence(restored, evidence_id="EV-NATIVE-WAKE-RESTORE")

    capsule = restored.wake_agent(AGENT_ID, reason="native core restore resume")
    verified = restored.memory_context.verify_context_capsule(capsule)

    assert verified is not None
    assert verified.receipt.continuity_checkpoint_id is not None
    continuity = restored.memory_context.context_intelligence.checkpoint(
        verified.receipt.continuity_checkpoint_id
    )
    assert continuity.scheduler_checkpoint_event_id == scheduler_checkpoint
    assert capsule.since_event_id == scheduler_checkpoint
    assert verified.receipt.replayed_full_history is False
    assert post_checkpoint.event_id in tuple(event.event_id for event in capsule.event_delta)
