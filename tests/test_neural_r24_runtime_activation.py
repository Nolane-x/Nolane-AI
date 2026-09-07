from __future__ import annotations

from dataclasses import replace

import pytest

from cogcoder.organization.context_intelligence import ContextBudget
from cogcoder.organization.execution import OrganizationExecutionControlPlane
from cogcoder.organization.runtime import OrganizationRuntime


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

    capsule = execution.context.compile(AGENT_ID, task_id=TASK_ID)

    assert events == ["modern-compile", "verify"]
    assert capsule.context_compilation_receipt_id is not None
    assert capsule.semantic_delta_digest is not None
