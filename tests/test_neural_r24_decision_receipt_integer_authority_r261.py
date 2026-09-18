import pytest

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution_types import (
    AgentDecisionReceipt,
    ExecutionAction,
    ExecutionCounters,
    InferenceRequest,
)


def _request(*, step_index: int = 0) -> InferenceRequest:
    schema = ("inspect", "complete")
    return InferenceRequest(
        agent_id="agent-r261",
        neural_version="Neural-R2.3-Ultra-Recursive-DAgger-Gated",
        task_id="task-r261",
        context_digest=canonical_digest({"context": "r261"}),
        encoder_version="encoder-r261",
        checkpoint_digest="checkpoint-r261",
        action_schema=schema,
        action_schema_digest=canonical_digest(list(schema)),
        counters=ExecutionCounters(),
        step_index=step_index,
        execution_lineage_version=1,
    )


def _legacy_direct(
    *,
    step_index=0,
    compute_units=1,
    request_provenance_version=1,
) -> AgentDecisionReceipt:
    action = ExecutionAction.wait(reason="r261-hold")
    payload = {
        "backend_id": "backend-r261",
        "request_digest": canonical_digest({"request": "legacy-r261"}),
        "agent_id": "agent-r261",
        "neural_version": "Neural-R2.3-Ultra-Recursive-DAgger-Gated",
        "checkpoint_digest": "checkpoint-r261",
        "encoder_version": "encoder-r261",
        "context_digest": canonical_digest({"context": "legacy-r261"}),
        "action_schema_digest": canonical_digest(["inspect", "complete"]),
        "step_index": step_index,
        "action": action.to_state(),
        "compute_units": compute_units,
    }
    digest = canonical_digest(payload)
    return AgentDecisionReceipt(
        receipt_id="decision-" + digest[:24],
        backend_id=payload["backend_id"],
        request_digest=payload["request_digest"],
        agent_id=payload["agent_id"],
        neural_version=payload["neural_version"],
        checkpoint_digest=payload["checkpoint_digest"],
        encoder_version=payload["encoder_version"],
        context_digest=payload["context_digest"],
        action_schema_digest=payload["action_schema_digest"],
        step_index=step_index,
        action=action,
        compute_units=compute_units,
        digest=digest,
        request_provenance_version=request_provenance_version,
        request=None,
    )


def _modern_decision() -> AgentDecisionReceipt:
    return AgentDecisionReceipt.create(
        backend_id="backend-r261",
        request=_request(),
        action=ExecutionAction.wait(reason="r261-hold"),
        compute_units=1,
    )


@pytest.mark.parametrize("step_index", (False, 0.0, "0"))
def test_r261_direct_legacy_receipt_rejects_non_exact_integer_step_index(step_index) -> None:
    with pytest.raises(ValueError, match="decision step index must be an exact integer"):
        _legacy_direct(step_index=step_index)


@pytest.mark.parametrize("version", (True, 1.0, "1"))
def test_r261_direct_legacy_receipt_rejects_non_exact_provenance_version(version) -> None:
    with pytest.raises(ValueError, match="request provenance version must be an exact integer"):
        _legacy_direct(request_provenance_version=version)


@pytest.mark.parametrize("version", (2.0, "2"))
def test_r261_direct_modern_receipt_rejects_non_exact_provenance_version(version) -> None:
    canonical = _modern_decision()
    with pytest.raises(ValueError, match="request provenance version must be an exact integer"):
        AgentDecisionReceipt(
            receipt_id=canonical.receipt_id,
            backend_id=canonical.backend_id,
            request_digest=canonical.request_digest,
            agent_id=canonical.agent_id,
            neural_version=canonical.neural_version,
            checkpoint_digest=canonical.checkpoint_digest,
            encoder_version=canonical.encoder_version,
            context_digest=canonical.context_digest,
            action_schema_digest=canonical.action_schema_digest,
            step_index=canonical.step_index,
            action=canonical.action,
            compute_units=canonical.compute_units,
            digest=canonical.digest,
            cognitive_state_digest=canonical.cognitive_state_digest,
            request_provenance_version=version,
            request=canonical.request,
        )


@pytest.mark.parametrize("step_index", (False, 0.0, "0"))
def test_r261_restore_rejects_non_exact_integer_step_index(step_index) -> None:
    canonical = _legacy_direct()
    state = canonical.to_state()
    state["step_index"] = step_index

    with pytest.raises(ValueError, match="decision step index must be an exact integer"):
        AgentDecisionReceipt.from_state(state)


@pytest.mark.parametrize("compute_units", (True, 1.0, "1"))
def test_r261_restore_rejects_non_exact_integer_compute_units(compute_units) -> None:
    canonical = _legacy_direct()
    state = canonical.to_state()
    state["compute_units"] = compute_units

    with pytest.raises(ValueError, match="decision receipt direct construction must be canonical"):
        AgentDecisionReceipt.from_state(state)


@pytest.mark.parametrize("version", (True, 1.0, "1"))
def test_r261_restore_rejects_non_exact_legacy_provenance_version(version) -> None:
    canonical = _legacy_direct()
    state = canonical.to_state()
    state["request_provenance_version"] = version

    with pytest.raises(ValueError, match="request provenance version must be an exact integer"):
        AgentDecisionReceipt.from_state(state)


@pytest.mark.parametrize("version", (2.0, "2"))
def test_r261_restore_rejects_non_exact_modern_provenance_version(version) -> None:
    canonical = _modern_decision()
    state = canonical.to_state()
    state["request_provenance_version"] = version

    with pytest.raises(ValueError, match="request provenance version must be an exact integer"):
        AgentDecisionReceipt.from_state(state)


def test_r261_canonical_integer_receipts_roundtrip_without_semantic_change() -> None:
    legacy = _legacy_direct(step_index=3, compute_units=2, request_provenance_version=1)
    modern = _modern_decision()

    restored_legacy = AgentDecisionReceipt.from_state(legacy.to_state())
    restored_modern = AgentDecisionReceipt.from_state(modern.to_state())

    assert restored_legacy == legacy
    assert restored_modern == modern
    assert type(restored_legacy.step_index) is int
    assert type(restored_legacy.compute_units) is int
    assert type(restored_legacy.request_provenance_version) is int
    assert type(restored_modern.step_index) is int
    assert type(restored_modern.compute_units) is int
    assert type(restored_modern.request_provenance_version) is int
